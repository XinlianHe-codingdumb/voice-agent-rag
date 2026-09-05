# Experiment and change log

This file records deliberate architecture changes and the evidence used to accept or reject them. Machine-generated run artifacts are stored under `reports/runs/<run_id>/`; `reports/experiment_history.csv` is the append-only metric index.

## Baseline implementation

- Source document: `HM_Treasury_ARA_25-26.pdf`.
- Document inspection: 300 PDF pages, 290 pages with usable text, 24 bookmarks.
- Chunking: page-local fixed windows of 220 words with 40-word overlap.
- Dense baseline: OpenAI embeddings with cosine similarity; no lexical retrieval, structure, query rewriting, reranking, or parent expansion.
- Gold set v0.1: 14 manually grounded retrieval questions, evenly split between dev and test. Tuning uses dev only.
- Reason for the baseline: establish the simplest credible reference before adding complexity.

## Change 001 - Immutable experiment traces

- Added timestamped run directories, `metrics.json`, full predictions, failures, configuration, environment versions, and a source-code fingerprint.
- Added `reports/experiment_history.csv` for cross-run comparison.
- `reports/latest/` remains a convenience copy and is never the sole record.
- Reason: the previous implementation overwrote `reports/latest`, which could not support an auditable comparison.

## Change 002 - Independent BM25 baseline

- Added a dependency-free BM25 implementation with `k1=1.5` and `b=0.75`.
- Uses exactly the same chunks, dev/test split, top-k, metrics, and report format as the dense baseline.
- Reason: distinguish lexical benchmark bias from genuine semantic retrieval gains before building hybrid RRF.

## Run 001 - BM25 on gold v0.1 dev split

- Run ID: `20260902T051706Z_baseline-bm25_dev`.
- Cases: 7; Top K: 5.
- Hit rate@5: 1.000.
- Mean Recall@5: 0.929.
- MRR: 0.857.
- Interpretation: exact evidence was found for every dev question, but relevant evidence was not always ranked first and one multi-page case retrieved only part of its gold evidence. The set is too small and lexically friendly to justify a quality claim.
- Decision: keep this as the lexical reference, inspect rankings, and strengthen the dev set before tuning.

## Change 003 - Test adapter repair

- The evaluation function now accepts a retriever callable so dense and BM25 use identical metric code.
- One unit test still attempted to monkeypatch the old module-level default. Python binds default arguments when a function is defined, so that mock was not used.
- Updated the test to pass its fake retriever explicitly. No production retrieval behavior or experiment result changed.

## Change 004 - Gold set v0.2 expansion

- Added 10 manually grounded dev questions, increasing dev from 7 to 17 cases while leaving the 7 held-out test cases unchanged.
- Added paraphrased KPI, policy-principle, fund-capitalisation, infrastructure, trade-finance, AI-training, incident-reporting, liability, budget-allocation, and entity-specific expenditure questions.
- Reason: Run 001 was too small and lexically friendly. A 1.000 Hit@5 on seven questions was not sufficient evidence of retrieval quality.

## Run 002 - BM25 on gold v0.2 dev split

- Run ID: `20260902T051900Z_baseline-bm25_dev`.
- Cases: 17; Top K: 5.
- Hit rate@5: 0.882.
- Mean Recall@5: 0.853.
- MRR: 0.824.
- Category weakness: hard-negative Hit@5 was 0.750; semantic Hit@5 was 0.857 and semantic Recall@5 was 0.786.
- Interpretation: the larger set exposed the expected lexical limitations. This is a more credible baseline than Run 001 and becomes the BM25 reference for dense/hybrid comparisons.
- Publication note: metric computation and the immutable run completed, but the first attempt to refresh `reports/latest` failed because Windows denied removal of the open directory.

## Change 005 - Windows-safe latest report publishing

- Replaced recursive deletion of `reports/latest` with overwrite-in-place copying.
- Reason: immutable runs are authoritative; deleting the convenience directory was unnecessary and failed when Windows held a directory handle.
- Retrieval logic, gold data, and Run 002 metrics were not changed.

## Change 006 - Exact report-boilerplate removal experiment

- Added a separate cleaned-BM25 pipeline; the original BM25 baseline and artifacts remain unchanged.
- Removes only the exact repeated annual-report header and six-item navigation strip before chunking.
- Evidence: Run 002 retrieved unrelated pages for the Group-liabilities question, while the repeated report chrome contributed common query terms across nearly every page.
- Acceptance rule: keep the change only if it improves the same 17-case dev metrics without introducing new failures.

## Run 003 - Cleaned BM25 on gold v0.2 dev split

- Run ID: `20260902T052142Z_cleaned-bm25_dev`.
- Cases: 17; Top K: 5.
- Hit rate@5: 0.882; Mean Recall@5: 0.853; MRR: 0.824.
- Result: exactly equal to Run 002.
- Decision: reject boilerplate removal as a quality improvement. It may remain a parser hygiene option, but it is not part of the evidence-backed retrieval upgrade.

## Runs 004-007 - BM25 chunk-size sweep

