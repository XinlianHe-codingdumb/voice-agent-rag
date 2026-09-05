/* Presentation components. Network/voice orchestration remains in app.js. */
(() => {
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const paths = {
    chat:'M21 11a8 8 0 0 1-8 8H6l-4 3 1-6a8 8 0 1 1 18-5Z',
    file:'M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 12h8M8 16h6',
    memory:'M9 4a3 3 0 0 0-5 3 4 4 0 0 0-1 7 4 4 0 0 0 6 5m6-15a3 3 0 0 1 5 3 4 4 0 0 1 1 7 4 4 0 0 1-6 5M9 2v20m6-20v20M5 10h4m6 4h4',
    settings:'m9 3 1-1h4l1 3 3 1 3 3-1 3 1 3-3 3-3 1-1 3h-4l-1-3-3-1-3-3 1-3-1-3 3-3 3-1Z M15 12a3 3 0 1 0-6 0 3 3 0 0 0 6 0',
    plus:'M12 5v14M5 12h14', close:'m6 6 12 12M18 6 6 18', trash:'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
    mic:'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5Zm-3 6v1a6 6 0 0 0 12 0v-1M12 18v4m-4 0h8',
    'arrow-up':'M12 19V5m-6 6 6-6 6 6', wave:'M3 10v4m4-8v12m5-16v20m5-16v12m4-8v4', pause:'M8 5v14M16 5v14',
    phone:'M3 15v-5c5-5 13-5 18 0v5l-5-1v-4H8v4l-5 1Z', check:'m5 12 4 4L19 6',
    layers:'m12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5',
    panel:'M3 3h18v18H3V3Zm12 0v18', menu:'M4 6h16M4 12h16M4 18h16',
    upload:'M12 16V3m-5 5 5-5 5 5M4 14v7h16v-7', shield:'m12 2 8 3v7c0 4-5 8-8 10-3-2-8-6-8-10V5l8-3Zm-4 10 3 3 5-6',
    copy:'M8 8h13v13H8V8ZM4 16H2V2h14v2', user:'M16 7a4 4 0 1 0-8 0 4 4 0 0 0 8 0ZM4 22v-3a8 8 0 0 1 16 0v3',
    spark:'m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z', edit:'m4 16 11-11 4 4L8 20H4v-4ZM13 7l4 4',
  };
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
  const fillIcons = (root = document) => root.querySelectorAll('[data-icon]').forEach(node => { node.innerHTML = icon(node.dataset.icon); });
  fillIcons();
  let api = {}, activeView = 'conversations', currentId = '', currentTitle = '', memories = [], conversations = [];
  const evidenceCache = new Map();
  let evidenceSources = [], evidenceKey = '', callStart = 0, callTick = null, live = false, paused = false, muted = false;
  let liveContext = null, frame = null;
  const time = seconds => `${Math.floor(seconds / 60).toString().padStart(2,'0')}:${Math.floor(seconds % 60).toString().padStart(2,'0')}`;
  const date = value => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleDateString(undefined,{month:'short',day:'numeric'}) : '';

  function navigate(view) {
    if (!['conversations','documents','memory','settings'].includes(view)) view = 'conversations';
    activeView = view;
    document.querySelectorAll('[data-view]').forEach(node => { node.classList.toggle('active',node.dataset.view === view); node.setAttribute('aria-current',node.dataset.view === view ? 'page' : 'false'); });
    ['conversation','documents','memory','settings'].forEach(name => { $(`#${name}-page`).hidden = (name === 'conversation' ? 'conversations' : name) !== view; });
    $('#current-title').textContent = view === 'conversations' ? currentTitle || 'New conversation' : view[0].toUpperCase()+view.slice(1);
    $('.app-shell').classList.remove('nav-open');
    $('#session-badge').hidden = !live;
  }
  function setConversation(conversation) {
    if (currentId !== conversation.conversation_id) showEvidence([], '');
    currentId = conversation.conversation_id;
    currentTitle = conversation.title || 'New conversation';
    if (activeView === 'conversations') $('#current-title').textContent = currentTitle;
  }
  function renderDocuments(docs) {
    const selected = docs.filter(doc => doc.attached);
    $('#document-count').textContent = `${selected.length} selected`;
    $('#selection-caption').textContent = selected.length ? `Using ${selected.length} document${selected.length === 1 ? '' : 's'}` : 'Conversation documents';
    $('#selected-documents').innerHTML = selected.map(doc => `<div class="document-chip" title="${esc(doc.name)}">${icon('file')}<span>${esc(doc.name)}</span><button type="button" data-detach="${esc(doc.document_id)}" aria-label="Deselect ${esc(doc.name)}">${icon('close')}</button></div>`).join('') || '<span class="selection-empty">Select documents to ground your answers</span>';
    $('#document-meta').innerHTML = docs.map(doc => `<div class="document-row"><label class="document-choice"><input type="checkbox" data-document-id="${esc(doc.document_id)}" ${doc.attached?'checked':''}>${icon('file')}<span><strong>${esc(doc.name)}</strong><small>${esc(doc.pages)} pages${doc.chunks != null ? ` · ${esc(doc.chunks)} chunks` : ''}</small></span></label><span class="ready-label">${icon('check')}Ready</span><button class="document-remove icon-button" data-delete-document="${esc(doc.document_id)}" aria-label="Remove ${esc(doc.name)}" title="Remove from library">${icon('trash')}</button></div>`).join('') || '<div class="empty-list">Your library is empty. Upload a PDF to get started.</div>';
  }
  function renderConversations(items, id) {
    conversations = items;
    $('#conversation-list').innerHTML = items.map(item => `<div class="conversation-row"><button class="conversation-item ${item.conversation_id===id?'active':''}" data-conversation-id="${esc(item.conversation_id)}" title="${esc(item.title)}">${esc(item.title)}<small>${esc(date(item.updated_at))}${item.document_count != null ? ` · ${item.document_count} documents` : ''}</small></button><button class="delete-item" data-delete-conversation="${esc(item.conversation_id)}" aria-label="Delete ${esc(item.title)}" title="Delete conversation">${icon('trash')}</button></div>`).join('');
    const current = items.find(item=>item.conversation_id===id); if(current) setConversation(current);
  }
  function renderMemories(items) {
    memories = items;
    $('#memory-list').innerHTML = items.map(item => {
      const source = conversations.find(c=>c.conversation_id===item.source_conversation_id);
      const kind = item.category === 'conversation_summary' ? 'Chat summary' : 'Saved detail';
      return `<article class="memory-item"><div><p>${esc(item.content)}</p><div class="memory-meta">${kind} · ${esc(date(item.created_at))}${source ? ` · <button data-memory-source="${esc(source.conversation_id)}">${esc(source.title)}</button>` : item.source_conversation_id ? ' · Source conversation unavailable' : ''}</div></div><div class="memory-actions"><button data-edit-memory="${item.memory_id}">Edit</button><button data-memory-id="${item.memory_id}" aria-label="Delete memory">Delete</button></div></article>`;
    }).join('') || '<div class="empty-list">No chat summaries yet. A summary is saved automatically after 10 user turns in one conversation.</div>';
    $('#clear-memories').hidden = !items.length;
  }
  function showEvidence(sources, key, focusIndex = null) {
    evidenceSources = sources; evidenceKey = key;
    $('#evidence-caption').textContent = sources.length ? `${sources.length} retrieved excerpt${sources.length===1?'':'s'}` : 'For the selected answer';
    $('#evidence-list').innerHTML = sources.map((source, index) => `<button class="evidence-card ${focusIndex===index?'selected':''}" data-evidence-index="${index}" data-document-name="${esc(source.document_name || 'Document')}" data-pdf-page="${esc(source.pdf_page)}"><div class="source-head"><span class="pdf-icon">${icon('file')}</span><div><strong>${esc(source.document_name || 'Document')}</strong><small>[${index+1}] · PDF page ${esc(source.pdf_page)}</small></div></div><div class="source-quote">${esc(source.snippet || source.text || 'No excerpt returned.')}</div><div class="relevance"><span>Retrieved evidence</span><span>Rank ${index+1}</span></div></button>`).join('') || `<div class="evidence-empty">${icon('file')}<strong>Every answer has a starting point</strong><p>Retrieved excerpts will appear here.<br>Select “Evidence” under an answer to inspect its sources.</p></div>`;
    if (focusIndex !== null) {
      $('.app-shell').classList.add('evidence-open'); $('#evidence-toggle').setAttribute('aria-expanded','true');
      $(`[data-evidence-index="${focusIndex}"]`)?.scrollIntoView({block:'nearest',behavior:'smooth'});
    }
  }
  function formatAnswer(text, sources, key) {
    let safe = esc(text);
    safe = safe.replace(/\[Document ([\s\S]*?), PDF page (\d+)\]/g, (all,name,page)=> {
      const index = sources.findIndex(s=>esc(s.document_name)===name && String(s.pdf_page)===page);
      return index < 0 ? all : `<button class="citation" data-citation="${index}" data-answer-key="${esc(key)}" title="View evidence">[${index+1}]</button>`;
    });
    safe = safe.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
    const lines = safe.split('\n'); let html='', list='';
    for (const line of lines) {
      const bullet = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/);
      if(bullet) { if(!list){html+='<ul>';list='ul';} html+=`<li>${bullet[1]}</li>`; }
      else { if(list){html+='</ul>';list='';} if(line.trim()) html+= /^#{1,3}\s/.test(line) ? `<h3>${line.replace(/^#{1,3}\s/,'')}</h3>` : `<p>${line}</p>`; }
    }
    return html+(list?'</ul>':'');
  }
  function addMessage(role,text,sources=[],latency=null) {
    $('.welcome')?.remove();
    const key = `${currentId}:${text}`;
    if(sources.length) evidenceCache.set(key,sources);
    const cached = evidenceCache.get(key) || sources;
    const article = document.createElement('article'); article.className=`message ${role}`;
    article.innerHTML=`<div class="message-avatar">${icon(role==='user'?'user':'spark')}</div><div class="message-content">${role==='user'?'':'<div class="role">WIZ AI</div>'}<div class="answer-body">${role==='user'?`<p>${esc(text).replace(/\n/g,'<br>')}</p>`:formatAnswer(text,cached,key)}</div>${role==='user'?'':`<div class="message-actions"><button data-copy-answer title="Copy answer">${icon('copy')}Copy</button>${cached.length?`<button data-show-evidence data-answer-key="${esc(key)}">${icon('file')}Evidence · ${cached.length}</button>`:''}${latency?`<span class="timing">${(Number(latency)/1000).toFixed(1)}s</span>`:''}</div>`}</div>`;
    article.dataset.copyText=text;
    if(role!=='user' && cached.length && !article.querySelector('.citation')) {
      const refs=document.createElement('div'); refs.className='source-references';
      refs.innerHTML='Retrieved sources '+cached.map((source,index)=>`<button class="citation" data-citation="${index}" data-answer-key="${esc(key)}" title="${esc(source.document_name)} · page ${esc(source.pdf_page)}">[${index+1}]</button>`).join(' ');
      article.querySelector('.answer-body').appendChild(refs);
    }
    $('#messages').appendChild(article); $('#messages').scrollTop=$('#messages').scrollHeight;
    if(role!=='user') showEvidence(cached,key);
  }
  function resetMessages(items=[]) {
    $('#messages').innerHTML=''; showEvidence([],'');
    if(!items.length) $('#messages').innerHTML=`<div class="welcome"><div class="welcome-mark">${icon('layers')}</div><h1>A clearer view of<br>your documents.</h1><p>Ask a question, connect the details, and explore the evidence behind every answer.</p><div class="welcome-rule"></div><small>Select your sources above, then start a conversation.</small></div>`;
    items.forEach(item=>addMessage(item.role,item.content));
  }
  function renderLiveStatus() {
    if(!live)return;
    const status=$('#live-call-status').textContent;
    let label=paused?'Paused':muted?'Microphone muted':/error|could not|no response|closed|disconnected/i.test(status)?'Connection issue':/connect/i.test(status)?'Connecting':/speaking|continuing after “/i.test(status)?'Speaking':/thinking|search|checking|routing|understanding|continuing after document/i.test(status)?'Thinking':'Listening';
    $('#live-state-label').textContent=label;
    $('#live-hint').textContent=paused?'Microphone and playback paused':muted?'Your microphone is off':label==='Listening'?'Speak naturally. You can interrupt.':label==='Speaking'?'Follow the answer and its evidence below':label==='Thinking'?'Working on your question':status;
    $('.app-shell').classList.toggle('live-paused',paused||muted);
    $('.app-shell').classList.toggle('live-thinking',label==='Thinking');
  }
  function setLive(active,stream=null) {
    live=active; $('.app-shell').classList.toggle('live-mode',active); $('#live-hero').hidden=!active; $('#session-badge').hidden=!active;
    $('#question').required=!active;
    if(!active) {
      clearInterval(callTick); callTick=null; callStart=0; paused=false;muted=false;
      if(frame) cancelAnimationFrame(frame);frame=null;
      liveContext?.close().catch(()=>{});liveContext=null;
      setCallFlags(false,false); return;
    }
    navigate('conversations');
    if(stream && !callStart) {
      callStart=Date.now(); callTick=setInterval(()=>$('#call-timer').textContent=time((Date.now()-callStart)/1000),1000);
      const Context=window.AudioContext||window.webkitAudioContext;
      if(Context) try {
        liveContext=new Context();const analyser=liveContext.createAnalyser();analyser.fftSize=256;
        liveContext.createMediaStreamSource(stream).connect(analyser);const samples=new Uint8Array(analyser.frequencyBinCount);
        const bars=[...$('#voice-wave').children];
        const animate=()=>{if(!liveContext)return;analyser.getByteFrequencyData(samples);bars.forEach((bar,i)=>{bar.style.opacity=String(.25+samples[i%samples.length]/340);});frame=requestAnimationFrame(animate);};animate();
      } catch { /* State animation still works when audio visualization is unavailable. */ }
    }
    if(!callStart)$('#call-timer').textContent='00:00';renderLiveStatus();
  }
  function setCallFlags(isMuted,isPaused) {
    muted=isMuted;paused=isPaused;
    $('#mute-call').setAttribute('aria-pressed',String(muted));$('#mute-call').innerHTML=icon('mic')+(muted?'Unmute':'Mute');
    $('#pause-call').setAttribute('aria-pressed',String(paused));$('#pause-call').innerHTML=icon('pause')+(paused?'Resume':'Pause');renderLiveStatus();
  }
  function recording(active,seconds=0,level=0,processing=false) {
    $('.composer').classList.toggle('recording',active);$('#recorder-state').hidden=!active;
    $('#recorder-timer').textContent=time(seconds);$('#record-meter-level').style.width=`${Math.min(100,level)}%`;
    $('#recorder-label').textContent=processing?'Transcribing…':'Listening…';$('#done-recording').disabled=processing;
  }
  function uploadJob(id,name,state,detail='') {
    let row=document.getElementById(`upload-${id}`);if(!row){row=document.createElement('div');row.id=`upload-${id}`;row.className='upload-job';$('#upload-jobs').appendChild(row);}
    row.dataset.state=state;row.innerHTML=`<span title="${esc(name)}">${esc(name)}</span><span title="${esc(detail)}">${esc(state)}${detail?`: ${esc(detail)}`:''}</span>`;
  }
  document.querySelectorAll('[data-view]').forEach(node=>node.addEventListener('click',()=>navigate(node.dataset.view)));
  $('.brand').addEventListener('click',event=>{event.preventDefault();navigate('conversations');});
  $('#sidebar-toggle').addEventListener('click',()=>$('.app-shell').classList.toggle('nav-open'));
  $('#documents-toggle').addEventListener('click',()=>navigate('documents'));$('#add-documents').addEventListener('click',()=>navigate('documents'));
  $('#evidence-toggle').addEventListener('click',()=>{const open=$('.app-shell').classList.toggle('evidence-open');$('#evidence-toggle').setAttribute('aria-expanded',String(open));});
  $('#evidence-close').addEventListener('click',()=>{$('.app-shell').classList.remove('evidence-open');$('#evidence-toggle').setAttribute('aria-expanded','false');});
  $('#upload-open').addEventListener('click',()=>$('#upload-dialog').showModal());$('#upload-close').addEventListener('click',()=>$('#upload-dialog').close());
  $('#memory-close').addEventListener('click',()=>$('#memory-dialog').close());
  $('#selected-documents').addEventListener('click',async event=>{const target=event.target.closest('[data-detach]');if(target){target.disabled=true;try{await api.detach(target.dataset.detach);}catch(error){addMessage('assistant',error.message);}}});
  $('#messages').addEventListener('click',async event=>{
    const target=event.target.closest('[data-answer-key]');if(target){const key=target.dataset.answerKey;showEvidence(evidenceCache.get(key)||[],key,target.hasAttribute('data-citation')?Number(target.dataset.citation):0);}
    const copy=event.target.closest('[data-copy-answer]');if(copy){try{await navigator.clipboard.writeText(copy.closest('.message').dataset.copyText);copy.innerHTML=icon('check')+'Copied';}catch{copy.textContent='Copy unavailable';}}
  });
  $('#evidence-list').addEventListener('click',event=>{const card=event.target.closest('[data-evidence-index]');if(!card)return;showEvidence(evidenceSources,evidenceKey,Number(card.dataset.evidenceIndex));document.dispatchEvent(new CustomEvent('evidence:navigate',{detail:{documentName:card.dataset.documentName,pdfPage:Number(card.dataset.pdfPage)}}));});
  $('#memory-list').addEventListener('click',event=>{
    const target=event.target.closest('[data-edit-memory]');if(target){const memory=memories.find(m=>String(m.memory_id)===target.dataset.editMemory);$('#memory-edit-text').value=memory.content;$('#memory-edit-form').dataset.memoryId=memory.memory_id;$('#memory-edit-status').textContent='';$('#memory-dialog').showModal();}
    const source=event.target.closest('[data-memory-source]');if(source)api.selectConversation(source.dataset.memorySource).then(()=>navigate('conversations')).catch(error=>addMessage('assistant',error.message));
  });
  $('#memory-edit-form').addEventListener('submit',async event=>{event.preventDefault();const submit=event.submitter;submit.disabled=true;try{await api.editMemory(event.currentTarget.dataset.memoryId,$('#memory-edit-text').value);$('#memory-dialog').close();}catch(error){$('#memory-edit-status').textContent=error.message;}finally{submit.disabled=false;}});
  $('#cancel-recording').addEventListener('click',()=>api.cancelRecording());$('#done-recording').addEventListener('click',()=>api.finishRecording());
  $('#mute-call').addEventListener('click',()=>api.mute());$('#pause-call').addEventListener('click',()=>api.pause());$('#end-live-dock').addEventListener('click',()=>api.endLive());
  const followup=()=>{const field=$('#live-followup');const text=field.value.trim();if(text){api.followup(text).then(()=>{field.value='';}).catch(error=>addMessage('assistant',error.message));}};
  $('#send-followup').addEventListener('click',followup);$('#live-followup').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();followup();}});
  $('#question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!$('#ask-button').disabled)$('#ask-form').requestSubmit();}});
  $('#pdf-dropzone').addEventListener('dragover',event=>{event.preventDefault();event.currentTarget.classList.add('dragover');});$('#pdf-dropzone').addEventListener('dragleave',event=>event.currentTarget.classList.remove('dragover'));
  $('#pdf-dropzone').addEventListener('drop',event=>{event.preventDefault();event.currentTarget.classList.remove('dragover');api.uploadFiles([...event.dataTransfer.files]);});
  $('#voice-wave').innerHTML=Array.from({length:55},(_,i)=>`<i style="--height:${5+65*Math.exp(-Math.pow((i-27)/10,2))*(.5+.5*Math.abs(Math.cos(i*.53)))}px;--delay:${(i%9)*-.17}s"></i>`).join('');
  new MutationObserver(renderLiveStatus).observe($('#live-call-status'),{childList:true,characterData:true,subtree:true});
  window.ResearchUI={configure:callbacks=>{api=callbacks;},navigate,setConversation,renderDocuments,renderConversations,renderMemories,addMessage,resetMessages,showEvidence,setLive,setCallFlags,recording,uploadJob,icon};
  resetMessages();
})();
