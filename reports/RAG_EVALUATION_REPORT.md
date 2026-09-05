# RAG Evaluation and Latency Report

**Project:** Multi-document Voice RAG for the Wiz AI Builder Intern take-home  
**Evaluation document:** `HM_Treasury_ARA_25-26.pdf`  
**Evaluation period:** 2-3 September 2026  
**Primary production pipeline:** BM25 + dense retrieval + reciprocal rank fusion (RRF) + LLM reranking + conditional multi-query retrieval  

## 1. Executive summary

The evaluation was designed to measure retrieval separately from answer generation. The system was not declared successful merely because an answer sounded plausible: retrieval was scored against manually verified PDF pages, and generated answers were checked for correctness, faithfulness, valid citations, and appropriate refusal of unsupported questions.

The strongest development retrieval result used hybrid RRF followed by an evidence-only LLM reranker. It achieved Hit Rate@5 and Mean Recall@5 of 1.000, with MRR varying between 0.931 and 0.971 across repeated runs. The accepted context-preserving multi-query pipeline achieved 1.000 Hit Rate@5, 1.000 Mean Recall@5, and 0.912 MRR on 19 development questions while retaining all evidence for the two-section questions.

The first and only untouched seven-question held-out run was weaker: Hit Rate@5 0.857, Mean Recall@5 0.786, and MRR 0.671. Audit found that one failure was caused by an incomplete gold annotation because a second PDF page independently contained the correct evidence. After correcting the evaluation schema and applying multi-query retrieval, the post-hoc diagnostic score was Hit Rate@5 1.000, Mean Recall@5 0.857, and MRR 0.833. This later result is useful for diagnosis but is **not presented as a fresh held-out score**.

Answer-level evaluation used ten questions: eight answerable and two deliberately unanswerable. Correctness, faithfulness, citation validity, and unanswerable handling were all 1.000. These results form a useful MVP regression suite, but the dataset is small and the configured generation model was also used as the judge.

## 2. Evaluation data

### 2.1 Source document

- 300 PDF pages.
- 290 pages contained extractable text.
- 24 PDF bookmarks.
- The accepted 220-word/40-word-overlap configuration produced 678 chunks.
- Dense index: 678 vectors with 3,072 dimensions using `text-embedding-3-large`.

The HM Treasury annual report was selected because it contains names, dates, currencies, percentages, similar financial tables, repeated accounting terminology, and facts distributed across distant sections. It therefore supports lexical, semantic, numeric, hard-negative, and multi-section retrieval tests.

### 2.2 Retrieval dataset

The final retrieval dataset contains 26 manually grounded questions:

- 19 development questions used for analysis and iteration.
- 7 test questions frozen before the first test run.
- Categories: lexical, numeric, semantic, hard-negative, and cross-section.
- Every case contains a reference answer and one or more manually verified PDF pages.
- Alternative evidence sets are supported when different pages independently provide a complete answer.

The dataset evolved from an initial 14-question version. Ten development questions were added after the first BM25 result proved too easy, and two further development-only cross-section questions were added after the first held-out run exposed a genuine multi-hop coverage weakness. Held-out questions were not copied into development data.

### 2.3 Answer dataset

The answer-quality dataset contains:

- 8 answerable questions spanning all major retrieval categories.
- 2 unanswerable questions whose requested facts do not occur in the report.
- Reference answers for correctness evaluation.
- Deterministic checks that every cited page was included in retrieved evidence.

## 3. Metrics

- **Hit Rate@5:** proportion of questions for which at least one valid evidence page appears in the first five results.
- **Mean Recall@5:** average fraction of all required evidence pages retrieved in the first five. This distinguishes partial from complete multi-section retrieval.
- **MRR:** mean reciprocal rank of the first valid evidence result. A value of 1.000 means the first result was relevant for every question.
- **Answer correctness:** model-judged 0/1/2 score normalized to 0-1 against the reference answer.
- **Faithfulness:** model-judged 0/1/2 score normalized to 0-1, measuring whether answer claims are supported by supplied evidence.
- **Citation validity:** proportion of generated PDF citations that correspond to retrieved pages.
- **Unanswerable handling:** proportion of unsupported questions that receive the required evidence-insufficiency response.
- **WER:** word error rate for speech transcription; lower is better.
- **Critical entity accuracy:** preservation of required names, dates, acronyms, and other key entities in an ASR transcript.

