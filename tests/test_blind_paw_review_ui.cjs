// Exercise Husky mode using the existing canvas/navigation helpers and actual review extension.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const manifestPath=path.join(root,'reports/husky-evaluation/annotation-manifest-v1.json');
const config=JSON.parse(fs.readFileSync(manifestPath));
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const blank=()=>({status:'unmarked',x:null,y:null});
const records=config.frames.filter(f=>f.sample).map(f=>({datasetId:config.datasetId,group:'husky-evaluation',split:'exploratory_evaluation',frameIndex:f.frameIndex,timestampSeconds:f.timestampSeconds,width:config.frameWidth,height:config.frameHeight,imageSha256:f.sample.sha256,human:{A:blank(),B:blank(),modelExposed:false}}));
const base={schemaVersion:1,annotationType:'blind-hind-paw-evaluation',blind:true,referenceSha256:hash(fs.readFileSync(manifestPath)),sourceConfiguration:config,records};
base.draft={schemaVersion:1,annotationType:base.annotationType,blind:true,referenceSha256:base.referenceSha256,sourceConfiguration:structuredClone(config),reviewer:'',reviews:records.flatMap(r=>['A','B'].map(paw=>({datasetId:r.datasetId,frameIndex:r.frameIndex,physicalPaw:paw,originalLabelSha256:hash(JSON.stringify(blank())),imageSha256:r.imageSha256,correctedLabel:blank(),identityState:'unreviewed',anatomicalKeypoint:null,landmarkConfirmed:false,continuityConfirmed:false,modelExposed:false,reviewer:'',evidence:''})))};

