import { useState, useEffect, useRef, useCallback } from 'react';

export const useWebSocket = (evaluationId) => {
  const [progress, setProgress] = useState(0);
  const [currentPhase, setCurrentPhase] = useState('');
  const [status, setStatus] = useState('');
  const [lastMessage, setLastMessage] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);

  const connect = useCallback(() => {
    if (!evaluationId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/evaluation/${evaluationId}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('WebSocket connected:', evaluationId);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLastMessage(data);

      switch (data.type) {
        case 'progress':
          setProgress(data.progress);
          setCurrentPhase(data.current_phase);
          break;
        case 'status_change':
          setStatus(data.status);
          break;
        case 'task_completed':
          // Update task-level progress
          break;
        case 'error':
          console.error('WebSocket error:', data.error);
          break;
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect after 3s
      reconnectTimeout.current = setTimeout(connect, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      ws.close();
    };
  }, [evaluationId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('ping');
    }
  }, []);

  return { progress, currentPhase, status, lastMessage, connected, sendPing };
};

export default useWebSocket;