## 4. Retrieval experiments

| Run | Pipeline and purpose | Split / cases | Hit@5 | Recall@5 | MRR | Decision |
|---|---|---:|---:|---:|---:|---|
| 001 | Initial BM25 baseline | Dev / 7 | 1.000 | 0.929 | 0.857 | Dataset was too small and lexically easy. |
| 002 | BM25 after dataset expansion | Dev / 17 | 0.882 | 0.853 | 0.824 | Accepted as the credible lexical baseline. |
| 003 | BM25 after exact boilerplate removal | Dev / 17 | 0.882 | 0.853 | 0.824 | No gain; rejected as a quality improvement. |
| 004 | BM25, 120 words / 20 overlap | Dev / 17 | 0.882 | 0.882 | 0.794 | Recall rose but ranking worsened. |
| 005 | BM25, 160 words / 30 overlap | Dev / 17 | 0.882 | 0.882 | 0.765 | Rejected. |
| 006 | BM25, 220 words / 40 overlap | Dev / 17 | 0.882 | 0.853 | 0.824 | Retained for best MRR. |
| 007 | BM25, 300 words / 50 overlap | Dev / 17 | 0.882 | 0.853 | 0.784 | Rejected. |
| 008 | Dense cosine baseline | Dev / 17 | 0.941 | 0.941 | 0.776 | Better coverage, weaker first-rank precision. |
| 009 | Unweighted BM25+dense RRF | Dev / 17 | 1.000 | 1.000 | 0.828 | Accepted: first complete top-five coverage. |
| 010 | RRF + evidence-only LLM reranker | Dev / 17 | 1.000 | 1.000 | 0.971 | Accepted: large MRR improvement. |
| 011 | Reranker replication | Dev / 17 | 1.000 | 1.000 | 0.931 | Exposed LLM reranking variance. |
| 012 | First frozen held-out run | Test / 7 | 0.857 | 0.786 | 0.671 | Preserved as the only untouched test result. |
| 013 | Clause-only multi-query | Dev / 19 | 1.000 | 1.000 | 0.904 | Coverage worked; clause context loss caused regressions. |
| 014 | Full-question-first multi-query merge | Dev / 19 | 1.000 | 1.000 | 0.912 | Accepted for multi-section coverage. |
| 015 | Answer-quality evaluation | Dev / 10 | — | — | — | All four answer metrics were 1.000. |
| 016 | Post-hoc audited retrieval test | Test / 7 | 1.000 | 0.857 | 0.833 | Diagnostic only, not a fresh held-out claim. |

### 4.1 What each experiment established

**BM25:** Exact terms and financial wording were strong, but semantic paraphrases and entity-specific hard negatives produced misses. Removing repeated report boilerplate did not change aggregate metrics. Smaller chunks recovered more pages in some multi-page cases but lowered first-result quality, so the original 220/40 configuration was retained.

**Dense retrieval:** Dense embeddings recovered semantic and hard-negative evidence that BM25 missed, increasing Hit@5 and Recall@5 to 0.941. However, exact numeric evidence often appeared at ranks two to five, and one budget-allocation question was missed entirely.

**RRF hybrid:** Unweighted RRF combined complementary lexical and semantic rankings without training weights. BM25 and dense each supplied 20 candidates; RRF used `1/(60 + rank)` and retained 12 candidates for reranking. This was the first configuration with perfect development top-five coverage.

**LLM reranking:** The reranker received only the question and 12 evidence candidates. It was instructed to rank by exact entity, period, accounting scope, metric, and units, without answering or using outside knowledge. MRR improved from 0.828 to a repeated-run range of 0.931-0.971. The variance is explicitly reported rather than selecting only the best run.

**Multi-query retrieval:** Deterministic decomposition is applied only to explicit coordinated questions. Clause-only retrieval solved multi-section coverage but lost useful context for some single-page questions. The accepted method ranks the complete question first, then interleaves clause rankings with duplicate removal. This preserved complete cross-section Recall@5 while improving MRR from 0.904 to 0.912.

