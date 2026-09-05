# Docker deployment (2026-09-05)

- Added Dockerfile, Compose and an allowlist-based .dockerignore. API keys, databases, user uploads and local indexes never enter the build context.
- Runtime and artifacts directories use separate named volumes. Container listens on 0.0.0.0 internally; host port is bound only to loopback.
- Fixed fresh startup: register the bundled baseline only if its index exists. Fresh installations open an empty library and use the existing upload/indexing workflow.
- README now starts with Docker instructions applicable to Windows/macOS/Linux; local Python setup is optional.
- Local machine has no Docker executable. GitHub Actions builds the Linux image and checks HTTP startup, OCR initialization and conversation survival across container recreation. Check its result for validation status.
- These checks use no real API key and do not validate paid ASR, RAG or Realtime connectivity. Existing application behaviour is reused.
