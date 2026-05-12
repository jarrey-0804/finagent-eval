"""
数据质量监控模块单元测试

对应数据质量治理方案 - 阶段 1
"""

import pytest
from datetime import datetime

from finagent.interface.models import (
    AgentConfig, EvalTask, EvalResponse, 
    AgentType, TaskType, EvalDimension
)
from finagent.api.schemas import EvaluationRequest, AgentRegistrationRequest
from finagent.monitor.data_quality import (
    DataQualityMonitor, DataQualityMetrics, 
    DataQualityReport, get_data_quality_monitor
)


class TestAgentConfigValidation:
    """测试 AgentConfig 数据验证"""

    def test_valid_agent_config(self):
        """测试有效的 AgentConfig"""
        config = AgentConfig(
            agent_name="TestAgent",
            agent_type=AgentType.INVESTMENT_DECISION,
            version="1.0.0",
            framework="langgraph",
            llm_backend="gpt-4o"
        )
        assert config.agent_name == "TestAgent"
        assert config.version == "1.0.0"

    def test_agent_name_empty(self):
        """测试空的 Agent 名称"""
        with pytest.raises(ValueError, match="Agent 名称不能为空"):
            AgentConfig(
                agent_name="",
                agent_type=AgentType.INVESTMENT_DECISION,
                version="1.0.0",
                framework="langgraph"
            )

    def test_agent_name_too_long(self):
        """测试过长的 Agent 名称"""
        with pytest.raises(ValueError, match="Agent 名称长度不能超过 128 字符"):
            AgentConfig(
                agent_name="a" * 129,
                agent_type=AgentType.INVESTMENT_DECISION,
                version="1.0.0",
                framework="langgraph"
            )

    def test_version_invalid_format(self):
        """测试无效的版本号格式"""
        with pytest.raises(ValueError, match="版本号必须符合语义化版本格式"):
            AgentConfig(
                agent_name="TestAgent",
                agent_type=AgentType.INVESTMENT_DECISION,
                version="invalid",
                framework="langgraph"
            )

    def test_framework_invalid(self):
        """测试无效的框架"""
        with pytest.raises(ValueError, match="框架必须是以下之一"):
            AgentConfig(
                agent_name="TestAgent",
                agent_type=AgentType.INVESTMENT_DECISION,
                version="1.0.0",
                framework="invalid_framework"
            )


class TestEvalTaskValidation:
    """测试 EvalTask 数据验证"""

    def test_valid_eval_task(self):
        """测试有效的 EvalTask"""
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "什么是股票？"}
        )
        assert task.task_id == "task_001"
        assert task.dimension == EvalDimension.ACCURACY

    def test_task_id_empty(self):
        """测试空的任务ID"""
        with pytest.raises(ValueError, match="任务ID不能为空"):
            EvalTask(
                task_id="",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.ACCURACY,
                input_data={"query": "test"}
            )

    def test_task_id_invalid_chars(self):
        """测试包含非法字符的任务ID"""
        with pytest.raises(ValueError, match="任务ID只能包含字母、数字、下划线、连字符和点"):
            EvalTask(
                task_id="task@001",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.ACCURACY,
                input_data={"query": "test"}
            )

    def test_input_data_missing_query(self):
        """测试缺少 query 字段的输入数据"""
        with pytest.raises(ValueError, match="输入数据必须包含 query 字段"):
            EvalTask(
                task_id="task_001",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.ACCURACY,
                input_data={"other": "data"}
            )

    def test_input_data_query_too_short(self):
        """测试过短的 query 内容"""
        with pytest.raises(ValueError, match="query 内容过短"):
            EvalTask(
                task_id="task_001",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.ACCURACY,
                input_data={"query": "ab"}
            )

    def test_dimension_invalid(self):
        """测试无效的评测维度"""
        with pytest.raises(ValueError, match="评测维度必须是以下之一"):
            EvalTask(
                task_id="task_001",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension="invalid_dimension",
                input_data={"query": "test query"}
            )

    def test_task_type_dimension_consistency(self):
        """测试任务类型与维度的一致性（已放宽为警告级别）"""
        # 对抗性任务可以使用非对抗性维度（仅记录警告）
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.ADVERSARIAL,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个测试查询"}
        )
        assert task.task_type == TaskType.ADVERSARIAL
        assert task.dimension == EvalDimension.ACCURACY


