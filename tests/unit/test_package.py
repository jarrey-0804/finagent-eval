"""
FinAgent-Eval 包初始化测试
"""

import pytest


class TestPackageInit:
    """包导入测试"""
    
    def test_import_interface(self):
        """测试interface模块导入"""
        from finagent.interface import (
            FinancialAgentInterface,
            AgentConfig,
            EvalTask,
            EvalResponse,
            EvalMode,
            EvalStatus,
            EvalDimension,
            TaskType,
            AgentType,
        )
        assert FinancialAgentInterface is not None
        assert EvalMode.FULL is not None
        assert EvalDimension.ACCURACY is not None
    
    def test_import_adapter(self):
        """测试adapter模块导入"""
        from finagent.adapter import (
            LangGraphAdapter,
            HTTPAdapter,
            AdapterRegistry,
        )
        assert LangGraphAdapter is not None
        assert HTTPAdapter is not None
    
    def test_import_taskgen(self):
        """测试taskgen模块导入"""
        from finagent.taskgen import (
            EvalTaskGenerator,
            TaskGeneratorConfig,
        )
        assert EvalTaskGenerator is not None
    
    def test_import_scoring(self):
        """测试scoring模块导入"""
        from finagent.scoring import (
            ScoringEngine,
            ScoringConfig,
            RatingLevel,
        )
        assert ScoringEngine is not None
        assert RatingLevel.S is not None
    
    def test_import_pipeline(self):
        """测试pipeline模块导入"""
        from finagent.pipeline import (
            EvalPipeline,
            PipelineConfig,
        )
        assert EvalPipeline is not None
    
    def test_import_judge(self):
        """测试judge模块导入"""
        from finagent.judge import (
            LLMJudge,
            JudgeConfig,
        )
        assert LLMJudge is not None
    
    def test_import_adversarial(self):
        """测试adversarial模块导入"""
        from finagent.adversarial import (
            AdversarialTester,
            AdversarialConfig,
        )
        assert AdversarialTester is not None
    
    def test_import_isolation(self):
        """测试isolation模块导入"""
        from finagent.isolation import (
            StateIsolationManager,
            IsolationConfig,
        )
        assert StateIsolationManager is not None
    
    def test_import_audit(self):
        """测试audit模块导入"""
        from finagent.audit import (
            UniversalToolAuditor,
            AuditConfig,
        )
        assert UniversalToolAuditor is not None
    
    def test_import_mcp(self):
        """测试mcp模块导入"""
        from finagent.mcp import (
            MCPServerManager,
            MCPServerConfig,
        )
        assert MCPServerManager is not None
    
    def test_import_report(self):
        """测试report模块导入"""
        from finagent.report import (
            ReportGenerator,
            ReportFormat,
        )
        assert ReportGenerator is not None
    
    def test_import_monitor(self):
        """测试monitor模块导入"""
        from finagent.monitor import (
            MetricsCollector,
            MetricsConfig,
        )
        assert MetricsCollector is not None
