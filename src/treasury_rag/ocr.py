"""CPU-only OCR fallback. No document images leave this machine."""
import threading

_lock = threading.Lock()
_engine = None


def read_scanned_page(path, page_index):
    import pypdfium2 as pdfium
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    global _engine
    # PDFium and the shared engine are serialized across concurrent uploads.
    with _lock:
        if _engine is None:
            _engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)
        document = pdfium.PdfDocument(str(path))
        try:
            page = document[page_index]
            try:
                width, height = page.get_size()
                bitmap = page.render(scale=min(2.5, 3200 / max(width, height)))
                try:
                    # PDFium default array is BGR, as expected by RapidOCR.
                    result, _ = _engine(np.array(bitmap.to_numpy(), copy=True))
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            document.close()
        return "\n".join(str(row[1]) for row in (result or []) if float(row[2]) >= 0.5)
