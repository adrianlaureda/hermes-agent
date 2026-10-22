"""Tests for the interim_assistant_callback config gating in tui_gateway.

These tests exercise the real _agent_cbs() wiring rather than a local
imitation, so a break in the production callback registration is caught.
"""

from __future__ import annotations

from unittest.mock import patch


def test_load_interim_assistant_messages_defaults_true():
    from tui_gateway.server import _load_interim_assistant_messages

    with patch("tui_gateway.server._load_cfg", return_value={}):
        assert _load_interim_assistant_messages() is True


def test_agent_cbs_includes_interim_callback_when_enabled():
    """_agent_cbs() includes interim_assistant_callback when the config is on.

    Exercises the real _agent_cbs() wiring: the callback must be present in
    the returned dict and, when invoked, must emit a message.interim event
    with the text and already_streamed flag passed through.
    """
    from tui_gateway.server import _agent_cbs

    emitted: list[tuple] = []

    def fake_emit(event_type, sid, payload=None):
        emitted.append((event_type, sid, payload))

    with patch("tui_gateway.server._load_cfg", return_value={}), \
         patch("tui_gateway.server._emit", side_effect=fake_emit):
        cbs = _agent_cbs("test-session")

        assert "interim_assistant_callback" in cbs
        cb = cbs["interim_assistant_callback"]
        assert callable(cb)

        # Invoke the real callback inside the patch context — the lambda
        # resolves _emit by name at call time, so it must be called while
        # the patch is active.
        cb("hello world", already_streamed=True)

    assert len(emitted) == 1
    assert emitted[0][0] == "message.interim"
    assert emitted[0][1] == "test-session"
    assert emitted[0][2]["text"] == "hello world"
    assert emitted[0][2]["already_streamed"] is True


def test_history_projection_respects_disabled_interim_messages():
    """La recarga conserva herramientas y respuesta final, sin narración desactivada."""
    from tui_gateway.server import _history_to_messages

    history = [
        {"role": "user", "content": "consulta"},
        {
            "role": "assistant",
            "content": "narracion intermedia",
            "tool_calls": [{
                "id": "call_1",
                "function": {"name": "todo", "arguments": '{"action":"read"}'},
            }],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "hecho"},
        {"role": "assistant", "content": "respuesta final"},
    ]
    with patch(
        "tui_gateway.server._load_cfg",
        return_value={"display": {"interim_assistant_messages": False}},
    ):
        rows = _history_to_messages(history)
    assert [row.get("text") for row in rows if row["role"] == "assistant"] == ["respuesta final"]
    assert next(row for row in rows if row["role"] == "tool")["args"] == {"action": "read"}


def test_agent_cbs_omits_interim_callback_when_disabled():
    from tui_gateway.server import _agent_cbs

    with patch(
        "tui_gateway.server._load_cfg",
        return_value={"display": {"interim_assistant_messages": False}},
    ):
        assert "interim_assistant_callback" not in _agent_cbs("test-session")
