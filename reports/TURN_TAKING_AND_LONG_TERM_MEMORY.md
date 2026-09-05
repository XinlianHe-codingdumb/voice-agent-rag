# Realtime turn-taking and long-term memory design

## Turn-taking policy

OpenAI semantic VAD remains responsible for detecting speech boundaries and committing user audio. Automatic response creation and automatic interruption are disabled. The browser waits for the completed ASR transcript and applies a deterministic policy:

- `backchannel`: exact short acknowledgements such as `OK`, `yeah`, `好啊`, `嗯`, or `你继续`; restore normal Agent volume and create no response.
- `hard_interrupt`: corrections and stop phrases such as `wait`, `stop`, `不对`, or `停一下`; cancel the active response, clear buffered WebRTC output, and answer the new turn.
- `new_turn`: any substantive utterance; if the Agent is speaking, treat it as a real interruption, otherwise create a normal response.
- `noise`: empty transcription; ignore it.

When the user begins speaking during output, Agent audio is ducked to 35% while the transcript is pending. This avoids an immediate hard stop but still makes the user easier to hear. The classifier is local and deterministic, so it adds no model call, API cost, or variable LLM latency. A qualified phrase such as `Okay, but what about chapter eight?` is not an acknowledgement because it is not an exact backchannel.

If a new substantive turn arrives during document search, the browser aborts the stale HTTP retrieval. The outstanding Realtime function call receives a cancelled result before the newest response is created, preventing an old search result from appearing as the answer to a newer question.

## Long-term memory policy

Long-term memory is distinct from the existing bounded conversation history:

- Conversation history: last 12 messages, scoped to one conversation.
- Long-term memory: durable goals, preferences, background, and explicitly requested notes, shared across conversations.

The SQLite table stores category, content, source conversation, timestamps, and a stable deduplication key. Only explicit patterns are captured. The system does not run an opaque post-turn LLM extractor, which avoids silently storing guesses or sensitive incidental details. The primary goal is replaceable; multiple independent preferences and notes may coexist.

Memory is injected into direct RAG answers, the bounded document Agent, and newly connected Realtime sessions. Prompts state that memory is personal background rather than document evidence and that the latest user request overrides conflicts. The UI and API support listing, deleting one item, and clearing all items.

## Known limitation and next evaluation

The acknowledgement lexicon is deliberately conservative. Accent-dependent ASR variants may need to be added from real usage logs. Manual evaluation should measure false-interrupt rate, missed-interrupt rate, time from completed transcript to cancellation, and whether stale tool results ever surface. No audio-environment claim is made by the offline classifier tests.
