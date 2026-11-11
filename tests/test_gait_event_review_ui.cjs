// Run the existing shared canvas with the four-paw contact extension; no server or model.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = {group:'gait-s004', datasetId:'ui-fixture', frameWidth:960, frameHeight:544,
  frameCount:2, reviewStart:0, reviewEnd:1, selectedFrames:[0,1],
  physicalPaws:['A','B','C','D'], pawRoles:{A:'Hind physical A',B:'Hind physical B',C:'Front physical C',D:'Front physical D'},
  attribution:'UI fixture only', sourceVideo:{sha256:'fixture'},
  frames:[0,1].map(i=>({frameIndex:i,timestampSeconds:i/12}))};
const blank = {schemaVersion:1, annotationType:'blind-gait-event-review', blind:true,
  manifestSha256:'fixture', datasetId:source.datasetId, reviewer:'', independenceDeclaration:'unreviewed',
  modelExposed:false, previousLabelsExposed:false, pawDescriptions:{A:'',B:'',C:'',D:''},
  observations:Object.fromEntries([0,1].map(i=>[i,Object.fromEntries(['A','B','C','D'].map(p=>[p,
    {visibility:'unreviewed',continuity:'unreviewed',supportState:'unreviewed',notes:''}]))])), strides:[]};

async function test() {
  const elements=new Map(), storage=new Map(), requests=[], frames=[];
  let downloaded;
  function el(id) {
    if(elements.has(id)) return elements.get(id);
    const e={value:'',textContent:'',children:[],style:{},files:[],
      append(...items){this.children.push(...items);}, replaceChildren(...items){this.children=[...items];},
      add(item){this.children.push(item);}, setAttribute(k,v){this[k]=v;},
      closest(){return el('legacy-details');}, insertAdjacentHTML(){}, click(){},
      getContext(){return {canvas:this,drawImage(){}};}};
    elements.set(id,e); return e;
  }
  const sandbox={console,URLSearchParams,location:{search:'?dataset=gait-s004'},structuredClone,Blob,Date,setTimeout,clearTimeout,
    document:{getElementById:el,createElement:()=>el('new-'+elements.size),querySelector:()=>el('warning'),addEventListener(){}},
    Option:class{constructor(text,value){this.textContent=text;this.value=value;}},
    Image:class{set src(url){frames.push(url);queueMicrotask(()=>this.onload());}},
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
    URL:{createObjectURL:b=>{downloaded=b;return 'blob:fixture';},revokeObjectURL(){}},
    fetch:async(url,options)=>{
      requests.push(url);
      if(url==='/api/session?group=gait-s004')return {ok:true,json:async()=>({source,manifestSha256:'fixture',draft:blank})};
      if(url==='/api/validate?group=gait-s004')return {ok:true,json:async()=>({})};
      throw Error('Unexpected request '+url);
    }};
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(root,'training/gait-event-review.js'),'utf8'),sandbox);
  vm.runInContext(fs.readFileSync(path.join(root,'tmp/rtmpose-test/paw-tracking-experiment/manual-annotation/annotation.js'),'utf8')
    .replace('boot().catch(error);','gaitEventReview.boot().catch(error);'),sandbox);
  for(let i=0;i<10;i++)await new Promise(setImmediate);
  assert.equal(el('error').textContent,'');
  assert.equal(vm.runInContext('current',sandbox),0);
  assert.equal(el('image').onclick,null);
  el('eventReviewer').value='reviewer-one';await el('eventStart').onclick();
  assert.equal(el('paws').children[0].children.length,4);
  function stored(name){return JSON.parse([...storage.entries()].find(([k])=>k.endsWith(name))[1]);}
  assert(Object.values(stored('reviewer-one').observations).every(p=>Object.values(p).every(o=>o.supportState==='unreviewed')));
  let selector=el('paws').children[0];selector.value='C';selector.onchange();
  function change(field,value){const row=el('paws').children.find(e=>e.textContent==='C '+field);row.children[0].value=value;row.children[0].onchange();}
  change('visibility','visible');change('supportState','contacting');
  assert.equal(stored('reviewer-one').observations[0].C.supportState,'unreviewed');
  assert.match(el('eventStatus').textContent,/physical paw/);
  change('visibility','occluded');change('continuity','uncertain');change('supportState','unknown');
  assert.equal(stored('reviewer-one').observations[0].C.supportState,'unknown');
  assert.match(el('progress').textContent,/1\/8/);
  el('next').onclick();for(let i=0;i<3;i++)await new Promise(setImmediate);
  assert.equal(vm.runInContext('current',sandbox),1);
  assert.equal(stored('reviewer-one').observations[1].C.supportState,'unreviewed');
  const first=storage.values().next().value;
  el('eventReviewer').value='reviewer-two';await el('eventStart').onclick();
  assert.equal(stored('reviewer-two').observations[0].C.supportState,'unreviewed');
  assert.equal(storage.values().next().value,first);
  el('eventBackup').onclick();assert.equal(JSON.parse(await downloaded.text()).reviewer,'reviewer-two');
  el('eventImport').files=[{text:async()=>JSON.stringify(stored('reviewer-one'))}];await el('eventImport').onchange();
  assert.match(el('eventStatus').textContent,/another reviewer/);
  assert(requests.every(url=>!url.includes('predictions')&&!url.includes('model')));
  assert(frames.every(url=>url.startsWith('/api/frame?group=gait-s004&index=')));
  console.log('PASS four-paw reviewer: original-frame canvas/navigation, blank labels, UNKNOWN/occlusion, physical identity guard, independent drafts, backup and import isolation.');
}
test().catch(e=>{console.error(e);process.exitCode=1;});
