from treasury_rag.judging import cited_pdf_pages, parse_json_object


def test_parse_json_object_from_fenced_output() -> None:
    parsed = parse_json_object('```json\n{"correctness": 2, "reason": "ok"}\n```')
    assert parsed == {"correctness": 2, "reason": "ok"}


def test_extract_cited_pdf_pages() -> None:
    assert cited_pdf_pages("Fact [PDF page 22]. More [PDF page 165].") == [22, 165]