- `w120/o20`: Hit@5 0.882, Recall@5 0.882, MRR 0.794.
- `w160/o30`: Hit@5 0.882, Recall@5 0.882, MRR 0.765.
- `w220/o40`: Hit@5 0.882, Recall@5 0.853, MRR 0.824.
- `w300/o50`: Hit@5 0.882, Recall@5 0.853, MRR 0.784.
- Interpretation: smaller chunks recovered more of the two-page gold evidence but ranked the first relevant result lower. No configuration improved Hit@5; the original 220/40 configuration retained the best MRR.
- Decision: keep 220/40 as the baseline. Do not tune chunk size further on this small dev set; the next justified experiment is dense semantic retrieval.

## Environment fix 001 - Windows filename extension

- The user-created secret file was named `.env.txt`; Windows Explorer displayed it like `.env` because known extensions were hidden.
- Renamed it in place to `.env` without reading or printing the key and added `.env.txt` to `.gitignore` as an additional safeguard.
- No model call or retrieval result was affected before this fix; API-backed experiments begin after it.

## Run 008 - Dense baseline on gold v0.2 dev split

- Run ID: `20260902T063432Z_baseline-dense_dev`.
- Model: `text-embedding-3-large`; 678 vectors; 3,072 dimensions.
- Cases: 17; Top K: 5.
- Hit rate@5: 0.941; Mean Recall@5: 0.941; MRR: 0.776.
- Compared with BM25 Run 002: Hit and Recall improved, but MRR fell from 0.824 to 0.776.
- Failure pattern: dense recovered hard-negative evidence missed by BM25, but exact lexical and numeric evidence was often ranked second to fifth; it missed the Resource DEL 73%/27% case entirely.
- Decision: neither retriever dominates. Proceed to unweighted reciprocal rank fusion before changing chunking or adding reranking.

## Change 007 - Unweighted RRF hybrid

- BM25 and dense each retrieve 20 candidates over exactly the same 220/40 chunks.
- Fuse by `1 / (60 + rank)` and return the top five.
- No learned weights, query rewriting, or reranker are introduced in this experiment.
- Acceptance rule: improve MRR over both single retrievers while retaining dense Hit@5/Recall@5.

## Run 009 - Unweighted RRF hybrid on gold v0.2 dev split

- Run ID: `20260902T144322Z_hybrid-rrf_dev`.
- Cases: 17; Top K: 5; candidate depth: 20 per retriever; RRF constant: 60.
- Hit rate@5: 1.000; Mean Recall@5: 1.000; MRR: 0.828.
- Compared with BM25 Run 002: Hit improved from 0.882 to 1.000, Recall from 0.853 to 1.000, and MRR from 0.824 to 0.828.
- Compared with dense Run 008: Hit/Recall improved from 0.941 to 1.000 and MRR from 0.776 to 0.828.
- Category result: semantic MRR reached 0.905, while hard-negative MRR remained the weakest at 0.688.
- Decision: accept unweighted RRF as the retrieval candidate because it is the first pipeline to retrieve all gold evidence in the top five and it does not trade away first-rank quality. The small MRR gain over BM25 is not strong enough to call ranking solved; inspect the four rank-below-two cases before adding a reranker.

## Change 008 - Evidence-only LLM reranker

- Rerank the top 12 RRF candidates using the configured chat model, while preserving the original RRF ordering as a stable fallback for omitted IDs.
- Prompt explicitly prioritises exact entity, period, accounting scope, metric, and units; it receives only the question and candidate text and is forbidden from answering or using outside knowledge.
- Every raw model ranking, input candidate list, and parsed output list is saved in `rerank_traces.jsonl` inside the immutable run directory.
- Reason: Run 009 achieved complete top-five coverage, but five cases were below rank one and the weakest cases involved near-duplicate figures, adjacent tables, or accounting-scope ambiguity.
- Acceptance rule: retain Hit@5/Recall@5 of 1.000 and materially improve MRR over 0.828. Reject if it only rearranges easy cases or introduces new top-five failures.

## Run 010 - RRF plus LLM reranker on gold v0.2 dev split

- Run ID: `20260902T144927Z_hybrid-rrf-llm-reranker_dev`.
- Cases: 17; Top K: 5; reranked candidates: 12.
- Hit rate@5: 1.000; Mean Recall@5: 1.000; MRR: 0.971.
- All 17 model calls returned all 12 candidate IDs; raw output and parsed rankings are preserved in the run directory.
- Compared with RRF Run 009: coverage remained perfect and MRR improved from 0.828 to 0.971. Lexical, numeric, and semantic category MRR reached 1.000.
- Decision: accept the reranker. One remaining rank-two case exposed an ambiguous evaluation question rather than an unsupported ranking.

## Change 009 - Disambiguate the GGC emissions development question

- The original question asked for 2025-26 Scope 1 and Scope 2 emissions without naming the reporting table.
- Page 271 reports 14 and 700 tonnes CO2e under Greening Government Commitments; page 272 contains a different Core HM Treasury restated inventory with the same Scope labels. Both are plausible retrieval targets for the original wording.
- Added “In the Greening Government Commitments table” to the question and expanded the evidence note. The reference answer, gold page, split, and category are unchanged.
- Reason: a gold question must identify one supported target. This is a dev-set annotation repair, recorded before rerunning; the held-out test set remains untouched.

