import json
import logging

import pytest

from app.infrastructure import obs


def test_new_trace_id_is_eight_hex_chars():
    trace_id = obs.new_trace_id()
    assert len(trace_id) == 8
    assert all(c in "0123456789abcdef" for c in trace_id)


def test_new_trace_id_is_unique_across_calls():
    assert obs.new_trace_id() != obs.new_trace_id()


def test_log_emits_one_json_line_with_required_fields(capsys):
    obs.configure_logging()
    obs.log(
        "abc12345",
        "policy_decision",
        tool="get_sales_orders",
        role="operator",
        decision="allow",
        reason="ok",
    )

    captured = capsys.readouterr().out.strip()
    assert "\n" not in captured

    payload = json.loads(captured)
    assert payload["trace_id"] == "abc12345"
    assert payload["event"] == "policy_decision"
    assert payload["level"] == "INFO"
    assert payload["tool"] == "get_sales_orders"
    assert payload["decision"] == "allow"
    assert "ts" in payload


def test_log_respects_configured_level(capsys, monkeypatch):
    monkeypatch.setattr(obs.settings, "log_level", "WARNING")
    obs.configure_logging()

    obs.log("abc12345", "debug_event", level=logging.INFO)
    assert capsys.readouterr().out.strip() == ""

    obs.log("abc12345", "warning_event", level=logging.WARNING)
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "warning_event"
    assert payload["level"] == "WARNING"


def test_logging_config_routes_uvicorn_through_json_formatter():
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        assert obs.LOGGING_CONFIG["loggers"][name]["handlers"] == ["json"]
        assert obs.LOGGING_CONFIG["loggers"][name]["propagate"] is False


def test_log_never_emits_a_raw_api_key(capsys):
    obs.configure_logging()
    obs.log("abc12345", "user_message", chars=42, sha8="deadbeef")
    payload = json.loads(capsys.readouterr().out.strip())
    assert "text" not in payload
    assert payload["chars"] == 42


def test_log_rejects_a_field_name_colliding_with_a_reserved_logrecord_attribute():
    obs.configure_logging()
    with pytest.raises(ValueError, match="name"):
        obs.log("abc12345", "tool_executed", name="evil")


def test_log_rejects_reserved_field_name_even_below_the_configured_level(monkeypatch):
    """The collision must surface immediately, not only once someone lowers LOG_LEVEL."""
    monkeypatch.setattr(obs.settings, "log_level", "WARNING")
    obs.configure_logging()
    with pytest.raises(ValueError, match="name"):
        obs.log("abc12345", "tool_executed", level=logging.DEBUG, name="evil")


def test_json_formatter_falls_back_to_a_safe_payload_on_circular_reference(capsys):
    obs.configure_logging()
    circular: dict = {}
    circular["self"] = circular

    obs.log("abc12345", "circular_test", bad=circular)

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["level"] == "ERROR"
    assert payload["event"] == "log_format_failed"
    assert "error" in payload
    assert payload["original_event"] == "circular_test"


def test_json_formatter_excludes_uvicorns_color_message_field(capsys):
    obs.configure_logging()
    logging.getLogger("uvicorn").info(
        "Started server process [%d]",
        1,
        extra={"color_message": "\x1b[36m%d\x1b[0m"},
    )
    payload = json.loads(capsys.readouterr().out.strip())
    assert "color_message" not in payload
