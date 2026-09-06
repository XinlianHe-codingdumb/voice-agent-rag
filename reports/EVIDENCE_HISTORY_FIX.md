# Local evidence history repair — 2026-09-06

- Changed the assistant message label from WIZ AI to Voice Agent.
- Root cause: database messages contained only text; history renderer discarded sources; Live Call saved concatenated text without evidence.
- Added an additive SQLite sources_json migration. Existing messages remain intact. Historical display now loads all saved messages; the model still uses bounded recent context.
- Typed/Mic answers save source snapshots. Live Call saves individual assistant segments with their own source lists to preserve citation numbering.
- Restoring a chat reconstructs citations and shows the latest available evidence. Numeric citations are clickable when the corresponding snapshot exists.
- Old messages without saved source snapshots cannot recover their original retrieved excerpts accurately. No new retrieval is presented as historical evidence.
- User accepted local behaviour on 2026-09-06 and authorized publishing. Existing messages without evidence snapshots are left unchanged; no historical retrieval backfill was requested.
- Reading-follow update: message-ID keys replace text keys; each answer always includes a full source button row. Scrolling selects the visible assistant answer closest to the reading center after a 120ms debounce. Clicking a citation cancels pending follow work and selects that card. New replies do not force a reader away from older turns; reopening a chat defaults to its latest evidence-bearing reply.
- Verification: 10 Python tests passed; 11 Node tests passed; both JavaScript syntax checks passed. Initial endpoint test failed due to a missing lock in the test fixture, corrected before the successful run.
- After the reading-follow update: 13 Node tests and 3 evidence-persistence Python tests passed. The user completed local acceptance testing.