## Run 011 - Reranker replication after dev annotation repair

- Run ID: `20260902T145152Z_hybrid-rrf-llm-reranker_dev`.
- Hit rate@5: 1.000; Mean Recall@5: 1.000; MRR: 0.931.
- Compared with Run 010, MRR fell from 0.971 to 0.931 even though retrieval code and model configuration were unchanged apart from the clarified question text.
- Weak rankings: the GGC question remained rank two and the Departmental Group cash question moved from rank one to rank three.
- Interpretation: top-five retrieval is stable, but the generative reranker has measurable run-to-run ranking variance. Report the observed 0.931-0.971 dev range rather than selecting the best run.
- Decision: freeze the current RRF plus reranker pipeline. Do not tune further on 17 development cases; run the seven held-out test cases once, then move to answer-level evaluation.

## Run 012 - First frozen held-out retrieval test

- Run ID: `20260902T145350Z_hybrid-rrf-llm-reranker_test`.
- Cases: 7; Hit rate@5: 0.857; Mean Recall@5: 0.786; MRR: 0.671.
- The original score is preserved unchanged as the first held-out result.
- Error audit found one incomplete annotation: `lexical-004` ranked page 185 first, and that page explicitly states the correct date, but the gold listed only page 58.
- A genuine multi-hop miss remained: `cross-section-002` retrieved page 165 but ranked page 58 sixth, so only one of two required sections entered the top five.
- Decision: do not treat the raw aggregate as a pure model-quality estimate. Repair the evaluation schema for alternative evidence, preserve this run, and develop multi-query retrieval on new development examples rather than tuning directly on these test labels.

## Change 010 - Alternative evidence-set semantics

- Added optional `gold_evidence_sets`, where each inner list is a complete required evidence set and different inner lists are valid alternatives.
- Recall is the maximum complete-set recall across alternatives; MRR still uses the first page belonging to any valid evidence set.
- Updated `lexical-004` to represent `[58]` and `[185]` as alternative single-page evidence sets. This is a post-test annotation audit, not a new held-out result.
- Multi-page questions such as `[58, 165]` retain their existing semantics: both pages are required.

## Change 011 - Explicit multi-query retrieval experiment

- Added two development-only cross-section questions using already verified dev evidence, increasing dev from 17 to 19 without copying held-out questions or pages.
- Questions containing explicit coordinated interrogatives such as “..., and which ...?” are split deterministically; no model invents subqueries.
- Each clause independently runs dense + BM25 RRF and LLM reranking. Final results are interleaved round-robin with duplicate chunks removed so one clause cannot consume all five evidence slots.
- Reason: the first held-out run showed a genuine partial-recall failure on a two-section question even though both pages were in the 12-candidate pool.
- Acceptance rule: both new dev cross-section cases must achieve full Recall@5 without materially lowering the existing single-hop aggregate.

## Run 013 - Clause-only multi-query development evaluation

- Run ID: `20260902T150113Z_multi-query-rrf-llm-reranker_dev`.
- Cases: 19; Hit rate@5: 1.000; Mean Recall@5: 1.000; MRR: 0.904.
- Both new cross-section cases achieved full Recall@5 and cross-section MRR 1.000.
- Regression: three single-page questions containing coordinated wording fell to ranks two or three because isolated clauses lost entity or table context.
- Decision: multi-query coverage works, but clause-only ranking is rejected. Preserve the complete-question ranking as the first merge stream and use clauses only to add coverage.

## Change 012 - Context-preserving multi-query merge

- For decomposed questions, retrieve and rerank the complete question as well as each clause.
- Round-robin order starts with the complete-question ranking, followed by clause rankings; duplicates are removed.
- Acceptance rule: retain 1.000 cross-section Recall@5 while recovering single-page first-rank quality relative to Run 013.

## Run 014 - Context-preserving multi-query development evaluation

- Run ID: `20260902T150314Z_multi-query-rrf-llm-reranker_dev`.
- Cases: 19; Hit rate@5: 1.000; Mean Recall@5: 1.000; MRR: 0.912.
- Both cross-section cases retained full evidence recall. Full-question-first merging improved MRR slightly from 0.904 to 0.912, but did not recover the earlier single-query reranker range of 0.931-0.971.
- Decision: accept the merge for multi-hop evidence coverage, not as an MRR improvement. Keep the measured reranker variance visible and move to answer-level quality rather than further tuning this small dataset.

## Change 013 - Reusable hybrid RAG pipeline

- Extracted loading, dense/BM25 retrieval, RRF, reranking, multi-query merging, context labelling, and answer generation into `HybridRAGPipeline`.
- Reason: evaluation scripts and the later web/voice backend must execute the same production path; duplicated script-only logic would make the reported metrics non-representative.

## Change 014 - Answer-quality evaluation harness

