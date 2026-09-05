import asyncio
import hashlib
import io

from fastapi import UploadFile

from treasury_rag import api


def test_pdf_upload_streams_to_hashed_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api, "RUNTIME_DOCUMENT_DIR", tmp_path)
    content = b"%PDF-" + (b"x" * (api.UPLOAD_BLOCK_BYTES + 17))
    upload = UploadFile(file=io.BytesIO(content), filename="large.pdf")

    path, digest, size = asyncio.run(api.persist_pdf_upload(upload))

    assert digest == hashlib.sha256(content).hexdigest()
    assert path == tmp_path / f"{digest}.pdf"
    assert path.read_bytes() == content
    assert size == len(content)


def test_pdf_upload_rejects_non_pdf_and_removes_temporary_file(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(api, "RUNTIME_DOCUMENT_DIR", tmp_path)
    upload = UploadFile(file=io.BytesIO(b"not a pdf"), filename="fake.pdf")

    try:
        asyncio.run(api.persist_pdf_upload(upload))
    except ValueError as exc:
        assert "not a valid PDF" in str(exc)
    else:
        raise AssertionError("Expected invalid PDF upload to fail")

    assert list(tmp_path.iterdir()) == []
