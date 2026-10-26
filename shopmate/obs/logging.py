import json
import logging
from datetime import datetime, timezone

from shopmate.api.trace import current_trace_id

LOG_KEYS = (
    "event",
    "trace_id",
    "sender_id",
    "message_id",
    "decision",
    "stages",
    "total_ms",
)


class TraceContextFilter(logging.Filter):
    """给每条日志补上当前请求的 trace_id。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "trace_id", ""):
            record.trace_id = current_trace_id()
        return True


class JsonFormatter(logging.Formatter):
    """一行一个 JSON，方便被日志系统直接采集。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in LOG_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_shopmate_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceContextFilter())

    root.handlers = [handler]
    root.setLevel(level)
    root._shopmate_configured = True  # type: ignore[attr-defined]
