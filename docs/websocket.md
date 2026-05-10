# WebSocket 实时进度推送指南

> 本文档介绍如何使用 WebSocket 实时获取评测进度，实现前端实时更新。

---

## 1. 概述

FinAgent-Eval 提供 WebSocket 实时进度推送功能，支持：

- **实时进度更新** - 无需轮询 API，实时获取评测进度
- **状态变更通知** - 评测完成、失败等状态变更即时通知
- **任务级事件** - 每个评测任务完成时推送详细结果
- **错误通知** - 评测过程中的错误即时推送

### 使用场景

- 前端实时进度条展示
- 评测监控面板
- 自动化测试集成
- 多用户协作场景

---

## 2. 连接与认证

### 连接 URL

```
ws://localhost:8000/ws/evaluation/{evaluation_id}?token={jwt_token}
```

| 参数 | 说明 |
|------|------|
| evaluation_id | 评测任务 ID |
| token | JWT 认证 Token |

### 认证方式

#### 方式一：URL 参数传递（推荐）

```javascript
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8000/ws/evaluation/${evalId}?token=${token}`);
```

#### 方式二：连接后发送认证消息

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/evaluation/${evalId}`);

ws.onopen = () => {
  // 发送认证消息
  ws.send(JSON.stringify({
    type: 'auth',
    token: token
  }));
};
```

### 心跳机制

- 服务端每 30 秒发送 `{"type": "ping"}` 消息
- 客户端应在 10 秒内回复 `{"type": "pong"}`
- 超过 60 秒无响应将断开连接

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'ping') {
    ws.send(JSON.stringify({ type: 'pong' }));
  }
};
```

---

## 3. 消息类型

### 3.1 进度更新（progress）

评测进度变化时推送：

```json
{
  "type": "progress",
  "evaluation_id": "eval-20250601-abc123",
  "current_phase": "DYNAMIC",
  "progress": 45.5,
  "stage": "running",
  "message": "正在执行动态评估任务 36/80",
  "timestamp": "2025-06-01T14:20:00Z"
}
```

| 字段 | 说明 |
|------|------|
| current_phase | 当前阶段：STATIC / DYNAMIC / TRUST |
| progress | 进度百分比 (0-100) |
| stage | 状态：pending / running / completed |
| message | 进度描述信息 |

### 3.2 状态变更（status_change）

评测状态变更时推送：

```json
{
  "type": "status_change",
  "evaluation_id": "eval-20250601-abc123",
  "status": "completed",
  "result": {
    "overall_score": 87.5,
    "overall_rating": "A"
  },
  "timestamp": "2025-06-01T18:00:00Z"
}
```

| 状态 | 说明 |
|------|------|
| pending | 等待中 |
| running | 执行中 |
| completed | 已完成 |
| failed | 失败 |
| cancelled | 已取消 |

### 3.3 任务完成（task_completed）

单个评测任务完成时推送：

```json
{
  "type": "task_completed",
  "evaluation_id": "eval-20250601-abc123",
  "task_id": "task-001",
  "dimension": "accuracy",
  "score": 88.5,
  "timestamp": "2025-06-01T14:15:00Z"
}
```

### 3.4 错误通知（error）

评测过程中发生错误时推送：

```json
{
  "type": "error",
  "evaluation_id": "eval-20250601-abc123",
  "error": "MCP 服务连接超时",
  "timestamp": "2025-06-01T14:10:00Z"
}
```

---

## 4. 前端集成

### 4.1 React Hook 示例

```javascript
// hooks/useEvaluationProgress.js
import { useEffect, useRef, useState, useCallback } from 'react';

export function useEvaluationProgress(evalId, token) {
  const [progress, setProgress] = useState(null);
  const [status, setStatus] = useState('pending');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    if (!evalId || !token) return;

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/evaluation/${evalId}?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket 已连接');
      setConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'progress':
          setProgress(data);
          break;
        case 'status_change':
          setStatus(data.status);
          if (data.result) {
            setResult(data.result);
          }
          break;
        case 'task_completed':
          // 可选：处理任务完成事件
          console.log(`任务 ${data.task_id} 完成，分数: ${data.score}`);
          break;
        case 'error':
          setError(data.error);
          break;
        case 'ping':
          ws.send(JSON.stringify({ type: 'pong' }));
          break;
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket 错误:', err);
    };

    ws.onclose = () => {
      setConnected(false);
      // 自动重连
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current++;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        setTimeout(connect, delay);
      }
    };
  }, [evalId, token]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
  }, []);

  return {
    progress,
    status,
    result,
    error,
    connected,
    disconnect,
    reconnect: connect
  };
}
```

### 4.2 使用示例

```jsx
// components/EvaluationProgress.jsx
import React from 'react';
import { Progress, Alert, Card, Tag } from 'antd';
import { useEvaluationProgress } from '../hooks/useEvaluationProgress';

function EvaluationProgress({ evalId, token }) {
  const { progress, status, result, error, connected } = useEvaluationProgress(evalId, token);

  if (error) {
    return <Alert type="error" message="评测错误" description={error} />;
  }

  return (
    <Card title="评测进度">
      <div style={{ marginBottom: 16 }}>
        <Tag color={connected ? 'green' : 'red'}>
          {connected ? '已连接' : '未连接'}
        </Tag>
        <Tag color={
          status === 'completed' ? 'green' :
          status === 'running' ? 'blue' :
          status === 'failed' ? 'red' : 'default'
        }>
          {status}
        </Tag>
      </div>

      {progress && (
        <>
          <div style={{ marginBottom: 8 }}>
            当前阶段: {progress.current_phase}
          </div>
          <Progress 
            percent={progress.progress} 
            status={status === 'completed' ? 'success' : 'active'}
          />
          <div style={{ color: '#666', marginTop: 8 }}>
            {progress.message}
          </div>
        </>
      )}

      {result && (
        <div style={{ marginTop: 16 }}>
          <h3>评测结果</h3>
          <p>总分: {result.overall_score}</p>
          <p>评级: {result.overall_rating}</p>
        </div>
      )}
    </Card>
  );
}
```

