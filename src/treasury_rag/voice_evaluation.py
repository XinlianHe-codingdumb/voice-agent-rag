from __future__ import annotations

import re
from collections.abc import Sequence


def normalized_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9£.]+", text.casefold())


def word_error_rate(reference: str, hypothesis: str) -> float:
    expected = normalized_words(reference)
    actual = normalized_words(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, start=1):
        current = [row]
        for column, actual_word in enumerate(actual, start=1):
            substitution = previous[column - 1] + (expected_word != actual_word)
            deletion = previous[column] + 1
            insertion = current[column - 1] + 1
            current.append(min(substitution, deletion, insertion))
        previous = current
    return previous[-1] / len(expected)


def critical_entity_accuracy(transcript: str, entities: Sequence[str]) -> float:
    if not entities:
        return 1.0
    normalized = " ".join(normalized_words(transcript))
    hits = sum(" ".join(normalized_words(entity)) in normalized for entity in entities)
    return hits / len(entities)
