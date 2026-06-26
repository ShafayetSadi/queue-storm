"""Safe structured logging.

Logs only non-sensitive operational metadata (ticket_id, latency, decision
source, case_type, verdict, fallback/safety flags). Complaint text is excluded
unless ``LOG_COMPLAINT_TEXT=true`` is explicitly set.
"""

from __future__ import annotations

import json
import logging
import sys

from app.core.config import get_settings

_logger = logging.getLogger("queuestorm")

if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def log_event(event: str, **fields: object) -> None:
    """Emit a single structured INFO line with safe metadata only."""
    settings = get_settings()
    if not settings.log_complaint_text:
        fields.pop("complaint", None)
    payload = {"event": event, **fields}
    try:
        _logger.info(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:  # logging must never break a request
        _logger.info("%s %s", event, fields)
