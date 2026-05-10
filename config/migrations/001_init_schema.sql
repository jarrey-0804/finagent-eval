-- ============================================================================
-- 001_init_schema.sql
-- finagent-eval 初始数据库 Schema
-- PostgreSQL DDL
-- ============================================================================

-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- agents 表：注册的被测 Agent 信息
-- ============================================================================
CREATE TABLE IF NOT EXISTS agents (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    type        VARCHAR(100) NOT NULL,
    config      JSONB       NOT NULL DEFAULT '{}',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- evaluations 表：评测任务
-- ============================================================================
CREATE TABLE IF NOT EXISTS evaluations (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id     UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status       VARCHAR(50) NOT NULL DEFAULT 'pending',
    mode         VARCHAR(50) NOT NULL DEFAULT 'full',
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    config       JSONB       NOT NULL DEFAULT '{}'
);

-- ============================================================================
-- evaluation_results 表：评测结果明细
-- ============================================================================
CREATE TABLE IF NOT EXISTS evaluation_results (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID       NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    task_id      VARCHAR(255) NOT NULL,
    dimension    VARCHAR(100) NOT NULL,
    score        FLOAT       NOT NULL,
    details      JSONB       NOT NULL DEFAULT '{}'
);

-- ============================================================================
-- checkpoints 表：评测过程中的状态检查点
-- ============================================================================
CREATE TABLE IF NOT EXISTS checkpoints (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID       NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    thread_id    VARCHAR(255) NOT NULL,
    checkpoint   JSONB       NOT NULL DEFAULT '{}',
    parent_id    UUID        REFERENCES checkpoints(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 索引：高频查询列
-- ============================================================================

-- evaluations: 按 agent_id 查询
CREATE INDEX idx_evaluations_agent_id ON evaluations(agent_id);

-- evaluations: 按状态查询
CREATE INDEX idx_evaluations_status ON evaluations(status);

-- evaluations: 按启动时间排序
CREATE INDEX idx_evaluations_started_at ON evaluations(started_at DESC);

-- evaluation_results: 按 evaluation_id 查询
CREATE INDEX idx_evaluation_results_evaluation_id ON evaluation_results(evaluation_id);

-- evaluation_results: 按维度查询
CREATE INDEX idx_evaluation_results_dimension ON evaluation_results(dimension);

-- checkpoints: 按 evaluation_id 查询
CREATE INDEX idx_checkpoints_evaluation_id ON checkpoints(evaluation_id);

-- checkpoints: 按 thread_id 查询
CREATE INDEX idx_checkpoints_thread_id ON checkpoints(thread_id);

-- checkpoints: 按 parent_id 查询（用于重建检查点链）
CREATE INDEX idx_checkpoints_parent_id ON checkpoints(parent_id);

-- checkpoints: 按创建时间排序
CREATE INDEX idx_checkpoints_created_at ON checkpoints(created_at DESC);

-- agents: 按名称查询
CREATE INDEX idx_agents_name ON agents(name);

-- agents: 按类型查询
CREATE INDEX idx_agents_type ON agents(type);

-- ============================================================================
-- eval_tasks 表：评测任务明细
-- ============================================================================
CREATE TABLE IF NOT EXISTS eval_tasks (
    task_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_id      UUID        NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    task_type    VARCHAR(100) NOT NULL,
    dimension    VARCHAR(100) NOT NULL,
    input_data   JSONB       NOT NULL DEFAULT '{}',
    output       JSONB       NOT NULL DEFAULT '{}',
    score        DECIMAL(6, 2),
    status       VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ============================================================================
-- eval_reports 表：评测报告
-- ============================================================================
CREATE TABLE IF NOT EXISTS eval_reports (
    report_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_id         UUID        NOT NULL UNIQUE REFERENCES evaluations(id) ON DELETE CASCADE,
    total_score     DECIMAL(6, 2),
    grade           VARCHAR(10),
    dimension_scores JSONB      NOT NULL DEFAULT '{}',
    report_markdown TEXT,
    report_json     JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- audit_logs 表：审计日志
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_id     UUID        NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    event_type  VARCHAR(100) NOT NULL,
    event_data  JSONB       NOT NULL DEFAULT '{}',
    severity    VARCHAR(20) NOT NULL DEFAULT 'info',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 新增表索引
-- ============================================================================

-- eval_tasks: 按 eval_id 查询
CREATE INDEX idx_eval_tasks_eval_id ON eval_tasks(eval_id);

-- eval_tasks: 按状态查询
CREATE INDEX idx_eval_tasks_status ON eval_tasks(status);

-- eval_tasks: 按维度查询
CREATE INDEX idx_eval_tasks_dimension ON eval_tasks(dimension);

-- eval_reports: 按 eval_id 查询（UNIQUE约束已隐含索引）

-- audit_logs: 按 eval_id 查询
CREATE INDEX idx_audit_logs_eval_id ON audit_logs(eval_id);

-- audit_logs: 按事件类型查询
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);

-- audit_logs: 按严重程度查询
CREATE INDEX idx_audit_logs_severity ON audit_logs(severity);

-- audit_logs: 按创建时间排序
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