- Added eight answerable cases spanning lexical, numeric, semantic, hard-negative, and cross-section behavior, plus two deliberately unanswerable questions.
- Production answers must cite retrieved `[PDF page N]` labels. Citation validity is checked deterministically against retrieved pages.
- A strict model judge scores correctness and faithfulness on a 0/1/2 rubric; raw judgments, reasons, answers, contexts, retrieval traces, and environment fingerprints are preserved.
- Limitation declared in every report: the configured chat model also acts as judge, so aggregate scores require inspection and later human spot-checking.

## Run 015 - First answer-quality development evaluation

- Run ID: `20260902T150845Z_answer-quality-multi-query-rag_dev`.
- Cases: 10: eight answerable and two unanswerable.
- Normalized correctness: 1.000; faithfulness: 1.000; citation validity: 1.000; unanswerable handling: 1.000.
- Manual audit confirmed that both cross-section answers cited both required pages, entity-specific numeric answers used the correct values, and both unsupported questions returned the exact refusal sentence.
- Limitation: the set is small and the same configured chat model generated and judged answers. Treat this as an MVP regression suite, not an independent human evaluation or proof of general accuracy.

## Change 015 - Post-hoc audited test wrapper

- Added a clearly labelled wrapper that applies the corrected alternative-evidence schema and context-preserving multi-query pipeline to the already inspected test cases.
- This run is for regression diagnosis only and will not be described as a fresh held-out result. Run 012 remains the first and only untouched held-out score.

## Run 016 - Post-hoc audited retrieval test

- Run ID: `20260902T151028Z_multi-query-rrf-llm-reranker_test`.
- Hit rate@5: 1.000; Mean Recall@5: 0.857; MRR: 0.833.
- Alternative evidence fixed the false lexical miss. Both cross-section cases still retrieved only one of two labelled pages in the top five; one retrieved page 65 rather than labelled page 63 for the five-year expenditure analysis, indicating remaining page-granularity annotation uncertainty.
- Decision: do not switch documents yet and do not tune further on the inspected test. Preserve the result, add section metadata later, and proceed with production integration because single-hop answers, citations, and refusals are already passing the answer regression suite.

## Change 016 - Runnable text RAG web backend

- Added a FastAPI backend with health, question-answering, and PDF-upload endpoints.
- Uploaded PDFs are validated, capped at 50 MB, stored by SHA-256, and indexed into separate cached artifact directories before atomically becoming active.
- Added a responsive browser UI showing the active document, answer, expandable retrieved evidence, and end-to-end latency.
- Generalised the answer prompt from HM Treasury-specific wording to arbitrary supplied documents.

## Run 017 - Backend end-to-end smoke test

- FastAPI health endpoint returned HTTP 200 with the expected active document and 678 chunks.
- Browser root returned HTTP 200 and the expected application title.
- A real `/api/ask` request returned the correct £23.6 billion answer with `[PDF page 22]`, five source records, and 4,163 ms measured end-to-end latency.
- The first server start could not reach the API because it ran under restricted network policy and returned HTTP 502; restarting the same build with approved API network access succeeded. Both observations are recorded in `reports/backend_smoke.md`.

## Change 017 - Browser voice round trip

- Added microphone capture with the browser `MediaRecorder` API and a single `/api/voice` endpoint.
- The endpoint runs ASR, the exact same evaluated hybrid RAG pipeline, and TTS; it returns the transcript, cited text answer, sources, playable MP3, query parts, and separate ASR/RAG/TTS/total timings.
- Visual citation syntax is removed only from the spoken string; the browser answer retains page citations.
- Defaults are configurable in `.env`: `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`, and voice `alloy`.

## Run 018 - Synthetic clean ASR-RAG-TTS smoke test

- Run ID: `20260902T152300Z_voice-smoke_synthetic-clean`.
- WER: 0.000; critical entity accuracy: 1.000.
- ASR: 2,033 ms; RAG: 4,602 ms; answer TTS: 2,168 ms; non-streaming voice round trip: 8,803 ms.
- Saved `question.mp3`, `answer.mp3`, transcript, answer, retrieved pages, model configuration, environment fingerprint, and traces in the immutable run directory.
- Limitation: the input was generated by TTS in clean conditions. It validates integration but is optimistic relative to a real microphone, accents, room noise, and interruptions.

## Run 019 - Browser-facing voice endpoint smoke test

- Posted the saved question MP3 to `/api/voice` as multipart audio.
- The endpoint returned the correct transcript and £23.6 billion answer with page 22 evidence plus a valid approximately 185 KB MP3 payload.
- ASR: 2,946 ms; RAG: 3,051 ms; TTS: 3,337 ms; total: 9,335 ms.
- Decision: the voice round trip is functionally complete for MVP demonstration. Latency is too high to call conversational; streaming output and real-microphone evaluation remain required improvements.

## Change 018 - Functional MVP corrections from browser testing