async function test(){
 const els=new Map(),store=new Map([['petlens-anatomical-review-v2:legacy','DO NOT CHANGE']]),requested=[],imageURLs=[];
 let blob,exportBody;
 const ctx={drawImage(){},clearRect(){},beginPath(){},arc(){},stroke(){},fillText(){},moveTo(){},lineTo(){}};
 function el(id){if(els.has(id))return els.get(id);const e={id,value:'',textContent:'',children:[],style:{},files:[],clientLeft:2,clientTop:2,width:852,height:480,
  append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=[...xs];this.value=xs[0]?.value||'';},add(x){this.children.push(x);if(this.children.length===1)this.value=x.value;},setAttribute(k,v){this[k]=v;},closest(){return el('details');},insertAdjacentHTML(){},getContext(){return {...ctx,canvas:this};},getBoundingClientRect(){return {left:0,top:0,width:856,height:484};},click(){}};els.set(id,e);return e;}
 el('speed').value='0.1';el('queue').value='selected';
 const sandbox={console,URLSearchParams,location:{search:'?dataset=husky-evaluation'},structuredClone,Blob,Date,setTimeout,clearTimeout,
  document:{getElementById:el,createElement:t=>{const e=el('new'+Math.random());e.tagName=t.toUpperCase();return e;},createTextNode:t=>({textContent:t}),querySelector:()=>el('warning'),addEventListener(){}},
  Option:class{constructor(text,value){this.text=text;this.value=value;}},Image:class{set src(v){imageURLs.push(v);queueMicrotask(()=>this.onload());}},
  localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},
  URL:{createObjectURL:b=>{blob=b;return 'blob:blind-review';},revokeObjectURL(){}},
  fetch:async(name,options)=>{requested.push(name);if(name==='/api/session?group=husky-evaluation')return {ok:true,json:async()=>structuredClone(base)};
   if(name==='/api/export?group=husky-evaluation'){exportBody=JSON.parse(options.body);return {ok:true,headers:{get:()=> 'reports/husky-evaluation/annotations/test-version.zip'},blob:async()=>new Blob(['test export'])};}
   throw Error('Unexpected request during blind review: '+name);}};
 vm.createContext(sandbox);
 vm.runInContext(fs.readFileSync(path.join(root,'training/paw-review.js'),'utf8'),sandbox);
 // Boot the blind extension with the existing shared functions; no legacy boot or manifests.
 const js=process.argv[2]?fs.readFileSync(process.argv[2],'utf8'):fs.readFileSync(path.join(root,'tmp/rtmpose-test/paw-tracking-experiment/manual-annotation/annotation.js'),'utf8').replace('boot().catch(error);','pawReview.bootBlind().catch(error);');
 vm.runInContext(js,sandbox);
 const run=s=>vm.runInContext(s,sandbox);
 for(let i=0;i<15;i++)await new Promise(setImmediate);
 assert.equal(el('error').textContent,'');
 assert.equal(run('current'),0);assert.equal(run('queue().length'),20);
 assert.equal(el('image').width,1228);assert.equal(el('image').height,754);
 assert.equal(el('adjudication').hidden,true);assert.equal(el('reviewModel').hidden,true);
 assert.deepEqual(requested,['/api/session?group=husky-evaluation']);
 el('draftDownload').onclick();let draft=JSON.parse(await blob.text());
 assert.equal(draft.reviews.length,40);assert(draft.reviews.every(e=>e.correctedLabel.status==='unmarked'&&e.anatomicalKeypoint===null));
 el('image').onclick({clientX:428,clientY:242});
 el('draftDownload').onclick();draft=JSON.parse(await blob.text());
 let entry=draft.reviews.find(e=>e.frameIndex===0&&e.physicalPaw==='A');
 assert.deepEqual(entry.correctedLabel,{status:'visible',x:614,y:377});assert.equal(entry.anatomicalKeypoint,null);
 // Anatomical uncertainty is independent of a visible point's coordinates.
 let row=el('paws').children[0],identitySelect=row.children.find(e=>e.tagName==='SELECT');
 identitySelect.value='uncertain';identitySelect.onchange();
 row=el('paws').children[1];let selects=row.children.filter(e=>e.tagName==='SELECT');
 selects[1].value='occluded';selects[1].onchange();
 el('blindReviewer').value='Human reviewer';el('blindReviewer').oninput();
 el('draftDownload').onclick();const marked=JSON.parse(await blob.text());
 entry=marked.reviews.find(e=>e.frameIndex===0&&e.physicalPaw==='A');
 assert.equal(entry.identityState,'uncertain');assert.equal(entry.correctedLabel.status,'visible');assert.equal(entry.anatomicalKeypoint,null);
 assert.equal(marked.reviews.find(e=>e.frameIndex===0&&e.physicalPaw==='B').correctedLabel.status,'occluded');
 el('queue').value='all';assert.equal(run('queue().length'),63);await run('load(1)');
 el('image').onclick({clientX:428,clientY:242});el('draftDownload').onclick();
 assert.deepEqual(JSON.parse(await blob.text()),marked);assert.equal(el('paws').children.length,0);
 await run('load(62)');assert.match(imageURLs.at(-1),/group=husky-evaluation&index=62/);
 await el('showModel').onclick();assert.match(el('error').textContent,/disabled/);assert.equal(run('model'),null);
 el('reviewImport').files=[{text:async()=>JSON.stringify(marked)}];await el('reviewImport').onchange();
 assert.equal(el('error').textContent,'');await el('reviewExport').onclick();
 assert.deepEqual(exportBody,marked);assert.match(el('reviewStatus').textContent,/reports\/husky-evaluation\/annotations\/test-version.zip/);
 const bad=structuredClone(marked);bad.reviews[0].modelExposed=true;
 el('reviewImport').files=[{text:async()=>JSON.stringify(bad)}];await el('reviewImport').onchange();assert.match(el('error').textContent,/exposed/);
 el('draftDownload').onclick();assert.deepEqual(JSON.parse(await blob.text()),marked);
 assert.equal(store.get('petlens-anatomical-review-v2:legacy'),'DO NOT CHANGE');
 assert([...store.keys()].filter(k=>k!=='petlens-anatomical-review-v2:legacy').every(k=>k.startsWith('petlens-blind-hind-review-v1:')));
 assert(requested.every(url=>!url.includes('predictions')));
 assert(imageURLs.every(url=>url.startsWith('/api/frame?group=husky-evaluation&index=')));
 console.log('PASS Husky UI: shared canvas/navigation, 20 samples, 63 context frames, coordinate scaling, visible uncertain identity, occlusion, draft resume, separate storage/export, and no prediction requests.');
}
test().catch(e=>{console.error(e);process.exitCode=1;});
