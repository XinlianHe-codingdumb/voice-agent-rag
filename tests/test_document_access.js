const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

for (const phrase of ['yes', 'Yes, please do that.', "Yes, please select it. I'll send you my question based on that."]) {
test(`Live Call consent reaches backend: ${phrase}`, async () => {
  const sent = [], requests = [];
  const node = () => ({addEventListener() {}, classList: {add(){}, remove(){}}, appendChild(){},
    value: '', textContent: '', innerHTML: ''});
  const elements = new Map();
  const context = vm.createContext({
    document: {querySelector(id) { if (!elements.has(id)) elements.set(id, node()); return elements.get(id); }, createElement: node},
    localStorage: {getItem(){return null;}, setItem(){}}, navigator: {},
    window: {RealtimeTurnPolicy: require('../web/realtime_turns.js')},
    setTimeout(){return 1;}, clearTimeout(){}, AbortSignal,
    fetch: async (url, options) => {
      requests.push({url, options});
      if (url === '/api/intent') return {ok: true, json: async () => ({requires_documents: true,
        document_access: {status: 'attached'}, response_instructions: 'Search the original DPO question'})};
      if (url.startsWith('/api/conversations/')) return {ok: true, json: async () => ({document_access_pending: false})};
      if (url.startsWith('/api/documents?')) return {ok: true, json: async () => ({documents: []})};
      return new Promise(() => {}); // Ignore unrelated startup requests.
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
  context.recordEvent = data => sent.push(JSON.parse(data));
  vm.runInContext("realtimeChannel = {readyState: 'open', send: recordEvent}; documentAccessPending = true;", context);
  context.testPhrase = phrase;
  await vm.runInContext("handleCompletedUserTranscript(testPhrase)", context);
  assert.equal(JSON.parse(requests.find(r => r.url === '/api/intent').options.body).text, phrase);
  const response = sent.find(e => e.type === 'response.create');
  assert.equal(response.response.tool_choice, 'required');
  assert.equal(response.response.instructions, 'Search the original DPO question');
});
}

test('sidebar deletion calls the right API and refreshes the current selection', async () => {
  const calls = [], elements = new Map();
  let ready = false;
  const node = () => ({addEventListener(){}, classList:{add(){},remove(){}}, appendChild(){}, value:'', innerHTML:''});
  const context = vm.createContext({
    document:{querySelector(id){if(!elements.has(id)) elements.set(id,node()); return elements.get(id);}, createElement:node},
    localStorage:{getItem(){return null;},setItem(){}}, navigator:{},
    window:{confirm(){return true;},RealtimeTurnPolicy:require('../web/realtime_turns.js')},
    setTimeout(){}, clearTimeout(){},
    fetch:async(url, options) => {
      if (!ready) return new Promise(()=>{});
      calls.push({url,options});
      return {ok:true,json:async()=> url === '/api/conversations' ? {conversations:[{conversation_id:'remaining',title:'Remaining'}]} :
        url.startsWith('/api/documents?') ? {documents:[]} : url === '/api/health' ? {document_count:0} : {messages:[]}};
    }
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8'),context);
  ready=true;
  await vm.runInContext("deleteSidebarItem('documents','synthetic')",context);
  await vm.runInContext("deleteSidebarItem('conversations','temporary')",context);
  assert(calls.some(r=>r.url==='/api/documents/synthetic' && r.options.method==='DELETE'));
  assert(calls.some(r=>r.url==='/api/conversations/temporary' && r.options.method==='DELETE'));
  assert(calls.some(r=>r.url==='/api/conversations/remaining'));
});
