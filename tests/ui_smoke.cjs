// Optional DOM smoke test: pnpm --dir .tools/ui-test add jsdom fake-indexeddb
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const {JSDOM}=require('../.tools/ui-test/node_modules/jsdom');
const fidb=require('../.tools/ui-test/node_modules/fake-indexeddb');
const dom=new JSDOM(fs.readFileSync('templates/index.html','utf8'),{url:'http://localhost/',runScripts:'outside-only'});
const w=dom.window;w.scrollTo=()=>{};w.indexedDB=fidb.indexedDB;w.crypto.randomUUID=()=>require('crypto').randomUUID();
w.URL.createObjectURL=()=> 'blob:local';w.URL.revokeObjectURL=()=>{};
w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>()=>{}});
let calls=[];w.fetch=async(path,options={})=>{calls.push(path);let data={};if(path==='/api/me')data={user:null,csrf:'test',storage:{notice:'local'}};else if(path==='/api/examples')data=[];else if(path==='/api/jobs')data={id:'test-job'};else if(path==='/api/jobs/test-job')data={state:'done',result:{fields:[],warnings:[]}};else if(path.startsWith('/api/batches'))data=[];return {ok:true,json:async()=>data}};
const ctx=dom.getInternalVMContext();for(const file of ['static/app.js','static/v3.js'])vm.runInContext(fs.readFileSync(file,'utf8'),ctx,{filename:file});
const run=s=>vm.runInContext(s,ctx);
(async()=>{
 await run('window.initialSession');await new Promise(r=>setTimeout(r,20));
 assert.equal(run('user'),null);assert.equal(w.document.querySelector('#auth-dialog').open,false);
 run("club()");assert.equal(w.document.querySelector('#auth-dialog').open,true);w.document.querySelector('#auth-dialog').close();
 await run("devicePut({id:'test',title:'Formulario completo',created:new Date().toISOString(),status:'reviewed',storage:'device',fields:[{label:'Edad',value:'20',confirmed:true},{label:'Nota',value:'18',confirmed:true}]})");
 await run("openSaved('test','device')");assert.equal(run('fields.length'),2);assert.equal(w.document.querySelector('#form-title').value,'Formulario completo');
 run("file=new File(['test'],'page.png',{type:'image/png'})");await run("document.querySelector('#extract').onclick()");
 assert.ok(calls.includes('/api/jobs'));assert.equal(w.document.querySelector('#auth-dialog').open,false);
 console.log('PASS: guest extraction, account gate, local history, complete saved responses');
 dom.window.close();
})().catch(e=>{console.error(e);dom.window.close();process.exitCode=1});
