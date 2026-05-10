# 贡献指南

感谢您对 FinAgent-Eval 的关注！本文档将帮助您参与项目贡献。

---

## 1. 贡献流程

### 1.1 Fork 与 Clone

```bash
# Fork 仓库到您的 GitHub 账户

# Clone 您的 Fork
git clone https://github.com/YOUR_USERNAME/finagent-eval.git
cd finagent-eval

# 添加上游仓库
git remote add upstream https://github.com/finagent/finagent-eval.git
```

### 1.2 分支命名规范

| 类型 | 命名格式 | 示例 |
|------|----------|------|
| 功能开发 | `feature/描述` | `feature/add-new-adapter` |
| Bug 修复 | `fix/描述` | `fix/websocket-reconnect` |
| 文档更新 | `docs/描述` | `docs/update-api-reference` |
| 性能优化 | `perf/描述` | `perf/optimize-scoring` |
| 重构 | `refactor/描述` | `refactor/pipeline-engine` |

```bash
# 创建新分支
git checkout -b feature/add-new-adapter
```

### 1.3 PR 提交规范

**提交信息格式：**

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 (type)：**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具

**示例：**

```
feat(adapter): add support for Semantic Kernel adapter

- Implement SemanticKernelAdapter class
- Add unit tests for new adapter
- Update documentation

Closes #123
```

---

## 2. 开发环境搭建

### 2.1 依赖安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install
```

### 2.2 本地运行

```bash
# 启动数据库
docker-compose up -d db redis

# 运行数据库迁移
alembic upgrade head

# 启动 API 服务
finagent-eval serve --reload

# 启动前端开发服务器
cd web && npm install && npm run dev
```

### 2.3 调试配置

**VS Code 配置 (`.vscode/launch.json`)：**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "finagent.api.app:app",
        "--reload",
        "--port", "8000"
      ],
      "jinjaTemplates": true
    }
  ]
}
```

---

## 3. 代码规范

### 3.1 Python 代码风格

使用 Black + isort + ruff 进行代码格式化和检查：

```bash
# 格式化代码
black src tests
isort src tests

# 代码检查
ruff check src tests

# 类型检查
mypy src
```

**代码风格要点：**

- 使用 4 空格缩进
- 行长度不超过 100 字符
- 使用类型注解
- 编写 docstring

```python
def calculate_score(
    responses: list[EvalResponse],
    weights: dict[str, float] | None = None,
) -> float:
    """计算评测得分。

    Args:
        responses: 评测响应列表
        weights: 维度权重字典，默认使用系统权重

    Returns:
        加权平均得分，范围 0-100

    Raises:
        ValueError: 当 responses 为空时
    """
    if not responses:
        raise ValueError("responses cannot be empty")

    weights = weights or DEFAULT_WEIGHTS
    # ...
```

### 3.2 前端代码风格

使用 ESLint + Prettier：

```bash
cd web

# 格式化代码
npm run format

# 代码检查
npm run lint
```

**代码风格要点：**

- 使用函数组件和 Hooks
- 使用 TypeScript 类型
- 组件命名使用 PascalCase
- 文件命名使用 camelCase

```jsx
// components/ScoreBadge.jsx
import React from 'react';
import './ScoreBadge.css';

interface ScoreBadgeProps {
  score: number;
  rating: string;
  size?: 'small' | 'medium' | 'large';
}

export function ScoreBadge({ score, rating, size = 'medium' }: ScoreBadgeProps) {
  const colorClass = `score-badge--${rating.toLowerCase()}`;
  const sizeClass = `score-badge--${size}`;

  return (
    <span className={`score-badge ${colorClass} ${sizeClass}`}>
      {rating} ({score})
    </span>
  );
}
```

### 3.3 提交信息格式

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

---

## 4. 测试规范

### 4.1 单元测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/test_scoring.py

# 运行特定测试
pytest tests/unit/test_scoring.py::test_calculate_weighted_score

# 生成覆盖率报告
pytest --cov=finagent --cov-report=html
```

**测试命名规范：**

```python
# test_<module>_<scenario>_<expected_result>
def test_calculate_score_with_empty_responses_raises_error():
    with pytest.raises(ValueError):
        calculate_score([])

def test_calculate_score_with_valid_responses_returns_score():
    responses = [create_mock_response(score=80)]
    result = calculate_score(responses)
    assert result == 80.0
```

### 4.2 集成测试

```bash
# 运行集成测试
pytest tests/integration/

# 需要数据库的测试
pytest tests/integration/ --with-db
```

### 4.3 测试覆盖率

目标覆盖率：≥ 80%

```bash
# 检查覆盖率
pytest --cov=finagent --cov-fail-under=80
```

---

## 5. 文档贡献

### 5.1 文档格式

- 使用 Markdown 格式
- 中文文档使用中文标点
- 代码块指定语言

```markdown
\`\`\`python
# Python 代码示例
from finagent import EvalPipeline
\`\`\`

\`\`\`bash
# Shell 命令示例
pip install finagent-eval
\`\`\`
```

### 5.2 文档结构

```
docs/
├── README.md          # 文档索引
├── tutorial.md        # 快速入门
├── user_manual.md     # 用户手册
├── api_reference.md   # API 参考
├── api_examples.md    # API 示例
├── architecture.md    # 架构设计
├── deployment.md      # 部署指南
├── adapter_guide.md   # 适配器开发
├── interface_spec.md  # 接口规范
├── operations.md      # 运维手册
├── faq.md             # 常见问题
├── websocket.md       # WebSocket 指南
├── three_stage_pipeline.md  # 三阶段流水线
└── features/          # 功能专项文档
```

### 5.3 文档更新

更新文档时，请同步更新：

1. 相关文档的交叉引用
2. `docs/README.md` 索引
3. 主 `README.md` 相关章节

---

## 6. 发布流程

### 6.1 版本号规范

使用语义化版本 (SemVer)：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的 Bug 修复

### 6.2 发布检查清单

- [ ] 所有测试通过
- [ ] 代码覆盖率 ≥ 80%
- [ ] 文档已更新
- [ ] CHANGELOG.md 已更新
- [ ] 版本号已更新
- [ ] Release Notes 已准备

### 6.3 发布步骤

```bash
# 1. 更新版本号
bump2version patch  # 或 minor / major

# 2. 更新 CHANGELOG
# 编辑 CHANGELOG.md

# 3. 构建发布包
python -m build

# 4. 发布到 PyPI
twine upload dist/*

# 5. 创建 Git Tag
git tag -a v1.0.1 -m "Release v1.0.1"
git push origin v1.0.1
```

---

## 7. 社区准则

### 7.1 行为准则

- 尊重所有贡献者
- 保持专业和友善的交流
- 接受建设性批评
- 关注对社区最有利的事情

### 7.2 问题反馈

提交 Issue 时请包含：

1. 问题描述
2. 复现步骤
3. 期望行为
4. 实际行为
5. 环境信息（Python 版本、操作系统等）

### 7.3 联系方式

- **GitHub Issues**: https://github.com/finagent/finagent-eval/issues
- **GitHub Discussions**: https://github.com/finagent/finagent-eval/discussions
- **Email**: finagent-eval@example.com

---

感谢您的贡献！