## 5. Held-out error analysis

The first frozen test run contained two important findings:

1. The NatWest sale-date case counted page 185 as a miss because the original gold annotation listed only page 58. Manual inspection confirmed that page 185 independently states the same correct date. The schema was changed to represent pages 58 and 185 as alternative complete evidence sets. The original run and score were not overwritten.
2. A genuine two-section miss remained. For a question requiring pages 58 and 165, the pipeline retrieved page 165 in the top five but ranked page 58 sixth. This motivated multi-query development using newly created development examples rather than direct tuning on test labels.

In the post-hoc audited test, every question had at least one valid hit, but Mean Recall@5 remained 0.857. Both cross-section cases retrieved only one of their two labelled pages in the top five. One result used page 65 instead of the labelled page 63, indicating that page-level labels can be ambiguous when an answer is spread across section boundaries.

## 6. Answer-quality results

| Metric | Result |
|---|---:|
| Cases | 10 |
| Answerable cases | 8 |
| Unanswerable cases | 2 |
| Normalized correctness | 1.000 |
| Normalized faithfulness | 1.000 |
| Citation validity | 1.000 |
| Unanswerable handling | 1.000 |

Manual audit confirmed that:

- Multi-section answers cited both required pages.
- Similar numbers were assigned to the correct accounting entities and periods.
- Unsupported questions returned the exact evidence-insufficiency response.
- Conversation-only answers did not fabricate PDF sources.

## 7. Production and system validation

- The initial backend smoke test loaded 678 chunks and returned the correct £23.6 billion answer with page 22 evidence in 4,163 ms.
- Multi-document upload was validated with the two-page take-home assessment and later with `AI Agent Book.pdf` (595 pages, 1,091 chunks).
- Documents are restored from a persistent catalog after server restart.
- Session memory correctly answered “What did I just ask?” without attaching irrelevant PDF citations.
- Both typed and spoken queries return text, sources, timing data, and synthesized MP3 audio.
- The automated unit/integration suite currently has 23 passing tests.

Formal retrieval and answer metrics currently apply to the HM Treasury document only. The two additional documents have integration smoke coverage but do not yet have independent gold evaluation sets.

## 8. Voice-chain validation

| Run | ASR | RAG | TTS | Voice total | WER | Entity accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Initial synthetic clean run | 2,033 ms | 4,602 ms | 2,168 ms | 8,803 ms | 0.000 | 1.000 |
| Initial browser-facing endpoint | 2,946 ms | 3,051 ms | 3,337 ms | 9,335 ms | Exact semantic match | — |
| Multi-document endpoint smoke | 1,025 ms | 5,478 ms | 1,761 ms | 8,265 ms | Exact | — |
| Corrected synthetic clean run | 1,132 ms | 3,886 ms | 2,086 ms | 7,104 ms | 0.000 | 1.000 |
| Corrected browser-facing endpoint | 1,566 ms | 7,909 ms | 2,132 ms | 11,608 ms | Exact | — |

The clean synthetic comparison decreased ASR time from 2,033 to 1,132 ms and voice-chain time from 8,803 to 7,104 ms. This is a single-sample smoke comparison, not a statistically controlled latency benchmark. API/network variability and the number of active documents materially affect results. A real browser interaction with three documents has been observed at approximately 14.6 seconds.

## 9. Latency: what has actually been reduced

The following optimizations are already implemented:

1. **Offline document indexing.** PDF extraction, chunking, and document embeddings are performed at upload time rather than during each question.
2. **Content-addressed index cache.** Document SHA-256, embedding model, and chunk settings identify reusable indexes. An unchanged document is loaded from disk without repeating extraction or embedding API calls.
3. **In-memory query indexes.** Dense vectors and BM25 indexes are loaded once when the backend starts instead of being rebuilt per request.
4. **Vectorized dense search.** Cosine search uses a normalized NumPy matrix multiplication and partial top-k selection rather than scoring and sorting every chunk in Python.
5. **Candidate pruning.** Each retriever produces only 20 candidates; RRF reduces these to 12 for the expensive reranker; only five chunks are sent as answer evidence.
6. **Conditional query decomposition.** Ordinary questions use one retrieval path. Additional retrieval calls are created only for explicit multi-clause questions.
7. **No rewrite call on the first turn.** A standalone first question bypasses the memory query-rewriter model call.
8. **ASR cleanup.** Removing the hallucinated transcription prompt, rejecting silence before API processing, and using `gpt-4o-transcribe` reduced the clean-sample ASR measurement by 44%. This number is directional rather than a guaranteed production reduction.