class TestEvalResponseValidation:
    """测试 EvalResponse 数据验证"""

    def test_valid_response(self):
        """测试有效的响应"""
        response = EvalResponse(
            task_id="task_001",
            output="这是一个测试回答"
        )
        assert response.task_id == "task_001"
        assert response.output == "这是一个测试回答"

    def test_response_with_error(self):
        """测试包含错误的响应"""
        response = EvalResponse(
            task_id="task_001",
            output="",
            error="连接超时"
        )
        assert response.error == "连接超时"

    def test_response_empty_without_error(self):
        """测试无输出且无错误的无效响应"""
        with pytest.raises(ValueError, match="响应必须包含 output 或 tool_calls 至少一项"):
            EvalResponse(
                task_id="task_001",
                output="",
                error=None
            )

    def test_response_output_too_long(self):
        """测试过长的输出内容"""
        with pytest.raises(ValueError, match="输出内容过长"):
            EvalResponse(
                task_id="task_001",
                output="a" * 100001
            )

    def test_response_tool_calls_invalid_format(self):
        """测试无效格式的工具调用"""
        # Pydantic 会自动验证类型，这里测试类型错误
        with pytest.raises(Exception):  # pydantic 会抛出 ValidationError
            EvalResponse(
                task_id="task_001",
                output="",
                tool_calls=["invalid"]  # 应该是字典
            )

    def test_response_tool_calls_missing_name(self):
        """测试缺少 tool_name 的工具调用"""
        with pytest.raises(ValueError, match="工具调用记录第 0 项缺少 tool_name 字段"):
            EvalResponse(
                task_id="task_001",
                output="",
                tool_calls=[{"other": "data"}]
            )


class TestEvaluationRequestValidation:
    """测试 EvaluationRequest 数据验证"""

    def test_valid_request(self):
        """测试有效的评测请求"""
        request = EvaluationRequest(
            agent_id="agent_001",
            eval_mode="quick",
            endpoint_url="https://example.com/api"
        )
        assert request.agent_id == "agent_001"

    def test_agent_id_empty(self):
        """测试空的 Agent ID"""
        with pytest.raises(ValueError, match="Agent ID 不能为空"):
            EvaluationRequest(agent_id="")

    def test_eval_mode_invalid(self):
        """测试无效的评测模式"""
        with pytest.raises(ValueError, match="评测模式必须是以下之一"):
            EvaluationRequest(agent_id="agent_001", eval_mode="invalid")

    def test_endpoint_url_invalid_protocol(self):
        """测试无效的 URL 协议"""
        with pytest.raises(ValueError, match="URL 必须使用 http 或 https 协议"):
            EvaluationRequest(agent_id="agent_001", endpoint_url="ftp://example.com")

    def test_endpoint_url_invalid_format(self):
        """测试无效的 URL 格式"""
        with pytest.raises(ValueError, match="无效的 URL 格式"):
            EvaluationRequest(agent_id="agent_001", endpoint_url="not-a-url")

    def test_task_count_too_small(self):
        """测试过小的任务数量"""
        with pytest.raises(ValueError, match="任务数量必须大于 0"):
            EvaluationRequest(agent_id="agent_001", task_count=0)

    def test_task_count_too_large(self):
        """测试过大的任务数量"""
        with pytest.raises(ValueError, match="任务数量不能超过 1000"):
            EvaluationRequest(agent_id="agent_001", task_count=1001)


