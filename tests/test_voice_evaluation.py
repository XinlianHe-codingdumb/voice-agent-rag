from treasury_rag.voice_evaluation import critical_entity_accuracy, word_error_rate


def test_word_error_rate_counts_substitution() -> None:
    assert word_error_rate("the quick fox", "the slow fox") == 1 / 3


def test_critical_entity_accuracy_normalizes_case_and_punctuation() -> None:
    transcript = "The OBR's March 2026 forecast covered the stability rule."
    assert critical_entity_accuracy(
        transcript, ["OBR", "March 2026", "stability rule", "missing"]
    ) == 0.75