### 4.3 Vue 3 组合式 API 示例

```javascript
// composables/useEvaluationProgress.js
import { ref, onUnmounted } from 'vue';

export function useEvaluationProgress(evalId, token) {
  const progress = ref(null);
  const status = ref('pending');
  const error = ref(null);
  const connected = ref(false);
  
  let ws = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;

  const connect = () => {
    if (!evalId.value || !token.value) return;

    const wsUrl = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/evaluation/${evalId.value}?token=${token.value}`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      connected.value = true;
      reconnectAttempts = 0;
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'progress':
          progress.value = data;
          break;
        case 'status_change':
          status.value = data.status;
          break;
        case 'error':
          error.value = data.error;
          break;
        case 'ping':
          ws.send(JSON.stringify({ type: 'pong' }));
          break;
      }
    };

    ws.onclose = () => {
      connected.value = false;
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        setTimeout(connect, Math.min(1000 * Math.pow(2, reconnectAttempts), 30000));
      }
    };
  };

  const disconnect = () => {
    if (ws) ws.close();
  };

  onUnmounted(disconnect);

  return { progress, status, error, connected, connect, disconnect };
}
```

---

## 5. 最佳实践

### 5.1 连接池管理

对于需要监控多个评测的场景，建议使用连接池：

```javascript
class EvaluationWebSocketPool {
  constructor() {
    this.connections = new Map();
  }

  connect(evalId, token, onMessage) {
    if (this.connections.has(evalId)) {
      return this.connections.get(evalId);
    }

    const ws = new WebSocket(`ws://localhost:8000/ws/evaluation/${evalId}?token=${token}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
      } else {
        onMessage(evalId, data);
      }
    };

    this.connections.set(evalId, ws);
    return ws;
  }

  disconnect(evalId) {
    const ws = this.connections.get(evalId);
    if (ws) {
      ws.close();
      this.connections.delete(evalId);
    }
  }

  disconnectAll() {
    for (const ws of this.connections.values()) {
      ws.close();
    }
    this.connections.clear();
  }
}
```

### 5.2 错误处理

```javascript
class EvaluationWebSocket {
  constructor(evalId, token, options = {}) {
    this.evalId = evalId;
    this.token = token;
    this.onProgress = options.onProgress || (() => {});
    this.onStatusChange = options.onStatusChange || (() => {});
    this.onError = options.onError || (() => {});
    this.onConnectionChange = options.onConnectionChange || (() => {});
    
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
    this.reconnectDelay = options.reconnectDelay || 1000;
    
    this.connect();
  }

  connect() {
    try {
      const wsUrl = `${this.getWsProtocol()}//${window.location.host}/ws/evaluation/${this.evalId}?token=${this.token}`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.onConnectionChange(true);
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(JSON.parse(event.data));
      };

      this.ws.onerror = (err) => {
        console.error('WebSocket error:', err);
      };

      this.ws.onclose = () => {
        this.onConnectionChange(false);
        this.scheduleReconnect();
      };
    } catch (err) {
      console.error('Failed to connect:', err);
      this.scheduleReconnect();
    }
  }

  handleMessage(data) {
    switch (data.type) {
      case 'progress':
        this.onProgress(data);
        break;
      case 'status_change':
        this.onStatusChange(data);
        break;
      case 'error':
        this.onError(data.error);
        break;
      case 'ping':
        this.ws.send(JSON.stringify({ type: 'pong' }));
        break;
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(
        this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
        30000
      );
      setTimeout(() => this.connect(), delay);
    }
  }

  getWsProtocol() {
    return window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
```

### 5.3 性能优化

1. **按需连接**：只在用户查看评测详情页时建立 WebSocket 连接
2. **及时断开**：离开页面时主动断开连接
3. **节流更新**：对高频消息进行节流处理

```javascript
// 节流处理高频消息
function throttle(fn, delay) {
  let lastTime = 0;
  return function(...args) {
    const now = Date.now();
    if (now - lastTime >= delay) {
      lastTime = now;
      fn.apply(this, args);
    }
  };
}

// 使用节流处理进度更新
const throttledProgressUpdate = throttle((data) => {
  updateUI(data);
}, 1000); // 每秒最多更新一次

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'progress') {
    throttledProgressUpdate(data);
  }
};
```

---

## 6. 故障排查

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 连接失败 | Token 无效或过期 | 重新获取 Token |
| 频繁断开 | 网络不稳定 | 实现自动重连 |
| 无消息推送 | evaluation_id 不存在 | 检查评测是否已启动 |
| 消息延迟 | 服务端负载高 | 检查服务端日志 |

### 调试技巧

```javascript
// 开启详细日志
const ws = new WebSocket(url);

ws.onopen = () => console.log('[WS] Connected');
ws.onclose = (e) => console.log('[WS] Closed', e.code, e.reason);
ws.onerror = (e) => console.error('[WS] Error', e);
ws.onmessage = (e) => console.log('[WS] Message', e.data);
```
