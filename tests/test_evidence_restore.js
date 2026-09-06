const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/workspace.js', 'utf8');
test('restoring a chat passes saved excerpts and shows latest evidence even after small talk', () => {
  const messages = [], panels = [];
  const start = source.indexOf('  function resetMessages(');
  const end = source.indexOf('  function renderLiveStatus(', start);
  const context = vm.createContext({
    $: () => ({innerHTML:'',scrollHeight:100}), currentId:'chat-a',
    clearTimeout(){}, evidenceScrollTimer:null, evidenceCache:new Map(),
    addMessage: (...args) => {messages.push(args);return 'saved-'+args[4];},
    showEvidence: (...args) => panels.push(args)
  });
  vm.runInContext(source.slice(start, end), context);
  const evidence = [{snippet:'Saved excerpt',pdf_page:6}];
  context.items = [{message_id:2,role:'assistant',content:'Answer [1]',sources:evidence},{message_id:4,role:'assistant',content:'Okay',sources:[]}];
  vm.runInContext('resetMessages(items)', context);
  assert.equal(messages[0][2], evidence);
  assert.equal(panels.at(-1)[0], evidence);
  assert.equal(panels.at(-1)[1], 'saved-2');
});

test('scroll chooses the answer at the reading center and does not redraw its panel', () => {
  const panels=[];
  const node=(key,top,bottom)=>({dataset:{evidenceKey:key},getBoundingClientRect:()=>({top,bottom})});
  const nodes=[node('old',0,180),node('current',190,500),node('below',600,900)];
  const context=vm.createContext({
    activeView:'conversations',evidenceKey:'old',
    evidenceCache:new Map([['old',[{snippet:'Old'}]],['current',[{snippet:'Current'}]]]),
    $:()=>({getBoundingClientRect:()=>({top:0,bottom:600})}),
    document:{querySelectorAll:()=>nodes},
    showEvidence:(sources,key)=>{panels.push({sources,key});context.evidenceKey=key;}
  });
  vm.runInContext(source.slice(source.indexOf('  function followReadingEvidence('),source.indexOf('  function renderLiveStatus(')),context);
  context.followReadingEvidence();
  assert.equal(panels.at(-1).key,'current');
  context.followReadingEvidence();
  assert.equal(panels.length,1);
  nodes[0]=node('old',100,500);nodes[1]=node('current',510,800);
  context.followReadingEvidence();
  assert.equal(panels.at(-1).sources[0].snippet,'Old');
  nodes[0]=node('without-evidence',100,500);
  context.followReadingEvidence();
  assert.equal(panels.at(-1).sources.length,0);
});

test('identical answers have separate evidence and always retain all citation buttons', () => {
  const articles=[], panels=[];
  const scroller={scrollHeight:500,scrollTop:0,clientHeight:200,appendChild:n=>articles.push(n)};
  const element=()=>({dataset:{},innerHTML:'',body:{children:[],appendChild(n){this.children.push(n);}},querySelector(){return this.body;}});
  const context=vm.createContext({
    $:selector=>selector==='.welcome'?null:scroller,
    currentId:'chat',messageSequence:0,evidenceCache:new Map(),icon:()=>'',esc:String,
    formatAnswer:()=>'<p>Same answer [1]</p>',
    document:{createElement:element},
    showEvidence:(...args)=>panels.push(args)
  });
  vm.runInContext(source.slice(source.indexOf('  function addMessage('),source.indexOf('  function resetMessages(')),context);
  const first=context.addMessage('assistant','Same answer',[{snippet:'A'}],null,10);
  const second=context.addMessage('assistant','Same answer',[{snippet:'B'}],null,12);
  assert.notEqual(first,second);
  assert.equal(context.evidenceCache.get(first)[0].snippet,'A');
  assert.equal(context.evidenceCache.get(second)[0].snippet,'B');
  assert.match(articles[0].body.children[0].innerHTML,/data-citation="0"/);
  assert.match(articles[1].body.children[0].innerHTML,/data-citation="0"/);
  assert.equal(scroller.scrollTop,0,'new answers must not pull the reader down');
  assert.equal(panels.length,0,'new answer must not replace evidence while reading history');
});
