"""logging_config: 구조화된 로깅 설정 모듈.

프로덕션(JSON)과 로컬 개발(human-readable) 로그 포맷을 설정합니다.
contextvars 기반 request_id 주입을 지원합니다.
"""

import json
import logging
import logging.config
from contextvars import ContextVar
from datetime import UTC, datetime

# 요청별 상관 ID — 미들웨어에서 설정, 모든 로그 레코드에 자동 주입
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """로그 레코드에 request_id 속성을 자동 추가하는 필터."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


class JsonFormatter(logging.Formatter):
    """프로덕션용 JSON 로그 포매터.

    각 로그 라인을 단일 JSON 객체로 출력합니다.
    ELK, CloudWatch Logs, Loki 등 로그 수집 도구와 호환됩니다.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(*, debug: bool = False) -> None:
    """애플리케이션 로깅을 설정합니다.

    Args:
        debug: True이면 human-readable 포맷, False이면 JSON 포맷.
    """
    if debug:
        formatter_config = {
            "class": "logging.Formatter",
            "format": "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    else:
        formatter_config = {
            "()": "core.logging_config.JsonFormatter",
        }

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": RequestIdFilter,
            },
        },
        "formatters": {
            "default": formatter_config,
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "filters": ["request_id"],
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"],
        },
        # uvicorn 로거도 통합 포맷 사용
        "loggers": {
            "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        },
    }
    logging.config.dictConfig(config)