class TestDataQualityMonitor:
    """测试数据质量监控器"""

    def setup_method(self):
        """每个测试方法前重置监控器"""
        monitor = get_data_quality_monitor()
        monitor.reset()

    def test_check_task_valid(self):
        """测试有效的任务检查"""
        monitor = DataQualityMonitor()
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "什么是股票？"}
        )
        result = monitor.check_task(task)
        assert result['is_valid'] is True
        assert len(result['issues']) == 0

    def test_check_task_duplicate_id(self):
        """测试重复任务ID检查"""
        monitor = DataQualityMonitor()
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "什么是股票？"}
        )
        monitor.check_task(task)
        result = monitor.check_task(task)  # 重复检查
        assert result['is_valid'] is False
        assert any(i['type'] == 'duplicate_task_id' for i in result['issues'])

    def test_check_response_valid(self):
        """测试有效的响应检查"""
        monitor = DataQualityMonitor()
        response = EvalResponse(
            task_id="task_001",
            output="这是一个测试回答"
        )
        result = monitor.check_response(response)
        assert result['is_valid'] is True

    def test_check_response_empty(self):
        """测试空响应检查 - 注意：模型验证器会阻止创建空响应"""
        monitor = DataQualityMonitor()
        # 由于模型验证器会阻止空响应创建，我们测试监控器对空输出的处理
        response = EvalResponse(
            task_id="task_001",
            output="有内容",  # 先创建有效响应
            error=None
        )
        # 手动模拟空输出场景
        response.output = ""
        response.tool_calls = []
        result = monitor.check_response(response)
        assert result['is_valid'] is False
        assert any(i['type'] == 'empty_response' for i in result['issues'])

    def test_check_response_with_error(self):
        """测试包含错误的响应"""
        monitor = DataQualityMonitor()
        response = EvalResponse(
            task_id="task_001",
            output="",  # 空输出
            error="连接超时"  # 但有错误
        )
        result = monitor.check_response(response)
        # 有错误时，监控器认为响应是有效的（只是标记为错误）
        # 但监控器会记录错误问题
        assert any(i['type'] == 'agent_error' for i in result['issues'])
        # 统计应该记录为 error
        assert monitor.response_stats['error'] > 0

    def test_calculate_completeness(self):
        """测试完整性计算"""
        monitor = DataQualityMonitor()
        # 添加一些统计数据
        monitor.field_stats['task_id'] = {'total': 10, 'missing': 1}
        monitor.field_stats['dimension'] = {'total': 10, 'missing': 0}
        
        completeness = monitor.calculate_completeness()
        assert completeness == 19 / 20  # (9 + 10) / (10 + 10)

    def test_calculate_validity(self):
        """测试有效性计算"""
        monitor = DataQualityMonitor()
        monitor.response_stats['success'] = 8
        monitor.response_stats['error'] = 2
        
        validity = monitor.calculate_validity()
        assert validity == 0.8

    def test_generate_report(self):
        """测试生成质量报告"""
        monitor = DataQualityMonitor()
        
        # 添加一些测试数据
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "什么是股票？"}
        )
        monitor.check_task(task)
        
        response = EvalResponse(task_id="task_001", output="回答")
        monitor.check_response(response)
        
        report = monitor.generate_report()
        assert isinstance(report, DataQualityReport)
        assert isinstance(report.metrics, DataQualityMetrics)
        assert report.timestamp is not None

    def test_get_summary(self):
        """测试获取监控摘要"""
        monitor = DataQualityMonitor()
        task = EvalTask(
            task_id="task_001",
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "什么是股票？"}
        )
        monitor.check_task(task)
        
        summary = monitor.get_summary()
        assert summary['total_tasks_checked'] == 1
        assert 'field_stats' in summary


class TestDataQualityIntegration:
    """数据质量集成测试"""

    def test_full_evaluation_flow(self):
        """测试完整的评测流程数据质量"""
        monitor = DataQualityMonitor()
        
        # 创建评测请求
        request = EvaluationRequest(
            agent_id="test_agent",
            eval_mode="quick",
            task_count=5
        )
        
        # 创建评测任务
        for i in range(5):
            task = EvalTask(
                task_id=f"task_{i:03d}",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.ACCURACY,
                input_data={"query": f"这是一个测试问题 {i}"}
            )
            monitor.check_task(task)
        
        # 模拟响应
        for i in range(5):
            response = EvalResponse(
                task_id=f"task_{i:03d}",
                output=f"回答 {i}"
            )
            monitor.check_response(response)
        
        # 生成报告
        report = monitor.generate_report()
        assert report.metrics.completeness_rate == 1.0
        assert report.metrics.validity_rate == 1.0

    def test_data_quality_with_issues(self):
        """测试包含质量问题的场景"""
        monitor = DataQualityMonitor()
        
        # 创建一些有效任务
        for i in range(3):
            task = EvalTask(
                task_id=f"task_{i:03d}",
                task_type=TaskType.KNOWLEDGE_QA,
                dimension=EvalDimension.ACCURACY,
                input_data={"query": f"这是一个测试问题 {i}"}
            )
            monitor.check_task(task)
        
        # 创建重复任务
        duplicate_task = EvalTask(
            task_id="task_000",  # 重复ID
            task_type=TaskType.KNOWLEDGE_QA,
            dimension=EvalDimension.ACCURACY,
            input_data={"query": "这是一个重复的问题"}
        )
        result = monitor.check_task(duplicate_task)
        assert not result['is_valid']
        
        # 生成报告
        report = monitor.generate_report()
        assert len(report.recommendations) > 0
        assert any('验证错误' in r for r in report.recommendations)
