"""
日志工具模块
使用 Loguru 提供强大的日志功能
"""
import sys
from pathlib import Path
from loguru import logger
from config.config import settings


def setup_logger():
    """配置日志系统"""
    
    # 移除默认日志处理器
    logger.remove()
    
    # 控制台输出
    logger.add(
        sys.stdout,
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # 文件输出（按日期分割）
    log_file = settings.LOGS_DIR / "job_agent_{time:YYYY-MM-DD}.log"
    logger.add(
        str(log_file),
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        rotation="00:00",
        retention="7 days",
        backtrace=True,
        diagnose=True
    )
    
    # 错误日志单独记录
    error_log_file = settings.LOGS_DIR / "error_{time:YYYY-MM-DD}.log"
    logger.add(
        str(error_log_file),
        format=settings.LOG_FORMAT,
        level="ERROR",
        rotation="00:00",
        retention="30 days",
        backtrace=True,
        diagnose=True
    )
    
    return logger


# 创建全局 logger 实例
log = setup_logger()
