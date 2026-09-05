from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid


REALTIME_URL = "https://api.openai.com/v1/realtime/calls"


def create_realtime_call(
    *,
    api_key: str,
    sdp: bytes,
    session: dict[str, object],
    safety_identifier: str,
) -> bytes:
    """Exchange a browser SDP offer for an OpenAI Realtime SDP answer."""
    boundary = f"----voice-rag-{uuid.uuid4().hex}"
    body = b"".join(
        [
            _field(boundary, "sdp", sdp, "application/sdp"),
            _field(
                boundary,
                "session",
                json.dumps(session, ensure_ascii=False).encode("utf-8"),
                "application/json",
            ),
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    request = urllib.request.Request(
        REALTIME_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "OpenAI-Safety-Identifier": safety_identifier,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Realtime session creation failed ({exc.code}): {detail}") from exc


def _field(boundary: str, name: str, value: bytes, content_type: str) -> bytes:
    return b"".join(
        [
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{name}"\r\n'.encode("ascii"),
            f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
            value,
            b"\r\n",
        ]
    )
