"""
统一日志配置模块

功能：
- 控制台输出 + 文件输出双路日志
- 支持 INFO / WARNING / ERROR 三级
- 日志文件按天滚动，自动清理旧日志

用法：
    from common.logger import setup_logger, get_logger

    setup_logger(log_dir="./logs", level="INFO")
    logger = get_logger("crawler")
    logger.info("开始爬取...")
    logger.warning("请求失败，重试中...")
    logger.error("致命错误！")
"""

from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


_DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False
_log_dir: Optional[Path] = None


def setup_logger(
    log_dir: Optional[str | Path] = None,
    level: str = "INFO",
    log_format: str = _DEFAULT_LOG_FORMAT,
    date_format: str = _DEFAULT_DATE_FORMAT,
    console: bool = True,
    file_output: bool = True,
    backup_days: int = 30,
) -> None:
    """
    初始化全局日志配置

    Args:
        log_dir: 日志文件目录，默认 ./logs
        level: 日志级别，DEBUG/INFO/WARNING/ERROR
        log_format: 日志格式
        date_format: 日期格式
        console: 是否输出到控制台
        file_output: 是否输出到文件
        backup_days: 日志文件保留天数
    """
    global _initialized, _log_dir

    # 获取根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有 handler，避免重复输出
    root_logger.handlers.clear()

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # ---- 控制台输出 ----
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # ---- 文件输出 ----
    if file_output and log_dir:
        _log_dir = Path(log_dir)
        _log_dir.mkdir(parents=True, exist_ok=True)

        # 主日志文件（按天滚动）
        main_log_path = _log_dir / "app.log"
        file_handler = TimedRotatingFileHandler(
            str(main_log_path),
            when="midnight",
            interval=1,
            backupCount=backup_days,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        file_handler.suffix = "%Y%m%d"
        root_logger.addHandler(file_handler)

        # ERROR 级别单独存文件，方便排查
        error_log_path = _log_dir / "error.log"
        error_handler = TimedRotatingFileHandler(
            str(error_log_path),
            when="midnight",
            interval=1,
            backupCount=backup_days,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        error_handler.suffix = "%Y%m%d"
        root_logger.addHandler(error_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    获取命名 logger

    Args:
        name: logger 名称，通常用模块名

    Returns:
        logging.Logger 实例
    """
    if not _initialized:
        # 延迟初始化：默认只输出到控制台
        setup_logger(log_dir=None, file_output=False)
    return logging.getLogger(name)