These changes reduce unnecessary computation, but they do **not** make the current voice experience low latency. The UI currently waits for complete ASR, complete RAG/answer generation, and complete TTS before playing audio.

## 10. Main remaining latency bottleneck

With three loaded documents, the current implementation retrieves and reranks each document sequentially, then makes another cross-document reranker call before answer generation. A history-dependent question can also require a query-rewrite call. The approximate critical path is:

`complete recording → ASR → optional rewrite → per-document query embedding/retrieval/rerank × N → cross-document rerank → answer generation → full TTS → playback`

For three documents this can produce three per-document reranker calls plus one cross-document reranker call, followed by the answer model and TTS. The sequential model calls, not local BM25 or NumPy search, are the dominant cause of the observed 8-15 second latency.

## 11. Recommended latency work

The highest-value next implementation is to replace per-document model reranking with one global retrieval and reranking path:

1. Search all loaded document chunks with one query embedding and one global BM25 index.
2. Fuse candidates globally and call the LLM reranker once, rather than once per document plus once across documents.
3. Keep document identity as chunk metadata so citations remain unchanged.
4. Make memory rewriting conditional on genuinely referential follow-ups instead of every turn with history.
5. Stream answer tokens to the browser and synthesize complete sentences as soon as they are available.
6. For a later voice-agent iteration, use streaming ASR or a realtime speech session so recognition begins before the user finishes speaking.

The global-index change should reduce total model calls while preserving the existing top-5 evaluation design. It must be accepted only after rerunning the frozen retrieval and answer regression suites. Streaming primarily lowers time to first visible token and time to first audio; it may not lower total compute time.

Suggested production targets for the next phase are:

- Text time to first token below 1.5 seconds under normal API conditions.
- Voice time to first audio below 3 seconds after end of speech.
- No material regression from the current retrieval and answer-quality suites.
- Latency reported as median and p95 across at least 20 fixed queries, rather than a single smoke request.

## 12. Limitations and honest interpretation

- The formal gold data covers one annual report and is manually authored.
- Development metrics are optimistic because the development set guided architecture decisions.
- Only the first frozen Run 012 is an untouched held-out result.
- Run 016 is explicitly post-hoc and must not be marketed as independent validation.
- Answer judging uses the same configured chat model family as generation and requires further human or independent-model validation.
- LLM reranking shows run-to-run MRR variance even when code and configuration are unchanged.
- Clean synthetic speech does not measure accents, room noise, interruptions, or microphone hardware.
- Single-request latency measurements are affected by API and network variance; a proper median/p95 benchmark has not yet been run.
- Multi-document functionality is implemented, but the additional uploaded documents do not yet have formal gold datasets.

## 13. Reproducibility and evidence

Every formal run has a timestamped immutable directory under `reports/runs/` containing configuration, metrics, predictions, failures, model traces where applicable, environment versions, and a source-code fingerprint. `reports/experiment_history.csv` is the append-only retrieval metric index. Convenience copies under `reports/latest/` are not the authoritative record.

Key commands:

```powershell
.\.venv\Scripts\python.exe 04_run_baseline_eval.py
.\.venv\Scripts\python.exe 05_run_bm25_eval.py
.\.venv\Scripts\python.exe 08_run_rrf_eval.py
.\.venv\Scripts\python.exe 09_run_llm_reranker_eval.py
.\.venv\Scripts\python.exe 11_run_multi_query_eval.py
.\.venv\Scripts\python.exe 12_run_answer_eval.py
.\.venv\Scripts\python.exe 15_run_voice_smoke.py
.\.venv\Scripts\python.exe -m pytest
```

The complete chronological rationale for every accepted and rejected change is preserved in `EXPERIMENT_LOG.md`.
