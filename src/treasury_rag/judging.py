from __future__ import annotations

import json
import re
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Judge output did not contain a JSON object")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Judge output must be a JSON object")
    return value


def cited_pdf_pages(text: str) -> list[int]:
    return [
        int(page)
        for page in re.findall(
            r"\[(?:Document [^\]]+,\s*)?PDF page (\d+)\]", text
        )
    ]
