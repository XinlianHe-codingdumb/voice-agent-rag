const health = document.querySelector("#health");
const meta = document.querySelector("#document-meta");
const input = document.querySelector("#pdf-input");
const form = document.querySelector("#ask-form");
const question = document.querySelector("#question");
const button = document.querySelector("#ask-button");
const recordButton = document.querySelector("#record-button");
const microphoneSelect = document.querySelector("#microphone-select");
const messages = document.querySelector("#messages");
const uploadProgress = document.querySelector("#upload-progress");
const uploadPercent = document.querySelector("#upload-percent");
const uploadStatus = document.querySelector("#upload-status");
const conversationList = document.querySelector("#conversation-list");
const newConversationButton = document.querySelector("#new-conversation");
const liveCallButton = document.querySelector("#live-call-button");
const liveCallStatus = document.querySelector("#live-call-status");
const memoryList = document.querySelector("#memory-list");
const clearMemoriesButton = document.querySelector("#clear-memories");
const speechLanguage = document.querySelector("#speech-language");
speechLanguage.value = localStorage.getItem("voice-rag-language") || "en";
let documentAccessPending = false;
speechLanguage.addEventListener("change", () => {
  localStorage.setItem("voice-rag-language", speechLanguage.value);
  if (realtimePeer) {
    endLiveCall();
    liveCallStatus.textContent = "Language changed. Start a new live call to apply it.";
  }
});

