# Voice endpoint smoke test

- Date: 2026-09-02 (Asia/Singapore)
- Endpoint: `POST /api/voice`
- Input: synthetic clean `question.mp3` from run `20260902T152300Z_voice-smoke_synthetic-clean`.
- Transcript: exact semantic match to the reference question.
- Answer: £23.6 billion in 2029-30 with PDF page 22 citation.
- Retrieved pages: 22, 7, 6, 22, 22.
- Returned MP3 payload: approximately 185,088 bytes.
- ASR: 2,946 ms.
- RAG: 3,051 ms.
- TTS: 3,337 ms.
- Total non-streaming endpoint latency: 9,335 ms.

This validates the browser-facing multipart endpoint and audio response path. It uses clean synthetic speech and does not replace real-microphone WER or qualitative TTS testing.