- Removed the 50 MB PDF application limit and replaced whole-file memory reads with 1 MB streaming writes, incremental SHA-256 hashing, exact temporary-file cleanup, and cached indexing by document hash.
- Added a persistent document catalog. Multiple PDFs remain loaded simultaneously and each query retrieves per document before a cross-document rerank; sources now include document name and PDF page.
- Added process-local, browser-session-isolated conversation memory with a 12-message window, standalone follow-up query rewriting, and conversation-only handling for questions such as “What did I just ask?”.
- Typed `/api/ask` responses now synthesize and return MP3 audio, matching the voice endpoint; the browser automatically plays both paths.
- Browser recording now selects a supported MediaRecorder MIME type, emits chunks every 250 ms, preserves the actual content type and filename extension, rejects sub-second/empty recordings, and passes MIME metadata to the transcription API.
- Added a visible circular upload indicator: determinate during byte upload and indeterminate while PDF extraction/embedding/indexing runs.

## Run 020 - Multi-document, memory, TTS, and voice regression smoke

- Uploaded `AI Builder Intern - Take Home Accessment.pdf` through the API: 2 pages, 3 chunks, 234,565 bytes. The running corpus then contained two documents and 681 chunks.
- A typed question about the take-home assessment cited that document’s page 1 and returned an approximately 221 KB MP3.
- In the same session, “What did I just ask you?” accurately reproduced the prior question, returned no fabricated document sources, retained four memory messages, and returned an approximately 114 KB MP3.
- A saved spoken question transcribed exactly, retrieved the correct HM Treasury page across both documents, answered with document/page citation, and returned an approximately 153 KB MP3. Timings: ASR 1,025 ms; RAG 5,478 ms; TTS 1,761 ms; total 8,265 ms.
- After a server restart, the health endpoint restored both documents from the persistent catalog. Browser root returned HTTP 200 and contained the multiple-file input and circular progress component.
- Limitation: API audio was verified with MP3. The corrected browser WebM/Opus capture path still requires one real microphone retest by the user because the automated environment has no microphone source.

## Change 019 - Browser microphone recognition hardening

- Root cause from the browser screenshot: low-signal or silent audio caused the transcription model to echo the optional ASR prompt verbatim, and that synthetic text was then treated as the user's question.
- Removed the ASR prompt entirely and upgraded the default from `gpt-4o-mini-transcribe` to `gpt-4o-transcribe` with deterministic temperature zero.
- Added explicit microphone selection, echo cancellation, noise suppression, automatic gain control, mono capture, 128 kbps recording, and a live RMS input-level display in the browser.
- Added browser and API guards for recordings shorter than 900 ms or with peak RMS below 0.005. Silent input is now rejected before it can consume ASR/RAG/TTS calls.
- Added server-side rejection of the exact historical prompt-echo pattern so it cannot enter retrieval even if returned by a stale client or provider response.

## Run 021 - Corrected microphone-chain regression

- Run ID: `20260903T092909Z_voice-smoke_synthetic-clean`.
- The upgraded ASR transcribed the fixed spoken question exactly: WER 0.000 and critical entity accuracy 1.000. ASR/RAG/TTS timings were 1,132/3,886/2,086 ms.
- The browser-facing `/api/voice` path accepted a valid-signal multipart request with HTTP 200, returned the exact transcript, cited the £23.6 billion answer, and produced approximately 150 KB of MP3 audio. Total measured latency was 11,608 ms.
- The same endpoint rejected an otherwise valid audio file tagged with zero peak signal with HTTP 400 before ASR, confirming the silence gate.
- Automated suite: 23 passed. Remaining manual check: select the physical microphone and confirm that its live percentage moves in the real Chrome/Windows environment.

## Change 020 - Persistent multi-conversation document Agent

- Replaced process-local memory with SQLite-backed conversations, messages, and per-conversation document bindings. Existing indexed PDFs are reusable library items rather than implicitly active in every new conversation.
- Added a bounded tool-calling harness for indirect requests such as learning plans, recommendations, comparisons, and summaries. Its only tools list selected documents and search their indexed content; simple factual questions remain on the frozen evaluated RAG path.
- Fixed a routing defect found during smoke testing: a repeated complex prompt was incorrectly classified as conversation-only by query rewriting. Complex Agent intent now takes precedence while explicit history questions still use memory.

## Change 021 - Realtime streaming voice and barge-in

- Added a backend-only OpenAI Realtime WebRTC handshake, keeping the standard API key out of the browser.
- Added browser WebRTC audio, semantic VAD, streaming output, document-search function calls, and interruption of an active response when the user starts speaking.
- Realtime reconnection receives up to eight recent persisted messages; turns during the connected call remain in the native Realtime conversation and completed transcripts are saved back to SQLite.
- Kept push-to-talk ASR and complete-file TTS as a fallback. The full Realtime microphone/speaker path still requires a human browser acceptance test.

## Change 022 - Low-latency Agent tool retrieval

- Added a dense + BM25 + RRF path that omits LLM reranking only for Agent tool calls and Realtime voice searches. The formally evaluated direct factual RAG pipeline is unchanged.
- Reason: the first indirect-question smoke made two Agent searches; reranking each search contributed avoidable model round trips before final generation.

## Run 022 - Agent latency before/after smoke

