"""
数据质量监控模块

提供数据质量指标采集、监控和报告功能。
对应数据质量治理方案 - 阶段 2
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from collections import defaultdict

from ..interface.models import EvalTask, EvalResponse


@dataclass
class DataQualityMetrics:
    """数据质量指标"""
    completeness_rate: float = 0.0      # 完整性率
    accuracy_rate: float = 0.0          # 准确性率
    consistency_rate: float = 0.0       # 一致性率
    timeliness_rate: float = 0.0        # 时效性率
    uniqueness_rate: float = 0.0        # 唯一性率
    validity_rate: float = 0.0          # 有效性率
    overall_score: float = 0.0          # 综合评分


@dataclass
class DataQualityReport:
    """数据质量报告"""
    timestamp: datetime
    metrics: DataQualityMetrics
    details: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class DataQualityMonitor:
    """
    数据质量监控器
    
    负责监控评测数据的质量，包括：
    - 任务数据完整性检查
    - 响应数据有效性检查
    - 数据唯一性检查
    - 质量指标统计
    """
    
    def __init__(self):
        self.task_ids: set[str] = set()
        self.field_stats: dict[str, dict] = defaultdict(lambda: {
            'total': 0, 'missing': 0, 'invalid': 0
        })
        self.validation_errors: list[dict] = []
        self.response_stats: dict[str, int] = defaultdict(int)
        self.quality_scores: list[float] = []
    
    def check_task(self, task: EvalTask) -> dict:
        """
        检查任务数据质量
        
        Args:
            task: 评测任务
            
        Returns:
            检查结果，包含 is_valid 和 issues
        """
        result = {
            'task_id': task.task_id,
            'is_valid': True,
            'issues': []
        }
        
        # 唯一性检查
        if task.task_id in self.task_ids:
            result['is_valid'] = False
            result['issues'].append({
                'type': 'duplicate_task_id',
                'message': f'任务ID重复: {task.task_id}'
            })
            self.validation_errors.append({
                'timestamp': datetime.now().isoformat(),
                'task_id': task.task_id,
                'type': 'duplicate_task_id'
            })
        else:
            self.task_ids.add(task.task_id)
        
        # 完整性检查
        required_fields = ['task_id', 'task_type', 'dimension', 'input_data']
        for field_name in required_fields:
            value = getattr(task, field_name, None)
            self.field_stats[field_name]['total'] += 1
            if value is None or (isinstance(value, dict) and not value):
                self.field_stats[field_name]['missing'] += 1
                result['issues'].append({
                    'type': 'missing_field',
                    'field': field_name
                })
        
        # 时效性检查（如果元数据中有时间戳）
        if task.metadata and 'created_at' in task.metadata:
            try:
                created_at = datetime.fromisoformat(task.metadata['created_at'])
                age_days = (datetime.now() - created_at).days
                if age_days > 365:  # 数据超过1年
                    result['issues'].append({
                        'type': 'stale_data',
                        'message': f'任务数据已过期 {age_days} 天'
                    })
            except (ValueError, TypeError):
                pass
        
        if result['issues']:
            result['is_valid'] = False
        
        return result
    
    def check_response(self, response: EvalResponse) -> dict:
        """
        检查响应数据质量
        
        Args:
            response: 评测响应
            
        Returns:
            检查结果
        """
        result = {
            'is_valid': True,
            'issues': []
        }
        
        # 统计响应类型
        if response.error:
            self.response_stats['error'] += 1
            result['issues'].append({
                'type': 'agent_error',
                'message': response.error
            })
        elif not response.output and not response.tool_calls:
            self.response_stats['empty'] += 1
            result['is_valid'] = False
            result['issues'].append({
                'type': 'empty_response',
                'message': '响应无输出且无工具调用'
            })
        else:
            self.response_stats['success'] += 1
        
        # 时效性检查
        if response.metadata and 'latency_ms' in response.metadata:
            latency = response.metadata['latency_ms']
            if latency > 30000:  # 30秒
                result['issues'].append({
                    'type': 'high_latency',
                    'value': latency,
                    'message': f'响应延迟过高: {latency}ms'
                })
                self.response_stats['high_latency'] += 1
        
        # 工具调用检查
        if response.tool_calls:
            for i, call in enumerate(response.tool_calls):
                if not isinstance(call, dict):
                    result['issues'].append({
                        'type': 'invalid_tool_call_format',
                        'index': i
                    })
                elif 'tool_name' not in call:
                    result['issues'].append({
                        'type': 'missing_tool_name',
                        'index': i
                    })
        
        if result['issues']:
            result['is_valid'] = False
        
        return result
    
    def calculate_completeness(self) -> float:
        """计算完整性评分"""
        if not self.field_stats:
            return 1.0
        
        total_fields = 0
        complete_fields = 0
        for stats in self.field_stats.values():
            total_fields += stats['total']
            complete_fields += stats['total'] - stats['missing']
        
        return complete_fields / total_fields if total_fields > 0 else 1.0
    
    def calculate_validity(self) -> float:
        """计算有效性评分"""
        total = sum(self.response_stats.values())
        if total == 0:
            return 1.0
        
        valid = self.response_stats.get('success', 0)
        return valid / total
    
    def calculate_uniqueness(self) -> float:
        """计算唯一性评分（简化版）"""
        # 实际应该检查历史数据中的重复率
        return 1.0  # 假设所有任务ID都是唯一的
    
    def generate_report(self) -> DataQualityReport:
        """
        生成数据质量报告
        
        Returns:
            数据质量报告
        """
        # 计算各维度评分
        completeness = self.calculate_completeness()
        validity = self.calculate_validity()
        uniqueness = self.calculate_uniqueness()
        
        # 简化计算其他维度
        accuracy = 1.0  # 需要实际评分数据
        consistency = 1.0  # 需要跨模块对比
        timeliness = 1.0 - (self.response_stats.get('high_latency', 0) / max(1, sum(self.response_stats.values())))
        
        # 综合评分（加权平均）
        overall = (
            completeness * 0.25 +
            validity * 0.25 +
            uniqueness * 0.15 +
            accuracy * 0.15 +
            consistency * 0.10 +
            timeliness * 0.10
        )
        
        metrics = DataQualityMetrics(
            completeness_rate=completeness,
            accuracy_rate=accuracy,
            consistency_rate=consistency,
            timeliness_rate=timeliness,
            uniqueness_rate=uniqueness,
            validity_rate=validity,
            overall_score=overall
        )
        
        # 生成改进建议
        recommendations = []
        if completeness < 0.95:
            recommendations.append(f'数据完整性不足 ({completeness:.1%})，建议检查必填字段')
        if validity < 0.90:
            recommendations.append(f'数据有效性较低 ({validity:.1%})，建议检查 Agent 响应')
        if timeliness < 0.95:
            recommendations.append(f'响应时效性不佳 ({timeliness:.1%})，建议优化 Agent 性能')
        if self.validation_errors:
            recommendations.append(f'发现 {len(self.validation_errors)} 个验证错误，建议修复')
        
        return DataQualityReport(
            timestamp=datetime.now(),
            metrics=metrics,
            details={
                'field_stats': dict(self.field_stats),
                'response_stats': dict(self.response_stats),
                'validation_error_count': len(self.validation_errors),
                'recent_errors': self.validation_errors[-10:] if self.validation_errors else []
            },
            recommendations=recommendations
        )
    
    def reset(self):
        """重置监控状态"""
        self.task_ids.clear()
        self.field_stats.clear()
        self.validation_errors.clear()
        self.response_stats.clear()
        self.quality_scores.clear()
    
    def get_summary(self) -> dict:
        """获取监控摘要"""
        return {
            'total_tasks_checked': len(self.task_ids),
            'validation_error_count': len(self.validation_errors),
            'field_stats': dict(self.field_stats),
            'response_stats': dict(self.response_stats)
        }


# 全局监控器实例（单例模式）
_data_quality_monitor: DataQualityMonitor | None = None


def get_data_quality_monitor() -> DataQualityMonitor:
    """获取全局数据质量监控器实例"""
    global _data_quality_monitor
    if _data_quality_monitor is None:
        _data_quality_monitor = DataQualityMonitor()
    return _data_quality_monitor
