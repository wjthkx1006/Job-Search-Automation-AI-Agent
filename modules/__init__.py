"""
modules - 核心功能模块包
"""
from .models import JobPosition, Resume, JDAnalysis, ApplicationRecord, QualityCheckResult
from .job_collector import JobCollector, BossZhipinPlatform, LAGouPlatform, InternSengPlatform
from .job_filter import JobFilter, RuleEngine, SemanticMatcher
from .resume_adapter import ResumeOptimizer as ResumeAdapter, JDParser, ResumeGenerator
from .auto_submitter import AutoSubmitterManager, BossZhipinSubmitter
from .quality_checker import (
    ResumeQualityChecker, 
    JDMatchChecker, 
    SubmissionValidator, 
    QualityAssuranceManager
)

__all__ = [
    # 模型
    'JobPosition',
    'Resume',
    'JDAnalysis',
    'ApplicationRecord',
    'QualityCheckResult',
    
    # 数据采集
    'JobCollector',
    'BossZhipinPlatform',
    'LAGouPlatform',
    'InternSengPlatform',
    
    # 智能筛选
    'JobFilter',
    'RuleEngine',
    'SemanticMatcher',
    
    # 简历定制
    'ResumeAdapter',
    'JDParser',
    'ResumeGenerator',
    
    # 自动投递
    'AutoSubmitterManager',
    'BossZhipinSubmitter',
    
    # 质量保障
    'ResumeQualityChecker',
    'JDMatchChecker',
    'SubmissionValidator',
    'QualityAssuranceManager'
]