- Same prompt and one selected document (`AI Agent Book.pdf`) in fresh conversations.
- Before: two document-search calls; Agent/RAG 16,633 ms; complete-file TTS 19,292 ms; total 35,935 ms.
- After: one document-search call; Agent/RAG 4,989 ms; complete-file TTS 8,807 ms; total 13,799 ms.
- Observed reductions: Agent/RAG 70.0%; total 61.6%. This is a one-run smoke comparison, not a stable benchmark; model decisions and answer length vary.
- The optimized answer cited book pages 30, 505, and 25 for fundamentals, LLM systems/tool use, and practical deployment skills. Raw result and full answer are preserved in `reports/runs/20260903T154704Z_agent-fast-hybrid_smoke`.

## Run 023 - Realtime proxy contract smoke

- A request reached the OpenAI Realtime calls endpoint using the configured model, session, and backend-held API key.
- A deliberately minimal SDP was rejected with HTTP 400 `invalid_offer` and the precise reason `Offer did not have an audio media section`; the local backend correctly surfaced this as 502.
- Interpretation: authentication, endpoint reachability, multipart transport, and session parsing passed far enough for SDP media validation. A real browser-generated audio offer and barge-in remain a manual acceptance check.

## Run 024 - User Realtime acceptance and false-interrupt finding

- The user manually confirmed that Live Call supported continuous conversation and stopped audible output when interrupted.
- The user also observed that acknowledgements such as `OK` and `好啊` triggered the same interruption as a substantive new question. Text could continue after audible output stopped.
- Diagnosis: server-side `interrupt_response=true` reacts to speech onset before the completed ASR transcript is available, so it cannot distinguish a backchannel from a real barge-in.

## Change 023 - Acknowledgement-aware application turn policy

- Retained OpenAI `semantic_vad` for speech boundary detection but set `create_response=false` and `interrupt_response=false`.
- Added a deterministic browser classifier with four outcomes: noise, backchannel, hard interruption, and new turn. Exact short acknowledgements restore output instead of creating a response; corrections and substantive turns cancel active output and create a new response.
- Duck Agent audio to 35% only while an overlapping utterance is being transcribed. This creates a short decision window without another model call.
- Added stale-tool protection: a newer substantive turn aborts the active document-search HTTP request; the outstanding function call receives a cancellation result before generation resumes.

## Change 024 - Explicit cross-conversation long-term memory

- Added an independent SQLite table for durable memories with category, content, source conversation, timestamps, and deterministic deduplication key.
- Only explicit statements such as `Remember that...`, `My goal is...`, `I prefer...`, and Chinese equivalents are captured. Ordinary questions are not silently summarized or memorized by an LLM.
- Long-term memory is shared across conversations and backend restarts, and is injected into direct answers, the bounded document Agent, and new Realtime sessions as personal context rather than document evidence.
- Added visible memory listing and per-item/all-memory deletion controls. A new explicit primary goal replaces the previous goal; separate preferences can coexist.

## Run 025 - Turn-policy and long-term-memory regression

- Run ID: `20260904T034505Z_turn-memory_regression`.
- Python suite: 34 passed in 8.11 seconds. Browser policy suite: 3 passed.
- Cross-conversation integration: a synthetic goal written from conversation A was returned from conversation B with `agent_mode=long-term-memory`.
- The synthetic memory and both synthetic conversations were deleted after verification; zero test memories remained.
- Remaining manual check: with the physical microphone, speak `OK啊` or `好啊` over a long response and verify that volume briefly ducks then resumes; then speak `等等，不对` and verify a true cancellation.

## Change 025 - Frontend/backend cache-coherency recovery

- Root cause: the browser fetched the updated HTML and `realtime_turns.js` but reused a cached older `app.js`. The updated Realtime session deliberately has `create_response=false`, so the absent client-side `response.create` left a completed transcript at `Thinking…`. The older script also did not reliably initialize the new long-term-memory panel.
- Added a release query version to all CSS and JavaScript asset URLs and `Cache-Control: no-store, max-age=0` plus `Pragma: no-cache` on `/` and `/static/*` responses.
- Added a ten-second Realtime response-start watchdog and explicit errors for a disconnected data channel or mismatched turn-policy script, replacing indefinite `Thinking…`.
- Memory loading now bypasses browser cache and renders the actual error instead of leaving `Loading memory…` forever.

## Run 026 - Frontend cache recovery regression

- Run ID: `20260904T040139Z_frontend-cache-recovery`.
- Python suite: 36 passed in 8.43 seconds. Browser turn-policy suite: 3 passed.
- JavaScript syntax checks passed for `app.js` and `realtime_turns.js`.
- Live HTTP checks: `/` and the versioned `app.js` returned HTTP 200 with `Cache-Control: no-store, max-age=0`; HTML referenced release `20260904.3`; served JavaScript contained both manual Realtime response creation and the memory endpoint; `/api/memories` returned HTTP 200 with an empty memory list.
- The backend is running at `http://127.0.0.1:8000`. A physical-microphone Live Call remains a manual acceptance test because the automated environment cannot supply the user's microphone stream.

## Run 027 - Mic document-retrieval diagnostic

