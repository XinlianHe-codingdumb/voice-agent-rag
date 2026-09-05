import json
from types import SimpleNamespace

from treasury_rag.api import build_realtime_session
from treasury_rag.realtime import _field


def test_multipart_field_preserves_sdp_bytes() -> None:
    payload = b"v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
    encoded = _field("boundary", "sdp", payload, "application/sdp")

    assert b'name="sdp"' in encoded
    assert b"Content-Type: application/sdp" in encoded
    assert payload in encoded


def test_multipart_session_is_valid_json() -> None:
    session = {"type": "realtime", "audio": {"output": {"voice": "marin"}}}
    value = json.dumps(session).encode("utf-8")
    encoded = _field("boundary", "session", value, "application/json")

    assert value in encoded
    assert encoded.endswith(b"\r\n")


def test_realtime_session_delegates_turn_and_interrupt_decisions_to_client() -> None:
    settings = SimpleNamespace(
        realtime_model="gpt-realtime-2.1",
        asr_model="gpt-4o-transcribe",
        realtime_voice="marin",
    )
    session = build_realtime_session(
        settings,
        "book.pdf",
        "user: earlier question",
        "- [goal] learn RAG",
    )
    turn_detection = session["audio"]["input"]["turn_detection"]

    assert turn_detection["type"] == "semantic_vad"
    assert turn_detection["create_response"] is False
    assert turn_detection["interrupt_response"] is False
    assert "learn RAG" in session["instructions"]