async function refreshDocumentSelection() {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`);
  if (!response.ok) return;
  const data = await response.json();
  documentAccessPending = !!data.document_access_pending;
  const library = await fetch(`/api/documents?conversation_id=${encodeURIComponent(conversationId)}`).then(r => r.json());
  renderDocuments(library.documents || []);
}

let conversationId = localStorage.getItem("voice-rag-conversation") || "default";

let mediaRecorder = null;
let audioChunks = [];
let recordingStartedAt = 0;
let peakRms = 0;
let speechFrames = 0;
let levelAnimation = null;
let audioContext = null;
let realtimePeer = null;
let realtimeChannel = null;
let realtimeStream = null;
let realtimeAudio = null;
let realtimeUserTranscript = "";
let realtimeAssistantSegments = [];
let realtimeSources = [];
let realtimeToolPending = false;
let realtimeSaveTimer = null;
let realtimeResponseActive = false;
let realtimeCurrentResponseId = null;
let realtimeUserSpokeDuringResponse = false;
let realtimeTurnEpoch = 0;
let realtimeToolAbort = null;
let realtimeQueuedResponse = false;
let realtimeAwaitingTurnDecision = false;
let realtimeResponseWatchdog = null;
let realtimeIntentDecision = null;
let realtimeToolSteps = 0;
let realtimeMuted = false;
let realtimePaused = false;
let currentAudio = null;
let recordingEpoch = 0;
let recordingCancelled = false;
let transcriptionAbort = null;
let uploadQueue = Promise.resolve();
let microphoneRequestAbort = null;

async function requestMicrophone(options) {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access is unavailable in this browser. Open the app in Chrome or Edge.');
  const controller = new AbortController();
  microphoneRequestAbort = controller;
  let settled = false;
  let timer;
  try {
    return await Promise.race([
      navigator.mediaDevices.getUserMedia(options).then(stream => {
        if (settled || controller.signal.aborted) { stream.getTracks().forEach(track => track.stop()); throw new DOMException('Cancelled', 'AbortError'); }
        return stream;
      }),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('Microphone permission is still waiting. Allow access in your browser, then try again.')), 20000);
        controller.signal.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError')), {once:true});
      }),
    ]);
  } finally {
    settled = true;
    clearTimeout(timer);
    if (microphoneRequestAbort === controller) microphoneRequestAbort = null;
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
}

function addMessage(role, text, sources = [], latency = null) {
  if (window.ResearchUI) return window.ResearchUI.addMessage(role, text, sources, latency);
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const evidence = sources.length ? `<div class="evidence">${sources.map(source =>
    `<details class="source"><summary><strong>${escapeHtml(source.document_name || "Document")} · PDF page ${source.pdf_page}</strong></summary>${escapeHtml(source.snippet)}</details>`
  ).join("")}</div>` : "";
  article.innerHTML = `<div class="role">${role === "user" ? "YOU" : "ASSISTANT"}</div><p>${escapeHtml(text)}</p>${evidence}${latency ? `<div class="timing">${latency} MS END-TO-END</div>` : ""}`;
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

function resetMessages(savedMessages = []) {
  if (window.ResearchUI) return window.ResearchUI.resetMessages(savedMessages);
  messages.innerHTML = "";
  const system = document.createElement("article");
  system.className = "message assistant";
  system.innerHTML = '<div class="role">SYSTEM</div><p>Ask for facts, summaries, comparisons, or a learning plan grounded in the selected documents.</p>';
  messages.appendChild(system);
  savedMessages.forEach(message => addMessage(message.role, message.content));
}

async function playResponseAudio(data) {
  if (!data.audio_base64) return;
  const audio = new Audio(`data:${data.audio_mime_type || "audio/mpeg"};base64,${data.audio_base64}`);
  currentAudio?.pause();
  currentAudio = audio;
  try {
    await audio.play();
  } catch (error) {
    addMessage("assistant", `Audio was generated but browser autoplay was blocked: ${error.message}`);
  }
}

function renderDocuments(documents) {
  if (window.ResearchUI) return window.ResearchUI.renderDocuments(documents);
  if (!documents.length) {
    meta.textContent = "No documents loaded.";
    return;
  }
  meta.innerHTML = documents.map(document => `
    <label class="document-choice">
      <input type="checkbox" data-document-id="${escapeHtml(document.document_id)}" ${document.attached ? "checked" : ""}>
      <span>${escapeHtml(document.name)}<small>${document.pages} pages · ${document.chunks} chunks</small></span>
    </label>
    <button type="button" data-delete-document="${escapeHtml(document.document_id)}">Remove file</button>
  `).join("");
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    health.textContent = `${data.document_count} document${data.document_count === 1 ? "" : "s"} online`;
    health.classList.add("online");
  } catch {
    health.textContent = "Backend offline";
    meta.textContent = "Start 14_run_backend.py";
  }
}

function renderConversationList(conversations) {
  if (window.ResearchUI) return window.ResearchUI.renderConversations(conversations, conversationId);
  conversationList.innerHTML = conversations.map(conversation => `
    <button type="button" class="conversation-item ${conversation.conversation_id === conversationId ? "active" : ""}" data-conversation-id="${escapeHtml(conversation.conversation_id)}">
      ${escapeHtml(conversation.title)}
    </button>
    <button type="button" data-delete-conversation="${escapeHtml(conversation.conversation_id)}">Delete chat</button>
  `).join("");
}

async function loadConversations() {
  const response = await fetch("/api/conversations");
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Could not load conversations");
  if (!data.conversations.length) {
    const created = await fetch("/api/conversations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({title: "New conversation"}),
    }).then(item => item.json());
    data.conversations = [created];
  }
  if (!data.conversations.some(item => item.conversation_id === conversationId)) {
    conversationId = data.conversations[0].conversation_id;
  }
  localStorage.setItem("voice-rag-conversation", conversationId);
  renderConversationList(data.conversations);
}

function renderMemories(memories) {
  if (window.ResearchUI) return window.ResearchUI.renderMemories(memories);
  if (!memories.length) {
    memoryList.innerHTML = '<span class="memory-empty">No chat summaries yet. One is saved automatically after 10 user turns.</span>';
    clearMemoriesButton.hidden = true;
    return;
  }
  memoryList.innerHTML = memories.map(memory => `
    <div class="memory-item">
      <span><small>${escapeHtml(memory.category)}</small>${escapeHtml(memory.content)}</span>
      <button type="button" data-memory-id="${memory.memory_id}" aria-label="Forget this memory">×</button>
    </div>
  `).join("");
  clearMemoriesButton.hidden = false;
}

async function loadMemories() {
  try {
    const response = await fetch("/api/memories", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load memory");
    renderMemories(data.memories || []);
  } catch (error) {
    memoryList.innerHTML = `<span class="memory-empty">Memory unavailable: ${escapeHtml(error.message)}</span>`;
    clearMemoriesButton.hidden = true;
    throw error;
  }
}

async function loadCurrentConversation() {
  const [conversationResponse, documentResponse] = await Promise.all([
    fetch(`/api/conversations/${encodeURIComponent(conversationId)}`),
    fetch(`/api/documents?conversation_id=${encodeURIComponent(conversationId)}`),
  ]);
  const conversation = await conversationResponse.json();
  documentAccessPending = !!conversation.document_access_pending;
  const documentData = await documentResponse.json();
  if (!conversationResponse.ok) throw new Error(conversation.detail || "Could not load conversation");
  window.ResearchUI?.setConversation(conversation);
  resetMessages(conversation.messages || []);
  renderDocuments(documentData.documents || []);
}

async function selectConversation(nextId) {
  cancelRecording();
  currentAudio?.pause();
  if (realtimePeer) endLiveCall();
  conversationId = nextId;
  localStorage.setItem("voice-rag-conversation", conversationId);
  await loadConversations();
  await loadCurrentConversation();
  window.ResearchUI?.navigate('conversations');
}

function sendRealtimeEvent(event) {
  if (realtimeChannel?.readyState === "open") {
    realtimeChannel.send(JSON.stringify(event));
    return true;
  }
  return false;
}

function clearRealtimeResponseWatchdog() {
  clearTimeout(realtimeResponseWatchdog);
  realtimeResponseWatchdog = null;
}

function realtimeResponsePolicy(decision, afterTool = false) {
  const policy = {tool_choice: !decision?.requires_documents ? "none" :
    (!afterTool ? "required" : (realtimeToolSteps >= 3 ? "none" : "auto"))};
  if (decision?.response_instructions) policy.instructions = decision.response_instructions;
  return policy;
}

function requestRealtimeResponse(
  status = "Thinking…",
  decision = realtimeIntentDecision,
  afterTool = false,
) {
  clearRealtimeResponseWatchdog();
  if (!sendRealtimeEvent({
    type: "response.create",
    response: realtimeResponsePolicy(decision, afterTool),
  })) {
    liveCallStatus.textContent = "Realtime connection is not ready. End the call and reconnect.";
    return;
  }
  liveCallStatus.textContent = status;
  realtimeResponseWatchdog = setTimeout(() => {
    if (!realtimeResponseActive) {
      liveCallStatus.textContent = "No response started. Refresh the page and reconnect the live call.";
    }
  }, 10000);
}

async function resolveUnifiedIntent(text) {
  const response = await fetch("/api/intent", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text, conversation_id: conversationId}),
    signal: AbortSignal.timeout(15000),
  });
  const decision = await response.json();
  if (!response.ok) throw new Error(decision.detail || "Intent routing failed");
  documentAccessPending = decision.document_access?.status === "pending";
  await refreshDocumentSelection();
  return decision;
}

async function saveRealtimeTurn() {
  if (!realtimeUserTranscript || !realtimeAssistantSegments.length || realtimeToolPending) return;
  const user = realtimeUserTranscript;
  const assistant = realtimeAssistantSegments.join(" ").trim();
  realtimeUserTranscript = "";
  realtimeAssistantSegments = [];
  await fetch("/api/realtime/turn", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({conversation_id: conversationId, user, assistant}),
  });
  await Promise.all([loadConversations(), loadMemories()]);
}

function scheduleRealtimeSave() {
  clearTimeout(realtimeSaveTimer);
  realtimeSaveTimer = setTimeout(() => saveRealtimeTurn().catch(() => {}), 1800);
}

async function executeRealtimeTool(item) {
  const toolEpoch = realtimeTurnEpoch;
  realtimeToolPending = true;
  realtimeToolSteps += 1;
  realtimeToolAbort = new AbortController();
  clearTimeout(realtimeSaveTimer);
  liveCallStatus.textContent = "Searching selected documents… you can interrupt me.";
  let output;
  try {
    const args = JSON.parse(item.arguments || "{}");
    if (item.name !== "search_documents") throw new Error(`Unknown tool: ${item.name}`);
    const response = await fetch("/api/realtime/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        conversation_id: conversationId,
        query: args.query,
        top_k: args.top_k || 5,
      }),
      signal: realtimeToolAbort.signal,
    });
    output = await response.json();
    if (!response.ok) throw new Error(output.detail || "Document search failed");
    if (toolEpoch === realtimeTurnEpoch) {
      realtimeSources = output.results || [];
      window.ResearchUI?.showEvidence(realtimeSources, '');
    } else {
      output = {cancelled: true, reason: "The user started a newer turn."};
    }
  } catch (error) {
    output = error.name === "AbortError"
      ? {cancelled: true, reason: "The user started a newer turn."}
      : {error: error.message};
  }
  sendRealtimeEvent({
    type: "conversation.item.create",
    item: {
      type: "function_call_output",
      call_id: item.call_id,
      output: JSON.stringify(output),
    },
  });
  realtimeToolPending = false;
  realtimeToolAbort = null;
  if (toolEpoch !== realtimeTurnEpoch && !realtimeQueuedResponse) return;
  const queued = realtimeQueuedResponse;
  realtimeQueuedResponse = false;
  if (queued) {
    realtimeToolSteps = 0;
    requestRealtimeResponse(
      "Thinking about your newer question…",
      realtimeIntentDecision,
      false,
    );
  } else {
    requestRealtimeResponse(
      "Continuing after document search…",
      realtimeIntentDecision,
      true,
    );
  }
}

function restoreRealtimeAudio() {
  if (realtimeAudio) realtimeAudio.volume = 1;
}

async function handleCompletedUserTranscript(transcript) {
  if (!window.RealtimeTurnPolicy?.classifyUtterance) {
    liveCallStatus.textContent = "Frontend files are out of sync. Refresh the page and reconnect.";
    return;
  }
  const turnAction = window.RealtimeTurnPolicy.classifyUtterance(transcript);
  const spokeDuringResponse = realtimeUserSpokeDuringResponse;
  realtimeUserSpokeDuringResponse = false;
  realtimeAwaitingTurnDecision = false;

  if (turnAction === "noise") {
    restoreRealtimeAudio();
    liveCallStatus.textContent = realtimeResponseActive ? "Speaking…" : "Listening…";
    return;
  }
  if (turnAction === "backchannel" && !documentAccessPending) {
    restoreRealtimeAudio();
    liveCallStatus.textContent = realtimeResponseActive
      ? `Continuing after “${transcript}”…`
      : `Acknowledged “${transcript}”. Listening…`;
    return;
  }

  realtimeTurnEpoch += 1;
  const turnEpoch = realtimeTurnEpoch;
  realtimeToolSteps = 0;
  saveRealtimeTurn().catch(() => {});
  realtimeUserTranscript = transcript;
  realtimeAssistantSegments = [];
  realtimeSources = [];
  addMessage("user", transcript);

  if (spokeDuringResponse) {
    if (realtimeResponseActive) sendRealtimeEvent({type: "response.cancel"});
    sendRealtimeEvent({type: "output_audio_buffer.clear"});
  }
  restoreRealtimeAudio();
  liveCallStatus.textContent = "Routing your request…";
  const decision = await resolveUnifiedIntent(transcript);
  if (turnEpoch !== realtimeTurnEpoch) return;
  realtimeIntentDecision = decision;
  if (realtimeToolPending) {
    realtimeQueuedResponse = true;
    realtimeToolAbort?.abort();
    liveCallStatus.textContent = "Switching to your newer question…";
  } else {
    const status = decision.requires_documents
      ? "Checking selected documents…"
      : "Thinking…";
    requestRealtimeResponse(
      turnAction === "hard_interrupt" ? `Interrupted · ${status.toLowerCase()}` : status,
      decision,
      false,
    );
  }
}

function handleRealtimeEvent(event) {
  if (realtimePaused && event.type.startsWith('input_audio_buffer.')) return;
  if (event.type === "input_audio_buffer.speech_started") {
    realtimeAwaitingTurnDecision = true;
    realtimeUserSpokeDuringResponse = realtimeResponseActive || realtimeToolPending;
    if (realtimeUserSpokeDuringResponse && realtimeAudio) realtimeAudio.volume = 0.35;
    liveCallStatus.textContent = realtimeUserSpokeDuringResponse
      ? "Listening briefly before deciding whether to interrupt…"
      : "Listening…";
    clearTimeout(realtimeSaveTimer);
  } else if (event.type === "input_audio_buffer.speech_stopped") {
    liveCallStatus.textContent = "Understanding what you said…";
  } else if (event.type === "conversation.item.input_audio_transcription.completed") {
    if (realtimePaused || realtimeMuted) return;
    const transcript = (event.transcript || "").trim();
    if (transcript) handleCompletedUserTranscript(transcript).catch(error => {
      restoreRealtimeAudio();
      liveCallStatus.textContent = `Intent error: ${error.message}`;
    });
    else restoreRealtimeAudio();
  } else if (event.type === "response.created") {
    clearRealtimeResponseWatchdog();
    realtimeResponseActive = true;
    realtimeCurrentResponseId = event.response?.id || null;
    liveCallStatus.textContent = "Speaking…";
  } else if (event.type === "response.done") {
    if (!realtimeCurrentResponseId || event.response?.id === realtimeCurrentResponseId) {
      realtimeResponseActive = false;
      realtimeCurrentResponseId = null;
      if (!realtimeAwaitingTurnDecision) restoreRealtimeAudio();
    }
  } else if (["response.output_audio_transcript.done", "response.audio_transcript.done"].includes(event.type)) {
    const transcript = (event.transcript || "").trim();
    if (transcript) {
      realtimeAssistantSegments.push(transcript);
      addMessage("assistant", transcript, realtimeSources);
      realtimeSources = [];
      scheduleRealtimeSave();
    }
    liveCallStatus.textContent = "Listening…";
  } else if (event.type === "response.output_item.done" && event.item?.type === "function_call") {
    executeRealtimeTool(event.item).catch(error => {
      liveCallStatus.textContent = `Tool error: ${error.message}`;
    });
  } else if (event.type === "error") {
    clearRealtimeResponseWatchdog();
    liveCallStatus.textContent = `Realtime error: ${event.error?.message || "unknown error"}`;
  }
}

function endLiveCall() {
  microphoneRequestAbort?.abort();
  realtimeTurnEpoch += 1;
  clearTimeout(realtimeSaveTimer);
  clearRealtimeResponseWatchdog();
  saveRealtimeTurn().catch(() => {});
  const closingChannel = realtimeChannel;
  const closingPeer = realtimePeer;
  realtimeChannel = null;
  realtimePeer = null;
  closingChannel?.close();
  closingPeer?.close();
  realtimeStream?.getTracks().forEach(track => track.stop());
  realtimeToolAbort?.abort();
  if (realtimeAudio) realtimeAudio.srcObject = null;
  realtimePeer = null;
  realtimeChannel = null;
  realtimeStream = null;
  realtimeAudio = null;
  realtimeResponseActive = false;
  realtimeCurrentResponseId = null;
  realtimeUserSpokeDuringResponse = false;
  realtimeToolPending = false;
  realtimeToolAbort = null;
  realtimeQueuedResponse = false;
  realtimeAwaitingTurnDecision = false;
  realtimeIntentDecision = null;
  realtimeToolSteps = 0;
  realtimeMuted = false;
  realtimePaused = false;
  window.ResearchUI?.setLive(false);
  liveCallButton.classList.remove("connected");
  liveCallButton.disabled = false;
  liveCallButton.innerHTML = window.ResearchUI ? window.ResearchUI.icon('wave') + 'Talk live' : 'Start live call';
  liveCallStatus.textContent = "Call ended. Push-to-talk is also available below.";
}

async function startLiveCall() {
  cancelRecording();
  currentAudio?.pause();
  const connectEpoch = ++realtimeTurnEpoch;
  liveCallButton.disabled = true;
  liveCallStatus.textContent = "Connecting secure realtime session…";
  window.ResearchUI?.setLive(true);
  try {
    const selectedDevice = microphoneSelect.value;
    realtimeStream = await requestMicrophone({
      audio: {
        ...(selectedDevice ? {deviceId: {exact: selectedDevice}} : {}),
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });
    if (connectEpoch !== realtimeTurnEpoch) {
      realtimeStream.getTracks().forEach(track => track.stop());
      realtimeStream = null;
      return;
    }
    realtimePeer = new RTCPeerConnection();
    realtimeAudio = document.createElement("audio");
    realtimeAudio.autoplay = true;
    realtimePeer.ontrack = event => { realtimeAudio.srcObject = event.streams[0]; };
    realtimePeer.addTrack(realtimeStream.getAudioTracks()[0]);
    realtimeChannel = realtimePeer.createDataChannel("oai-events");
    realtimeChannel.addEventListener("message", event => handleRealtimeEvent(JSON.parse(event.data)));
    realtimeChannel.addEventListener("open", () => {
      liveCallStatus.textContent = "Listening… speak naturally and interrupt at any time.";
    });
    realtimeChannel.addEventListener("close", () => {
      if (realtimePeer) { endLiveCall(); liveCallStatus.textContent = 'Live connection closed. You can reconnect.'; }
    });
    const offer = await realtimePeer.createOffer();
    await realtimePeer.setLocalDescription(offer);
    const response = await fetch(`/api/realtime/session?conversation_id=${encodeURIComponent(conversationId)}&language=${encodeURIComponent(speechLanguage.value)}`, {
      method: "POST",
      headers: {"Content-Type": "application/sdp"},
      body: offer.sdp,
    });
    const answerSdp = await response.text();
    if (connectEpoch !== realtimeTurnEpoch || !realtimePeer) return;
    if (!response.ok) throw new Error(answerSdp);
    await realtimePeer.setRemoteDescription({type: "answer", sdp: answerSdp});
    liveCallButton.classList.add("connected");
    liveCallButton.textContent = "End live call";
    window.ResearchUI?.setLive(true, realtimeStream);
  } catch (error) {
    if (connectEpoch !== realtimeTurnEpoch || error.name === 'AbortError') return;
    endLiveCall();
    liveCallStatus.textContent = `Could not start live call: ${error.message}`;
  } finally {
    liveCallButton.disabled = false;
  }
}

liveCallButton.addEventListener("click", () => {
  if (realtimePeer) endLiveCall();
  else startLiveCall();
});

conversationList.addEventListener("click", event => {
  const deletion = event.target.closest("[data-delete-conversation]");
  if (deletion) {
    deleteSidebarItem("conversations", deletion.dataset.deleteConversation).catch(error => addMessage("assistant", error.message));
    return;
  }
  const target = event.target.closest("[data-conversation-id]");
  if (target) selectConversation(target.dataset.conversationId).catch(error => addMessage("assistant", `Error: ${error.message}`));
});

async function deleteSidebarItem(kind, id) {
  if (button.disabled || recordButton.disabled || mediaRecorder?.state === "recording") {
    throw new Error("Please finish the current question or recording before deleting.");
  }
  const warning = kind === "documents"
    ? "Remove this file from the library and ALL chats? The original PDF and index are retained; re-upload to restore."
    : "Delete this chat and its messages? Documents and long-term memories are kept.";
  if (!window.confirm(warning)) return;
  if (realtimePeer) endLiveCall();
  const response = await fetch(`/api/${kind}/${encodeURIComponent(id)}`, {method: "DELETE"});
  if (!response.ok) throw new Error((await response.json()).detail || "Delete failed");
  await loadConversations();
  await loadCurrentConversation();
  await loadHealth();
}

meta.addEventListener("click", event => {
  const target = event.target.closest("[data-delete-document]");
  if (target) deleteSidebarItem("documents", target.dataset.deleteDocument).catch(error => addMessage("assistant", error.message));
});

newConversationButton.addEventListener("click", async () => {
  const response = await fetch("/api/conversations", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({title: "New conversation"}),
  });
  const data = await response.json();
  if (!response.ok) return addMessage("assistant", `Error: ${data.detail || "Could not create conversation"}`);
  await selectConversation(data.conversation_id);
});

memoryList.addEventListener("click", async event => {
  const button = event.target.closest("[data-memory-id]");
  if (!button) return;
  button.disabled = true;
  const response = await fetch(`/api/memories/${encodeURIComponent(button.dataset.memoryId)}`, {method: "DELETE"});
  if (!response.ok) {
    const data = await response.json();
    addMessage("assistant", `Memory error: ${data.detail || "Could not forget memory"}`);
  }
  await loadMemories();
});

clearMemoriesButton.addEventListener("click", async () => {
  clearMemoriesButton.disabled = true;
  try {
    const response = await fetch("/api/memories", {method: "DELETE"});
    if (!response.ok) throw new Error("Could not clear long-term memory");
    await loadMemories();
  } catch (error) {
    addMessage("assistant", `Memory error: ${error.message}`);
  } finally {
    clearMemoriesButton.disabled = false;
  }
});

meta.addEventListener("change", async event => {
  const checkbox = event.target.closest("[data-document-id]");
  if (!checkbox) return;
  checkbox.disabled = true;
  const endpoint = `/api/conversations/${encodeURIComponent(conversationId)}/documents/${encodeURIComponent(checkbox.dataset.documentId)}`;
  try {
    const response = await fetch(endpoint, {method: checkbox.checked ? "POST" : "DELETE"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not update document selection");
    await loadConversations();
    await refreshDocumentSelection();
  } catch (error) {
    checkbox.checked = !checkbox.checked;
    addMessage("assistant", `Error: ${error.message}`);
  } finally {
    checkbox.disabled = false;
  }
});

function setUploadProgress(percent, status, indeterminate = false) {
  uploadProgress.hidden = false;
  uploadProgress.classList.toggle("indeterminate", indeterminate);
  uploadPercent.textContent = indeterminate ? "" : `${percent}%`;
  uploadProgress.style.setProperty("--progress", `${percent * 3.6}deg`);
  uploadStatus.textContent = status;
}

function uploadPdf(file, targetConversation = conversationId) {
  return new Promise(resolve => {
  const job = `${Date.now()}-${Math.floor(Math.random()*100000)}`;
  window.ResearchUI?.uploadJob(job, file.name, 'Uploading');
  const body = new FormData();
  body.append("file", file, file.name);
  body.append("conversation_id", targetConversation);
  const request = new XMLHttpRequest();
  request.open("POST", "/api/documents");
  setUploadProgress(0, `Uploading ${file.name}`);
  request.upload.addEventListener("progress", event => {
    if (event.lengthComputable) {
      const percent = Math.min(100, Math.round(event.loaded / event.total * 100));
      setUploadProgress(percent, percent < 100 ? `Uploading ${file.name}` : "Upload complete · indexing", percent >= 100);
    } else {
      setUploadProgress(0, `Uploading ${file.name}`, true);
    }
  });
  request.upload.addEventListener("load", () => {
    setUploadProgress(100, "Indexing document…", true);
    window.ResearchUI?.uploadJob(job, file.name, 'Indexing');
  });
  request.addEventListener("load", async () => {
    try {
    let data = {};
    try { data = JSON.parse(request.responseText); } catch { data = {}; }
    if (request.status < 200 || request.status >= 300) {
      uploadProgress.hidden = true;
      window.ResearchUI?.uploadJob(job, file.name, 'Failed', data.detail || 'Upload failed');
      return;
    }
    setUploadProgress(100, "Ready");
    window.ResearchUI?.uploadJob(job, file.name, 'Ready');
    await loadHealth();
    await Promise.all([loadConversations(), loadMemories()]);
    await refreshDocumentSelection();
    } catch(error) {
      window.ResearchUI?.uploadJob(job, file.name, 'Failed', error.message);
    } finally { resolve(); }
  });
  request.addEventListener("error", () => {
    uploadProgress.hidden = true;
    window.ResearchUI?.uploadJob(job, file.name, 'Failed', 'Connection interrupted');
    resolve();
  });
  request.send(body);
  });
}

function queueUploads(files) {
  const cid = conversationId;
  for (const file of files) uploadQueue = uploadQueue.then(() => uploadPdf(file, cid));
}

input.addEventListener("change", () => {
  queueUploads([...input.files]);
  input.value = "";
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) return;
  if (button.disabled) return;
  const requestConversation = conversationId;
  addMessage("user", text);
  question.value = "";
  button.disabled = true;
  button.textContent = "Thinking…";
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: text, conversation_id: requestConversation}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Request failed");
    if (requestConversation === conversationId) {
      addMessage("assistant", data.answer, data.sources, data.timings_ms?.total || data.latency_ms);
      await refreshDocumentSelection();
      await playResponseAudio(data);
    }
    await Promise.all([loadConversations(), loadMemories()]);
  } catch (error) {
    addMessage("assistant", `Error: ${error.message}`);
  } finally {
    button.disabled = false;
    button.innerHTML = window.ResearchUI ? 'Send ' + window.ResearchUI.icon('arrow-up') : 'Ask <span>→</span>';
    question.focus();
  }
});

function preferredRecordingType() {
  const choices = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return choices.find(type => MediaRecorder.isTypeSupported(type)) || "";
}

function extensionForMime(mime) {
  if (mime.includes("mp4")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

async function loadMicrophones() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  const previous = microphoneSelect.value;
  const devices = (await navigator.mediaDevices.enumerateDevices())
    .filter(device => device.kind === "audioinput");
  microphoneSelect.replaceChildren(new Option("Default microphone", ""));
  devices.forEach((device, index) => {
    microphoneSelect.add(new Option(device.label || `Microphone ${index + 1}`, device.deviceId));
  });
  if ([...microphoneSelect.options].some(option => option.value === previous)) {
    microphoneSelect.value = previous;
  }
}

function stopLevelMonitor() {
  if (levelAnimation !== null) cancelAnimationFrame(levelAnimation);
  levelAnimation = null;
  if (audioContext) audioContext.close().catch(() => {});
  audioContext = null;
}

function startLevelMonitor(stream) {
  const Context = window.AudioContext || window.webkitAudioContext;
  if (!Context) return;
  audioContext = new Context();
  const source = audioContext.createMediaStreamSource(stream);
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  const measure = () => {
    analyser.getFloatTimeDomainData(samples);
    const rms = Math.sqrt(samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length);
    peakRms = Math.max(peakRms, rms);
    if (rms >= 0.008) speechFrames += 1;
    const level = Math.min(99, Math.round(rms * 500));
    window.ResearchUI?.recording(true, (performance.now() - recordingStartedAt) / 1000, level);
    levelAnimation = requestAnimationFrame(measure);
  };
  measure();
}

function finishRecording() {
  if (mediaRecorder?.state === 'recording') { mediaRecorder.requestData(); mediaRecorder.stop(); }
}

function cancelRecording() {
  microphoneRequestAbort?.abort();
  recordingCancelled = true;
  recordingEpoch += 1;
  transcriptionAbort?.abort();
  transcriptionAbort = null;
  if (mediaRecorder?.state === 'recording') mediaRecorder.stop();
  stopLevelMonitor();
  recordButton.disabled = false;
  window.ResearchUI?.recording(false);
}

recordButton.addEventListener("click", async () => {
  if (mediaRecorder?.state === "recording") { finishRecording(); return; }
  if (recordButton.disabled) return;
  if (realtimePeer) return;
  currentAudio?.pause();
  recordingCancelled = false;
  const epoch = ++recordingEpoch;
  const draft = question.value;
  recordButton.disabled = true;
  try {
    const selectedDevice = microphoneSelect.value;
    const stream = await requestMicrophone({
      audio: {
        ...(selectedDevice ? {deviceId: {exact: selectedDevice}} : {}),
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });
    if (epoch !== recordingEpoch) { stream.getTracks().forEach(track=>track.stop()); return; }
    await loadMicrophones();
    const mimeType = preferredRecordingType();
    audioChunks = [];
    peakRms = 0;
    speechFrames = 0;
    mediaRecorder = mimeType
      ? new MediaRecorder(stream, {mimeType, audioBitsPerSecond: 128000})
      : new MediaRecorder(stream, {audioBitsPerSecond: 128000});
    recordingStartedAt = performance.now();
    window.ResearchUI?.recording(true);
    mediaRecorder.addEventListener("dataavailable", event => {
      if (event.data.size) audioChunks.push(event.data);
    });
    mediaRecorder.addEventListener("stop", async () => {
      stopLevelMonitor();
      stream.getTracks().forEach(track => track.stop());
      if (epoch !== recordingEpoch || recordingCancelled) return;
      const duration = performance.now() - recordingStartedAt;
      const recordedMime = mediaRecorder.mimeType || mimeType || "audio/webm";
      const blob = new Blob(audioChunks, {type: recordedMime});
      if (duration < 900 || blob.size < 500) {
        liveCallStatus.textContent = "Recording too short. Speak for at least one second before Done.";
        recordButton.disabled = false;
        window.ResearchUI?.recording(false);
        return;
      }
      if (peakRms < 0.005 || speechFrames < 3) {
        const selectedLabel = microphoneSelect.selectedOptions[0]?.text || "Default microphone";
        liveCallStatus.textContent = `No signal from ${selectedLabel}. Choose your microphone in Settings.`;
        recordButton.disabled = false;
        window.ResearchUI?.recording(false);
        return;
      }
      const body = new FormData();
      body.append("file", blob, `question.${extensionForMime(recordedMime)}`);
      body.append("conversation_id", conversationId);
      body.append("duration_ms", String(Math.round(duration)));
      body.append("peak_rms", String(peakRms));
      body.append("language", speechLanguage.value);
      window.ResearchUI?.recording(true, duration / 1000, 0, true);
      transcriptionAbort = new AbortController();
      try {
        const response = await fetch("/api/transcribe", {method: "POST", body, signal: transcriptionAbort.signal});
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Voice request failed");
        if (epoch !== recordingEpoch) return;
        question.value = draft ? `${draft}\n${data.transcript}` : data.transcript;
        liveCallStatus.textContent = 'Transcript ready. Review or edit it, then press Send.';
        question.focus();
      } catch (error) {
        if (error.name !== 'AbortError') liveCallStatus.textContent = `Transcription error: ${error.message}`;
      } finally {
        if (epoch === recordingEpoch) {
          recordButton.disabled = false;
          transcriptionAbort = null;
          window.ResearchUI?.recording(false);
        }
      }
    });
    mediaRecorder.start(250);
    startLevelMonitor(stream);
  } catch (error) {
    if (epoch !== recordingEpoch || error.name === 'AbortError') return;
    stopLevelMonitor();
    recordButton.disabled = false;
    window.ResearchUI?.recording(false);
    const guidance = error.name === "NotAllowedError"
      ? " Allow microphone access from Chrome's address-bar site controls, then try again."
      : error.name === "NotFoundError"
        ? " No microphone input device is available."
        : "";
    liveCallStatus.textContent = `Microphone error: ${error.message}.${guidance}`;
  }
});

function updateCallFlags() {
  realtimeStream?.getAudioTracks().forEach(track => { track.enabled = !realtimeMuted && !realtimePaused; });
  if (realtimeAudio) realtimeAudio.muted = realtimePaused;
  window.ResearchUI?.setCallFlags(realtimeMuted, realtimePaused);
}

window.ResearchUI?.configure({
  selectConversation,
  detach: async id => {
    const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/documents/${encodeURIComponent(id)}`, {method:'DELETE'});
    if (!response.ok) throw new Error('Could not deselect document');
    await refreshDocumentSelection(); await loadConversations();
  },
  editMemory: async (id, content) => {
    const response = await fetch(`/api/memories/${id}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})});
    if (!response.ok) throw new Error((await response.json()).detail || 'Could not update memory');
    await loadMemories();
  },
  cancelRecording, finishRecording,
  mute: () => { realtimeMuted = !realtimeMuted; updateCallFlags(); },
  pause: () => { realtimePaused = !realtimePaused; updateCallFlags(); },
  endLive: endLiveCall,
  followup: async text => {
    if (!realtimeChannel || realtimeChannel.readyState !== 'open') throw new Error('Wait for the live connection to open.');
    if (realtimePaused) throw new Error('Resume the live session before sending a follow-up.');
    sendRealtimeEvent({type:'conversation.item.create',item:{type:'message',role:'user',content:[{type:'input_text',text}]}});
    realtimeUserSpokeDuringResponse = realtimeResponseActive || realtimeToolPending;
    await handleCompletedUserTranscript(text);
  },
  uploadFiles: files => queueUploads(files),
});

Promise.all([loadHealth(), loadConversations(), loadMemories()])
  .then(() => loadCurrentConversation())
  .catch(error => addMessage("assistant", `Startup error: ${error.message}`));
loadMicrophones().catch(() => {});
navigator.mediaDevices?.addEventListener?.("devicechange", () => loadMicrophones().catch(() => {}));