- Run ID: `20260904T041400Z_mic-document-diagnostic`.
- Investigated the apparent disagreement between push-to-talk Mic and Live Call for `Can you hear me?`. Server logs showed both session paths succeeded with HTTP 200, and Live Call separately completed document-search tool calls.
- The active conversation `313c419ab4ba450b92a01dc3f5bc092a` had two attached documents: `AI Agent Book.pdf` and `medical-examination-report.pdf`; `HM_Treasury_ARA_25-26.pdf` was present in the library but not attached to that conversation.
- A clean saved speech sample was sent through the current browser-equivalent `/api/voice` endpoint in a disposable conversation with HM Treasury attached. ASR reproduced the question exactly, `agent_mode=fast-rag` retrieved HM Treasury pages 22, 22, 7, 6, and 10, and the answer correctly reported £23.6 billion with a page-22 citation.
- Measured stages: ASR 2,165 ms; RAG 3,656 ms; TTS 1,847 ms; total 7,669 ms. The disposable conversation was deleted.
- Conclusion: Mic document retrieval is operational. The screenshot is an intent-routing inconsistency: push-to-talk treats `Can you hear me?` as a grounded document query and refuses for lack of evidence, while the Realtime model treats it as conversation. No code was changed in this diagnostic run.

## Change 026 - Unified intent router across text, Mic, and Live Call

- Added one auditable Python router with four outcomes: `conversation`, `document_fact`, `document_task`, and `memory`. Memory commands are detected first, exact conversational/control phrases second, indirect document-task markers third, and remaining requests default to grounded document facts.
- Typed input and push-to-talk Mic now route through the same decision inside `_answer`. Conversation turns bypass document availability and retrieval; document tasks use the bounded tool harness; document facts retain the evaluated hybrid RAG path.
- Added a dedicated conversational responder because integration testing found that merely labeling a turn `conversation` still passed it to the old document-only prompt and caused a false refusal.
- Added `/api/intent` for Live Call. After Realtime transcription, the browser requests the same Python decision: conversational and memory turns disable tools, while document turns require `search_documents` before an answer. Realtime document tool work is bounded to three searches per user turn.
- Updated frontend asset release to `20260904.4` so the browser cannot reuse the pre-router script.

## Run 028 - Unified intent and cross-modality regression

- Run ID: `20260904T102827Z_unified-intent-router`.
- Full automated suite: 48 Python tests passed in 8.13 seconds; 3 browser turn-policy tests passed. JavaScript syntax and Python compilation checks also passed.
- Router contract passed in English and Chinese for all four classes. `Can you hear me?` returned `conversation`; a DPO location question returned `document_fact`; an AI-job learning-plan request returned `document_task`; and a memory query returned `memory`.
- Disposable-conversation integration without attached documents: `Can you hear me?` returned `Yes — I can receive your messages.`, `agent_mode=conversation`, and zero document sources.
- In the same disposable conversation after attaching HM Treasury, the saved Mic audio transcribed exactly and routed as `document_fact`; hybrid RAG cited HM Treasury PDF page 22 and correctly answered £23.6 billion. Timings: ASR 1,992 ms; RAG 8,097 ms; TTS 2,012 ms; total 12,103 ms.
- The disposable conversation was deleted. Backend remains running at `http://127.0.0.1:8000`. Physical-microphone Live Call remains the final manual acceptance check for the new response-level tool policy.

## Change 027 - Explicit speech language and consent-based document discovery (2026-09-05)

- Diagnosis: neither file ASR nor Realtime transcription previously supplied a language. Automatic language identification is a plausible contributor to the reported wrong-language transcripts, but the original microphone audio was not available; no definitive acoustic diagnosis is claimed.
- Added one persisted browser speaking-language selector: English (default), Chinese, automatic/mixed. Both file transcription and Realtime session creation now pass the chosen language; auto omits the hint. Changing language ends the current call and asks the user to reconnect. English sessions default spoken replies to English unless explicitly asked otherwise.
- Added a shared pre-answer consent gate for text, Mic and Realtime. Candidate discovery checks explicit file names or compares the query embedding with existing local chunk vectors. It sends no unselected excerpts to generation. A suggestion contains only the filename and says “may contain relevant information”.
- Semantic discovery currently requires cosine similarity >= 0.35 and a >= 0.04 margin over the best selected document. These are conservative heuristics, not calibrated probabilities or exhaustive discovery guarantees. One document is proposed at a time; each discovery request can add one query-embedding call.
- Pending proposals persist in SQLite for 10 minutes, keyed by conversation. Exact confirmation attaches the proposed document and resumes the saved original question; refusal does not attach; an unrelated new question invalidates the proposal. Browser document checkboxes refresh after consent.
- Live Call confirmations bypass the usual short-acknowledgement filter while consent is pending. Response instructions carry the original question after approval; stale tool completion cannot generate a reply while a newer intent is still resolving. Ending a call invalidates outstanding frontend epochs.
- Frontend assets bumped to 20260905.1. Tests and the reusable scripts/verify_document_access.py preserve the workflow for later replays.

## Run 029 - Speech-language and document-access regression

