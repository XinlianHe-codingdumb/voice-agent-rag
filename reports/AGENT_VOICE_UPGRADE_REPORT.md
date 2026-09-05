# Multi-conversation Agent and Realtime voice upgrade

## Implemented

- Persistent SQLite conversations, messages, and per-conversation document selections in `runtime/conversations.sqlite3`.
- Separate browser conversations. Previously indexed documents form a library; each conversation independently selects which documents its Agent can search.
- A bounded document Agent with `list_documents` and `search_documents` tools. Direct factual questions stay on the evaluated RAG path; recommendations, learning plans, summaries, and comparisons enter the tool Agent.
- A low-latency Agent search path using dense retrieval + BM25 + RRF without invoking an LLM reranker on every tool call.
- Browser WebRTC Realtime calls with semantic VAD, streamed speech-to-speech output, document-search tool calls, and interruption while the Agent is speaking.
- Recent persistent conversation history is injected when a Realtime call reconnects. Turns within one call also remain in the Realtime conversation.
- Push-to-talk ASR/TTS remains available as a fallback.

## Verification

- Automated suite: 29 tests passed after the upgrade.
- JavaScript syntax and Python bytecode compilation passed.
- SQLite persistence was checked after a backend restart: the earlier Agent smoke conversation retained two messages and its one selected document.
- The Realtime server handshake reached OpenAI and accepted authentication/session configuration. A deliberately incomplete test SDP was rejected specifically because it contained no audio media section, which is expected.
- The same indirect job-learning prompt was executed against `AI Agent Book.pdf` before and after the fast Agent tool path. Agent/RAG fell from 16,633 ms to 4,989 ms; total non-streaming response including MP3 fell from 35,935 ms to 13,799 ms. See the immutable run folder `reports/runs/20260903T154704Z_agent-fast-hybrid_smoke`.

## Remaining manual acceptance check

Automated execution cannot prove real speaker/microphone behavior. In Chrome, select the previously confirmed physical input (`Default - Microphone (Realtek(R) Audio)`), click **Start live call**, ask a document-dependent question, and then speak over the Agent while it is answering. Acceptance requires streamed audible output, a visible document-search status, grounded citations in the transcript, and successful barge-in.

## Harness boundaries

This is not an unbounded ReAct loop. The text Agent is intentionally capped at three model/tool rounds and exposes no chain-of-thought. Realtime uses the model's native conversation loop but only one application tool, `search_documents`. This keeps the take-home auditable and limits accidental actions: the Agent can read selected documents, but cannot write files, browse the web, or call external business systems.
