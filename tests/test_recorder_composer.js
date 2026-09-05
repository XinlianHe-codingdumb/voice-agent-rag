const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function setup() {
  const nodes = new Map(), requests=[];
  const node = () => ({handlers:{},addEventListener(name,fn){this.handlers[name]=fn;},classList:{add(){},remove(){}},value:'',textContent:'',innerHTML:'',focus(){}});
  let stopPromise;
  class Recorder {
    static isTypeSupported(){return true;}
    constructor(){this.handlers={};this.mimeType='audio/webm';this.state='inactive';}
    addEventListener(name,fn){this.handlers[name]=fn;}
    start(){this.state='recording';}
    requestData(){this.handlers.dataavailable({data:new Blob(['a'.repeat(1000)])});}
    stop(){this.state='inactive';stopPromise=this.handlers.stop();}
  }
  const ui = new Proxy({}, {get:(target,name)=>name==='configure' ? callbacks=>{target.callbacks=callbacks;} : name==='callbacks'?target.callbacks:()=>{}});
  const context=vm.createContext({document:{querySelector(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node},
    window:{ResearchUI:ui},localStorage:{getItem(){return null;},setItem(){}},navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}]})}},
    performance:{now:()=>2000},Blob,FormData,AbortController,AbortSignal,DOMException,MediaRecorder:Recorder,setTimeout(){},clearTimeout(){},
    fetch:async(url,options)=>{requests.push({url,options});if(url==='/api/transcribe')return {ok:true,json:async()=>({transcript:'Where is Chapter 8?'})};if(url==='/api/ask')return {ok:true,json:async()=>({answer:'Grounded answer.',sources:[]})};return new Promise(()=>{});}
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8'),context);
  return {context,nodes,requests,stopped:()=>stopPromise};
}

test('Mic returns an editable draft and performs no ask before manual Send',async()=>{
  const s=setup();await s.nodes.get('#record-button').handlers.click();
  vm.runInContext('peakRms=0.05; speechFrames=10; recordingStartedAt=0; finishRecording();',s.context);
  await s.stopped();
  assert.equal(s.nodes.get('#question').value,'Where is Chapter 8?');
  assert.equal(s.requests.filter(r=>r.url==='/api/transcribe').length,1);
  assert.equal(s.requests.filter(r=>r.url==='/api/ask').length,0);
  s.nodes.get('#question').value='Where is Chapter 8 in this book?';
  // The handler reaches the ask call before awaiting the remaining page refreshes.
  s.nodes.get('#ask-form').handlers.submit({preventDefault(){}});
  const request=s.requests.find(r=>r.url==='/api/ask');
  assert.equal(JSON.parse(request.options.body).question,'Where is Chapter 8 in this book?');
});

test('Cancel discards audio without sending a transcription request',async()=>{
  const s=setup();await s.nodes.get('#record-button').handlers.click();
  vm.runInContext('cancelRecording()',s.context);await s.stopped();
  assert.equal(s.requests.filter(r=>r.url==='/api/transcribe').length,0);
});

test('End live cancels a pending microphone request and enables reconnect',async()=>{
  const s=setup();
  vm.runInContext('navigator.mediaDevices.getUserMedia = () => new Promise(() => {});',s.context);
  const connecting=vm.runInContext('startLiveCall()',s.context);
  vm.runInContext('endLiveCall()',s.context);
  await connecting;
  assert.equal(s.nodes.get('#live-call-button').disabled,false);
  assert.match(s.nodes.get('#live-call-status').textContent,/Call ended/);
});