- Python: 53 passed in 9.30 s. Existing Node policy tests: 3 passed. Added browser event replay: 1 passed, verifying Live Call “yes” reaches the shared gate and creates a required document-tool response with the saved original question. Targeted Python language/Realtime tests were rerun after the final prompt adjustment: 8 passed.
- First integration attempt: reports/runs/20260905T021605Z_document-access-language/result.json preserves a failure caused by the old backend still owning port 8000. Its OpenAPI schema lacked the new conversation_id field. The old process was stopped and the new service started; no result was silently overwritten.
- Successful integration: reports/runs/20260905T021800Z_document-access-language/result.json. From an empty selection, both typed and Realtime-routing endpoints suggested HM Treasury, kept it unselected before approval, then attached it after “yes please”. Typed continuation answered £23.6 billion with a page-22 citation. Realtime routing returned the original question and required document search.
- English MP3 replay through /api/voice transcribed the question exactly and answered correctly: ASR 1,158 ms, RAG 4,249 ms, TTS 3,891 ms, total 9,299 ms. This is synthetic clean speech, not a noisy physical-microphone benchmark.
- All disposable integration conversations were deleted. No user documents or conversations were removed. Real WebRTC audio and noisy English microphone acceptance remain manual checks.

## Change 028 - Natural consent, sidebar deletion and scanned PDF OCR (2026-09-05)

- Fixed exact-match consent bug reproduced by both screenshot phrases. Negation takes precedence, conditional statements remain unapproved, and selecting for a later question returns an application-generated truthful confirmation. Immediate consent resumes the original question and prevents its rewrite from becoming CONVERSATION_ONLY.
- Added Delete chat and Remove file controls with confirmation, selection refresh and active-call shutdown. Conversation deletion includes default; a persisted initialization marker prevents startup reimport. File removal clears every conversation association and pending grant, stores a SQLite tombstone, retains source/index for re-upload recovery. Independent provider fallback handles an empty library.
- Added CPU RapidOCR 1.4.4 + pypdfium2 4.30; removed rejection of scanned PDFs. Text-first extraction uses OCR below 80 native characters, caps render dimension at 3200, serializes PDFium/engine, closes resources, and preserves page numbers. New extraction.json files record per-page provenance. Existing cached indexes are intentionally not rebuilt.
- Added Python regression tests, natural-phrase browser replay and delete-control tests, plus scripts/verify_consent_delete_ocr.py. README and reports/CONSENT_DELETE_OCR.md explain recovery and OCR limitations.

## Run 030 - Consent/delete/OCR verification and failure history

- Initial dependency download was blocked by sandbox networking; authorized installation succeeded. First Python run: 63 passed, 1 failed (PDFium context manager unsupported); corrected explicit cleanup. Second: 63 passed, 1 failed (ORION -> ORlON OCR substitution); retained exact amount checks and recorded a <5% character substitution acceptance threshold, not a fabricated perfect transcription.
- reports/runs/20260905T025806Z_consent-delete-ocr records 46 passed / 18 test setup errors caused by shared pytest temporary-directory permissions. The replay now creates an isolated per-run test directory.
- reports/runs/20260905T025905Z_consent-delete-ocr records 64 Python tests passing and successful real-backend regression. Both screenshot confirmations attach the book while preserving Treasury. Immediate approval and follow-up answers cite AI Agent Book pages 16/290. Real image-only PDF upload creates a searchable chunk and answers 4729 dollars with page-1 evidence. Synthetic file removal and temporary conversation deletion succeeded.
- Final browser replay after expanding coverage: 7 tests passed, including both full phrases and both deletion endpoints. Final full-suite output is recorded separately below. No real microphone/WebRTC claim; no user document/chat deletion.
- Final verification: reports/runs/20260905T030318Z_consent-delete-ocr-final/result.json. Python 64 passed in 14.50 s; Node 7 passed; JavaScript syntax, Python compilation and pip dependency compatibility passed. Includes the final OCR provenance and in-flight deletion guard changes.

## Change 029 - Final visual refinements (2026-09-05)

- Renamed the top-left product label to “Voice Agent”.
- Increased the selected Evidence card outline from 1 px to 2 px green while preserving its size with matching padding adjustment, making a clicked citation visibly easier to locate.

## Change 030 - Automatic per-chat long-term summaries (2026-09-05)

- Reframed the Memory workspace as Chat summaries. A conversation generates one durable summary after its 11th user turn; the summary is linked to that source conversation and can be opened, edited, or deleted from the Memory workspace.
- Added full but bounded (80-message) transcript retrieval for summarization. Normal agent turns still use the existing recent-history limit; this avoids increasing the prompt size or latency of normal RAG responses.
- The summary has a stable `conversation-summary:<conversation_id>` key. Repeated turns cannot create duplicate summaries. Explicit “remember” facts remain supported as optional user preferences and are visibly labeled as Saved detail.
- Summary generation uses the configured chat model once at the threshold and is limited to 4-7 concise bullets / 180 words. It is intentionally not recalculated on every later turn, so the feature adds no ongoing response latency after its first summary.
- If that one summarization call is temporarily unavailable, it never fails the user’s completed answer or Live Call turn. No empty record is written; a later turn can retry safely.
