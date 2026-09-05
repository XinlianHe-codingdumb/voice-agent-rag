# Backend smoke test

- Date: 2026-09-02 (Asia/Singapore)
- Command: `python 14_run_backend.py`
- Health endpoint: HTTP 200; active document `HM_Treasury_ARA_25-26.pdf`; 678 chunks.
- Browser root: HTTP 200; title `Document Voice RAG`.
- Question endpoint: HTTP 200 after starting the server with API network access.
- Test question: stability-rule headroom in the OBR March 2026 forecast.
- Result: `£23.6 billion in 2029-30` with `[PDF page 22]`.
- Returned sources: 5.
- Measured end-to-end latency: 4,163 ms.

The first sandboxed server start intentionally recorded a `502 Connection error` because outbound API access was blocked. The same code succeeded when the server was restarted with approved network access; this distinguishes environment policy from an application defect.
