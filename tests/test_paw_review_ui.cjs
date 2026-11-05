// Exercise the actual existing interface with the review extension, using a minimal DOM.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../tmp/rtmpose-test/paw-tracking-experiment/manual-annotation');
const base=JSON.parse(cp.execFileSync('python',['-c',`import json
from training.review_paw_annotations import session
from training.prepare_paw_annotations import label_digest
b=session()
for r in b['records']: r['labelHashes']={p:label_digest(r['human'][p]) for p in ('A','B')}
print(json.dumps(b))`],{maxBuffer:4e6}));
async function test(group){
 const els=new Map(),store=new Map(),requested=[];let blob;let previewFailure=false;
 const ctx={drawImage(){},clearRect(){},beginPath(){},arc(){},stroke(){},fillText(){},moveTo(){},lineTo(){}};
 function el(id){if(els.has(id))return els.get(id);const e={id,value:'',textContent:'',children:[],style:{},files:[],clientLeft:2,clientTop:2,width:852,height:480,
  append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=[...xs];this.value=xs[0]?.value||'';},add(x){this.children.push(x);if(this.children.length===1)this.value=x.value;},setAttribute(){},closest(){return el('details');},insertAdjacentHTML(){},getContext(){return {...ctx,canvas:this};},getBoundingClientRect(){return {left:0,top:0,width:856,height:484};},click(){}};els.set(id,e);return e;}
 el('queue').value='selected';el('limb').value='hind';
 const sandbox={console,URLSearchParams,location:{search:'?dataset='+group},structuredClone,Blob,Date,setTimeout,clearTimeout,
 document:{getElementById:el,createElement:t=>el('new'+Math.random()),createTextNode:t=>({textContent:t}),querySelector:()=>el('warning'),addEventListener(){}},
 Option:class{constructor(text,value){this.text=text;this.value=value;}},Image:class{set src(v){queueMicrotask(()=>this.onload());}},
 localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},
 URL:{createObjectURL:b=>{blob=b;return 'blob:review';},revokeObjectURL(){}},
 fetch:async (name,options)=>{requested.push(name);
 if(name==='/api/bulk-preview'||name==='/api/bulk-apply'||name==='/api/validate'){
  const body=JSON.parse(options.body);
  if(name==='/api/bulk-preview'&&previewFailure)return {ok:true,json:async()=>({annotationCount:57,previewToken:'old',affected:[{frameIndex:46,physicalPaws:['A']}],excluded:[]})};
  try {const result=cp.execFileSync('python',['-c',`import json,sys
from training.review_paw_annotations import bulk_preview,bulk_apply,review_diagnostics
b,body,endpoint=json.load(sys.stdin)
print(json.dumps(review_diagnostics(b,body) if endpoint.endswith('validate') else bulk_preview(b,body) if endpoint.endswith('preview') else bulk_apply(b,body['draft'],body)))`],{input:JSON.stringify([base,body,name]),maxBuffer:4e6});return {ok:true,json:async()=>JSON.parse(result)};
  }catch(e){return {ok:false,text:async()=>String(e.stderr)};}
 }
if(name==='/api/session')return {json:async()=>structuredClone(base)};
 if(name.startsWith('/api/predictions')){const s=base.sourceConfiguration.sequences.find(s=>s.group===group);return {json:async()=>JSON.parse(fs.readFileSync(path.resolve(__dirname,'..',s.predictions.path)))};}
 const file=name==='dog02/manifest.json'?'dog02/evaluation-manifest.json':name;
 return {json:async()=>JSON.parse(fs.readFileSync(path.join(root,file)))};}};
 vm.createContext(sandbox);
 for(const name of ['physical-tracks.js','review.js','annotation.js']){let js=fs.readFileSync(name==='review.js'?path.resolve(__dirname,'../training/paw-review.js'):path.join(root,name),'utf8');if(name==='annotation.js')js=js.replace('boot().catch(error);','boot().then(()=>pawReview.boot()).catch(error);');vm.runInContext(js,sandbox);}
 const run=s=>vm.runInContext(s,sandbox);
 for(let i=0;i<20;i++)await new Promise(setImmediate);
 assert.equal(el('error').textContent,'');assert.equal(run('current'),group==='dalmatian'?46:2);
 assert.equal(run('queue().length'),group==='dalmatian'?42:28);
 assert.equal(requested.some(n=>n.startsWith('/api/predictions')),false);
 el('draftDownload').onclick();let draft=JSON.parse(await blob.text());assert.equal(draft.reviews.filter(e=>e.identityState==='verified').length,0);
 await el('reviewCheck').onclick();assert.match(el('reviewDiagnostics').textContent,/passes export validation/);
 el('reviewDiagnosticsDownload').onclick();assert.equal(JSON.parse(await blob.text()).valid,true);
 if(group==='dalmatian'){
  const originalDraft=structuredClone(draft);
  assert.equal(el('bulkSummary').textContent,'');
  previewFailure=true;await el('bulkPreview').onclick();
  assert.match(el('bulkSummary').textContent,/Preview failed: Incompatible preview response/);
  el('bulkConfirm').checked=true;el('bulkConfirm').onchange();assert.equal(el('bulkApply').disabled,true);
  el('draftDownload').onclick();assert.deepEqual(JSON.parse(await blob.text()),originalDraft);
  previewFailure=false;
  await el('bulkPreview').onclick();
  assert.match(el('bulkSummary').textContent,/42 affected frames; 79 annotations/);
  assert.match(el('bulkSummary').textContent,/Frame 75/);
  assert.match(el('bulkSummary').textContent,/not independently verified/);
  assert.match(el('bulkSummary').textContent,/Frame 90/);
  assert.equal(el('bulkConfirm').checked,false);
  await el('bulkApply').onclick();assert.match(el('error').textContent,/confirmation required/);
  el('error').textContent='';
  el('draftDownload').onclick();assert.equal(JSON.parse(await blob.text()).reviews.filter(e=>e.identityState==='verified').length,0);
  el('bulkReviewer').value='human';el('bulkEvidence').value='Leg anatomy followed through temporal context';
  el('bulkConfirm').checked=true;el('bulkConfirm').onchange();assert.equal(el('bulkApply').disabled,false);
  await el('bulkApply').onclick();assert.equal(el('error').textContent,'');
  el('draftDownload').onclick();const assigned=JSON.parse(await blob.text());
  assert.equal(assigned.reviews.filter(e=>e.identitySource==='human-confirmed-mapping').length,79);
  assert.equal(assigned.bulkAssignments.length,1);assert.equal(el('bulkApply').disabled,true);
  el('reviewImport').files=[{text:async()=>JSON.stringify(originalDraft)}];await el('reviewImport').onchange();
  await el('bulkPreview').onclick();run('physicalTracks.point(200,300)');
  el('bulkConfirm').checked=true;await el('bulkApply').onclick();assert.match(el('error').textContent,/Review changed/);
  el('reviewImport').files=[{text:async()=>JSON.stringify(originalDraft)}];await el('reviewImport').onchange();el('error').textContent='';
  const incomplete=structuredClone(originalDraft);
  const point=incomplete.reviews.find(e=>e.frameIndex===46&&e.physicalPaw==='A'&&e.datasetId.includes('dalmatian'));
  point.identityState='verified';point.anatomicalKeypoint='right_back_paw';
  el('reviewImport').files=[{text:async()=>JSON.stringify(incomplete)}];await el('reviewImport').onchange();
  await el('reviewCheck').onclick();assert.match(el('reviewDiagnostics').textContent,/frame 46 · paw A: missing reviewer, evidence, landmarkConfirmed, continuityConfirmed/);
  el('reviewDiagnosticsDownload').onclick();const report=JSON.parse(await blob.text());assert.equal(report.valid,false);assert.equal(report.incompleteReviews.length,1);
  el('draftDownload').onclick();assert.deepEqual(JSON.parse(await blob.text()),incomplete);
  el('reviewImport').files=[{text:async()=>JSON.stringify(originalDraft)}];await el('reviewImport').onchange();el('error').textContent='';
  draft=originalDraft;
 }
 let e=draft.reviews.find(e=>e.datasetId===run('manifest.datasetId')&&e.frameIndex===run('current')&&e.physicalPaw==='A');
 const original=structuredClone(e.correctedLabel);e.identityState='verified';e.anatomicalKeypoint='left_back_paw';e.landmarkConfirmed=true;e.continuityConfirmed=true;e.reviewer='test';e.evidence='temporal anatomy';
 el('reviewImport').files=[{text:async()=>JSON.stringify(draft)}];await el('reviewImport').onchange();assert.equal(el('error').textContent,'');
 run('physicalTracks.point(200,300)');el('draftDownload').onclick();draft=JSON.parse(await blob.text());
 e=draft.reviews.find(e=>e.datasetId===run('manifest.datasetId')&&e.frameIndex===run('current')&&e.physicalPaw==='A');assert.equal(e.correctedLabel.x,200);assert.equal(e.identityState,'unreviewed');assert.equal(e.anatomicalKeypoint,null);assert.equal(e.landmarkConfirmed,false);
 const r=base.records.find(r=>r.datasetId===e.datasetId&&r.frameIndex===e.frameIndex);assert.deepEqual(r.human.A,original);
 await el('reviewModel').onclick();assert.equal(el('error').textContent,'');el('draftDownload').onclick();draft=JSON.parse(await blob.text());assert(draft.reviews.some(e=>e.modelExposed));
 el('queue').value='all';assert.equal(run('queue().length'),group==='dalmatian'?177:60);
 await run('load(manifest.frameCount-1)');assert.equal(el('error').textContent,'');
 console.log('PASS '+group+': existing UI boot, original-label seed, priority/all queues, draft import, coordinate correction invalidates verification, original preserved, explicit saved prediction reveal.');
}
(async()=>{await test('dalmatian');await test('dog02');})().catch(e=>{console.error(e);process.exitCode=1;});
