'use strict';
globalThis.pawReview = (() => {
 let base, draft, group, selected='A', key, targets, blind=false, exposed=new Set();
 const entries=i=>draft.reviews.filter(e=>e.datasetId===manifest.datasetId&&e.frameIndex===i);
 const entry=()=>entries(current).find(e=>e.physicalPaw===selected);
 function download(value,name,type='application/json') {const url=URL.createObjectURL(new Blob([value],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function save(){try{localStorage.setItem(key,JSON.stringify(draft));$('reviewStatus').textContent='Review autosaved locally. Download a draft backup regularly.';}catch(e){$('reviewStatus').textContent='Autosave failed. Download draft now.';}}
 function clearBulk(e){delete e.identitySource;delete e.bulkAssignmentId;}
 function invalidate(e){clearBulk(e);e.identityState='unreviewed';e.anatomicalKeypoint=null;e.landmarkConfirmed=false;e.continuityConfirmed=false;}
 function updatePoint(x,y){const e=entry();if(!e)return; e.correctedLabel={status:'visible',x,y};invalidate(e);save();showLabels();paint();}
 function markers(ctx,i){for(const e of entries(i)){const v=e.correctedLabel;if(v.status!=='visible')continue;ctx.strokeStyle=ctx.fillStyle=e.physicalPaw==='A'?'#ffee66':'#ff88dd';ctx.lineWidth=3;const x=v.x*ctx.canvas.width/manifest.frameWidth,y=v.y*ctx.canvas.height/manifest.frameHeight;ctx.beginPath();ctx.arc(x,y,10,0,2*Math.PI);ctx.stroke();ctx.fillText(`${e.physicalPaw} · ${e.identityState==='verified'?e.anatomicalKeypoint:e.identityState}`,x+12,y-12);}}
 function labels(){
  $('paws').replaceChildren();
  for(const e of entries(current)){
   const row=document.createElement('div');row.className='card';
   const b=document.createElement('button');b.textContent=(selected===e.physicalPaw?'● ':'')+'Physical '+e.physicalPaw;b.onclick=()=>{stopPlayback();selected=e.physicalPaw;labels();};row.append(b);
   const original=base.records.find(r=>r.datasetId===e.datasetId&&r.frameIndex===current).human[e.physicalPaw];
   const info=document.createElement('p');info.textContent=`Original: ${JSON.stringify(original)} → Current: ${JSON.stringify(e.correctedLabel)}`;row.append(info);
   const select=document.createElement('select');select.setAttribute('aria-label',e.physicalPaw+' anatomical identity');
   for(const [v,t] of [['unreviewed','Unreviewed'],['uncertain','Uncertain'],['left_back_paw','Anatomical left hind'],['right_back_paw','Anatomical right hind']])select.add(new Option(t,v));
   select.value=e.anatomicalKeypoint||e.identityState;
   select.onchange=()=>{stopPlayback();clearBulk(e);const val=select.value;e.identityState=['unreviewed','uncertain'].includes(val)?val:'verified';e.anatomicalKeypoint=e.identityState==='verified'?val:null;save();paint();};row.append(select);
   const visibility=document.createElement('select');visibility.setAttribute('aria-label',e.physicalPaw+' visibility');
   for(const v of ['visible','occluded','uncertain','ambiguous','unmarked'])visibility.add(new Option(v,v));visibility.value=e.correctedLabel.status;
   visibility.onchange=()=>{stopPlayback();selected=e.physicalPaw;if(visibility.value==='visible'&&e.correctedLabel.status!=='visible'){error('Click the selected paw to place a coordinate.');labels();return;}e.correctedLabel={status:visibility.value,x:visibility.value==='visible'?e.correctedLabel.x:null,y:visibility.value==='visible'?e.correctedLabel.y:null};invalidate(e);save();labels();paint();};row.append(visibility);
   for(const [field,text] of [['landmarkConfirmed','Same visible paw-tip landmark confirmed'],['continuityConfirmed','Physical identity followed in temporal context']]){const label=document.createElement('label'),c=document.createElement('input');c.type='checkbox';c.checked=e[field];c.onchange=()=>{stopPlayback();clearBulk(e);e[field]=c.checked;save();};label.append(c,document.createTextNode(text));row.append(label);}
   for(const [field,placeholder] of [['reviewer','Reviewer ID'],['evidence','Anatomical evidence, context frames and correction reason']]){if(blind&&field==='reviewer')continue;const input=document.createElement(field==='evidence'?'textarea':'input');input.placeholder=blind?'Optional location notes; evidence required for an anatomical assertion':placeholder;input.setAttribute('aria-label',e.physicalPaw+' '+field);input.value=e[field];input.oninput=()=>{stopPlayback();clearBulk(e);e[field]=input.value;save();};row.append(input);}
   $('paws').append(row);
  }
  $('frameStatus').textContent=entries(current).length?(blind?'Click the selected A/B hind-paw tip. Visible coordinates can have uncertain anatomical identity.':'Click the selected A/B paw to correct its coordinate. Any coordinate edit resets its verification.'):'Context frame only. Use the sampled-point queue to edit labels.';
  $('progress').textContent=blind?`${targets.filter(i=>entries(i).every(e=>e.correctedLabel.status!=='unmarked')).length}/${targets.length} sampled frames marked for both paws`:`${draft.reviews.filter(e=>e.datasetId===manifest.datasetId&&e.identityState==='verified').length} identity decisions / ${targets.length} annotated frames (export validates all decisions)`;
 }
 async function boot(){
  if(blind)return;
  stopPlayback();base=await (await fetch('/api/session')).json();group=datasetBase==='dog02/'?'dog02':'dalmatian';
  if(datasetBase!==group+'/'){location.search='?dataset=dalmatian';return;}
  key='petlens-anatomical-review-v2:'+base.referenceSha256;
  draft={schemaVersion:2,annotationType:base.annotationType,referenceSha256:base.referenceSha256,sourceConfiguration:base.sourceConfiguration,reviews:base.records.flatMap(r=>['A','B'].map(paw=>({datasetId:r.datasetId,frameIndex:r.frameIndex,physicalPaw:paw,originalLabelSha256:r.labelHashes[paw],imageSha256:r.imageSha256,correctedLabel:structuredClone(r.human[paw]),identityState:'unreviewed',anatomicalKeypoint:null,landmarkConfirmed:false,continuityConfirmed:false,modelExposed:r.human.modelExposed,reviewer:'',evidence:''})))};
  const stored=localStorage.getItem(key);if(stored){const d=JSON.parse(stored);if(d.referenceSha256!==base.referenceSha256)throw Error('Stale draft');draft=d;}
  targets=base.records.filter(r=>r.group===group&&['A','B'].some(p=>r.human[p].status==='visible')).map(r=>r.frameIndex);
  $('annotationIntro').textContent=`Anatomical review · ${group==='dalmatian'?'Dalmatian: 79 training points first':'dog02: exploratory evaluation only'}. Follow connected leg anatomy through time; A/B remain physical track names. Never decide identity using RTMPose labels. Leave unresolved points uncertain.`;
  document.querySelector('.warning').textContent='Original labels are preserved. Review corrections export separately. Anatomical decisions apply to one physical paw in one frame; bulk mappings require a safe preview and explicit human confirmation.';
  $('physicalControls').hidden=true;$('adjudication').hidden=true;$('clearPaw').hidden=true;$('frameNotes').disabled=true;
  $('annotationIntro').insertAdjacentHTML('afterend','<div class="card"><button id="draftDownload">Download draft JSON</button><label>Resume draft <input type="file" id="reviewImport" accept=".json"></label><button id="reviewCheck">Check incomplete reviews</button><button id="reviewDiagnosticsDownload" disabled>Download validation report</button><pre id="reviewDiagnostics" aria-live="polite"></pre><button id="reviewExport">Validate & download versioned export</button><button id="reviewModel">Reveal saved predictions for this frame</button><p id="reviewStatus" aria-live="polite"></p></div>');
  if(group==='dalmatian'){
   $('annotationIntro').insertAdjacentHTML('afterend',`<div class="card" id="bulkMapping">
    <p>Bulk human mapping · frames 46–90 (source frame indices, inclusive): Physical A = Right hind paw; Physical B = Left hind paw.</p>
    <p>Only unchanged visible labels qualify. Continuity for frames 75–90 is reviewer-provided evidence, not independently verified. Existing decisions are preserved. A gap, swap or ambiguity stops propagation through the remaining range.</p>
    <label>Reviewer ID <input id="bulkReviewer"></label>
    <label>Anatomical evidence and context <textarea id="bulkEvidence"></textarea></label>
    <button id="bulkPreview">Preview affected frames and counts</button>
    <pre id="bulkSummary" aria-live="polite"></pre>
    <label><input type="checkbox" id="bulkConfirm">I confirm A = Right hind and B = Left hind, visible paw-tip landmarks, and physical continuity for the previewed annotations.</label>
    <button id="bulkApply" disabled>Apply confirmed human mapping</button>
   </div>`);
   let preview, snapshot;
   async function post(url,body){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok)throw Error(`${url}: ${await response.text()}`);return response.json();}
   $('bulkConfirm').onchange=()=>{$('bulkApply').disabled=!preview||!preview.annotationCount||!$('bulkConfirm').checked;};
   $('bulkPreview').onclick=async()=>{stopPlayback();preview=null;$('bulkConfirm').checked=false;$('bulkApply').disabled=true;$('bulkSummary').textContent='Generating preview…';$('error').textContent='';try{
    snapshot=JSON.stringify(draft);const candidate=await post('/api/bulk-preview',draft);
    if(typeof candidate.previewToken!=='string'||!Number.isInteger(candidate.annotationCount)||!Array.isArray(candidate.affected)||!Array.isArray(candidate.excluded)||candidate.affected.some(a=>!Array.isArray(a.annotations)))throw Error('Incompatible preview response. Restart the review server and reload this page; your browser draft is preserved.');
    if(snapshot!==JSON.stringify(draft))throw Error('Review changed while preview was loading; preview again.');
    preview=candidate;
    $('bulkSummary').textContent=`${preview.frameCount} affected frames; ${preview.annotationCount} annotations.\n`+
     (preview.continuityEvidence?`Reviewer-provided continuity, frames 75–90 (not independently verified): ${preview.continuityEvidence.statement}\n`:'')+
     preview.affected.map(a=>`Frame ${a.frameIndex}: ${a.annotations.map(e=>`${e.physicalPaw} → ${e.anatomicalKeypoint} at (${e.label.x}, ${e.label.y})`).join('; ')} [${a.continuitySource}]`).join('\n')+
     '\nExclusions:\n'+preview.excluded.map(a=>`Frame ${a.frameIndex}${a.physicalPaw?' '+a.physicalPaw:''}: ${a.reason}`).join('\n');
   }catch(e){preview=null;$('bulkApply').disabled=true;$('bulkSummary').textContent='Preview failed: '+String(e.message||e);error(e);}};
   $('bulkApply').onclick=async()=>{stopPlayback();try{
    if(!preview||!$('bulkConfirm').checked)throw Error('Preview and explicit confirmation required.');
    if(snapshot!==JSON.stringify(draft))throw Error('Review changed; preview and confirm again.');
    const result=await post('/api/bulk-apply',{draft,previewToken:preview.previewToken,confirmed:true,reviewer:$('bulkReviewer').value,evidence:$('bulkEvidence').value});
    draft=result;preview=null;$('bulkConfirm').checked=false;$('bulkApply').disabled=true;save();labels();paint();
    $('bulkSummary').textContent='Human-confirmed mapping applied locally. Validate & download the versioned export to save the audit and original annotations.';
   }catch(e){error(e);}};
  }
  $('download').closest('details').hidden=true;
  $('queue').replaceChildren(new Option('Existing visible human points (priority)','selected'),new Option('All frames: continuous context','all'));$('queue').value='selected';manifest.selectedFrames=targets;
  // Reuse the existing canvas, click scaling, playback, navigation and marker hooks.
  globalThis.physicalTracks={enabled:()=>true,labels,markers,point:updatePoint};
  showLabels=labels;
  image=async i=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Original frame unavailable or hash mismatch'));im.src=`/api/frame?group=${group}&index=${i}`;});
  const originalPaint=paint;paint=()=>{originalPaint();if(exposed.has(current)&&originalImage&&model)markersWithModel();};
  function markersWithModel(){const ctx=$('image').getContext('2d');for(const p of model.frames.find(f=>f.frameIndex===current)?.keypoints||[]){if(!['left_back_paw','right_back_paw'].includes(p.name))continue;const x=p.x*ctx.canvas.width/manifest.frameWidth,y=p.y*ctx.canvas.height/manifest.frameHeight;ctx.strokeStyle=ctx.fillStyle='#5eeaff';ctx.beginPath();ctx.moveTo(x-8,y-8);ctx.lineTo(x+8,y+8);ctx.moveTo(x-8,y+8);ctx.lineTo(x+8,y-8);ctx.stroke();ctx.fillText('MODEL '+p.name,x+12,y+20);}}
  $('reviewModel').onclick=async()=>{try{if(!model)model=await(await fetch('/api/predictions?group='+group)).json();exposed.add(current);for(const e of entries(current))e.modelExposed=true;save();paint();}catch(e){error(e);}};
  $('draftDownload').onclick=()=>download(JSON.stringify(draft,null,2),'petlens-anatomical-review-v2-draft.json');
  $('reviewImport').onchange=async()=>{try{const file=$('reviewImport').files[0];if(!file)return;const d=JSON.parse(await file.text());if(d.schemaVersion!==2||d.referenceSha256!==base.referenceSha256||JSON.stringify(d.sourceConfiguration)!==JSON.stringify(base.sourceConfiguration)||!Array.isArray(d.reviews)||d.reviews.length!==draft.reviews.length)throw Error('Wrong review source or format');const slots=new Map(draft.reviews.map(e=>[`${e.datasetId}:${e.frameIndex}:${e.physicalPaw}`,e]));for(const e of d.reviews){const id=`${e.datasetId}:${e.frameIndex}:${e.physicalPaw}`,old=slots.get(id);if(!old||old.originalLabelSha256!==e.originalLabelSha256||old.imageSha256!==e.imageSha256||!e.correctedLabel||typeof e.reviewer!=='string'||typeof e.evidence!=='string')throw Error('Invalid or stale draft label');slots.delete(id);}draft=d;exposed.clear();save();labels();paint();}catch(e){error(e);}};
  let diagnostics;
  $('reviewCheck').onclick=async()=>{stopPlayback();diagnostics=null;$('reviewDiagnosticsDownload').disabled=true;try{
   const snapshot=JSON.stringify(draft),response=await fetch('/api/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:snapshot});
   if(!response.ok)throw Error(await response.text());const report=await response.json();
   if(snapshot!==JSON.stringify(draft))throw Error('Review changed during validation; check again.');
   diagnostics=report;$('reviewDiagnosticsDownload').disabled=false;
   $('reviewDiagnostics').textContent=(report.valid?'Current draft passes export validation.':'Export blocked. Existing decisions and coordinates are preserved.')+'\n'+
    report.incompleteReviews.map(e=>`${e.datasetId} · frame ${e.frameIndex} · paw ${e.physicalPaw}: missing ${e.missing.join(', ')}`).join('\n')+'\n'+report.errors.join('\n')+'\n'+report.note;
  }catch(e){$('reviewDiagnostics').textContent='Validation failed: '+String(e.message||e);error(e);}};
  $('reviewDiagnosticsDownload').onclick=()=>{if(diagnostics)download(JSON.stringify(diagnostics,null,2),'petlens-paw-review-validation.json');};
  $('reviewExport').onclick=async()=>{stopPlayback();try{const response=await fetch('/api/export',{method:'POST',body:JSON.stringify(draft)});if(!response.ok)throw Error(await response.text());download(await response.blob(),`petlens-paw-review-v2-${new Date().toISOString().replace(/[:.]/g,'-')}.zip`,'application/zip');$('reviewStatus').textContent='Validated export downloaded. Originals were not changed.';$('error').textContent='';}catch(e){error(e);}};
  $('imageHelp').textContent='Select A or B, then click to correct the visible paw tip. Arrows follow the selected queue. Use All frames and slow playback to follow each physical paw through crossings.';
  await load(targets[0]);
 }
 async function bootBlind(){
  stopPlayback();blind=true;group='husky-evaluation';
  const response=await fetch('/api/session?group='+group);
  if(!response.ok)throw Error(await response.text());
  base=await response.json();manifest=structuredClone(base.sourceConfiguration);
  if(base.annotationType!=='blind-hind-paw-evaluation'||base.blind!==true||manifest.group!==group)throw Error('Wrong blind evaluation session');
  targets=manifest.selectedFrames;draft=structuredClone(base.draft);
  key='petlens-blind-hind-review-v1:'+manifest.datasetId+':'+base.referenceSha256;
  function checkDraft(d){
   if(d.annotationType!==base.annotationType||d.referenceSha256!==base.referenceSha256||d.blind!==true||JSON.stringify(d.sourceConfiguration)!==JSON.stringify(base.sourceConfiguration)||typeof d.reviewer!=='string'||!Array.isArray(d.reviews)||d.reviews.length!==base.draft.reviews.length)throw Error('Wrong Husky draft provenance');
   const slots=new Map(base.draft.reviews.map(e=>[`${e.datasetId}:${e.frameIndex}:${e.physicalPaw}`,e]));
   for(const e of d.reviews){const k=`${e.datasetId}:${e.frameIndex}:${e.physicalPaw}`,old=slots.get(k);if(!old||e.imageSha256!==old.imageSha256||e.originalLabelSha256!==old.originalLabelSha256||e.modelExposed!==false||!e.correctedLabel||!['unreviewed','uncertain','verified'].includes(e.identityState))throw Error('Invalid or exposed Husky draft label');slots.delete(k);}
   return d;
  }
  const stored=localStorage.getItem(key);
  if(stored){try{draft=checkDraft(JSON.parse(stored));}catch(e){throw Error('Stored Husky draft is invalid; it was preserved. '+e.message);}}
  // Existing canvas, original-frame loader, click scaling and queue navigation.
  data={frames:{},transitions:{}};model=null;reveal=false;pairImages=null;
  for(const id of ['image','before','after']){$(id).width=manifest.frameWidth;$(id).height=manifest.frameHeight;}
  $('frame').max=manifest.frameCount-1;
  $('queue').replaceChildren(new Option('20 blind annotation samples','selected'),new Option('All 63 prepared frames: context only','all'));$('queue').value='selected';
  $('annotationIntro').textContent='Blind Husky evaluation only. Mark physical hind paws A/B; they do not imply anatomical left/right. Click visible paw tips, mark occluded paws, and leave uncertain identities unresolved. Use neighboring original frames for context. No training or tuning on this clip.';
  document.querySelector('.warning').textContent='Predictions cannot be revealed in Husky review. The source range/container implies 64 frames, but only 63 decode; use prepared indices 0-62. Screen-record timestamps do not validate gait timing.';
  $('sourceAttribution').textContent='Verified: all 20 sampled PNGs match prepared-video pixels and timestamps. Original source-frame correspondence remains unresolved.';
  $('annotationIntro').insertAdjacentHTML('afterend','<div class="card"><label>Reviewer ID <input id="blindReviewer" placeholder="Required for validated export"></label><button id="draftDownload">Download draft backup</button><label>Resume Husky draft <input type="file" id="reviewImport" accept=".json"></label><button id="reviewExport">Validate, save & download versioned evaluation export</button><p id="reviewStatus" aria-live="polite"></p></div>');
  $('blindReviewer').value=draft.reviewer;$('blindReviewer').oninput=()=>{draft.reviewer=$('blindReviewer').value;save();};
  $('download').closest('details').hidden=true;
  for(const id of ['physicalControls','adjudication','clearPaw','reviewModel'])if($(id))$(id).hidden=true;
  $('frameNotes').disabled=true;
  $('eventHelp').textContent='No gait events are collected. A/B are reviewer-defined physical paws; anatomy may remain uncertain even when the paw tip is visible.';
  $('imageHelp').textContent='Original 1228 x 754 pixels. Select Physical A or B, then click the paw tip. Arrows step the chosen queue. All frames provides context; only the 20 samples accept annotations. Download backups before closing the browser.';
  globalThis.physicalTracks={enabled:()=>true,labels,markers,point:updatePoint};showLabels=labels;
  image=async i=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Verified original Husky frame unavailable'));im.src=`/api/frame?group=${group}&index=${i}`;});
  $('image').onclick=e=>{if(!originalImage||!entry())return;const rect=$('image').getBoundingClientRect();const x=Math.max(0,Math.min(manifest.frameWidth-0.0001,(e.clientX-rect.left-$('image').clientLeft)/(rect.width-2*$('image').clientLeft)*manifest.frameWidth));const y=Math.max(0,Math.min(manifest.frameHeight-0.0001,(e.clientY-rect.top-$('image').clientTop)/(rect.height-2*$('image').clientTop)*manifest.frameHeight));stopPlayback();updatePoint(x,y);};
  $('prev').onclick=()=>move(-1);$('next').onclick=()=>move(1);
  $('go').onclick=()=>{stopPlayback();load(Number($('frame').value)).catch(error);};
  $('queue').onchange=()=>{stopPlayback();load(queue()[0]).catch(error);};
  playStep=async()=>{if(!playing)return;const next=queue().find(i=>i>current);if(next===undefined){stopPlayback();return;}const elapsed=manifest.frames[next].timestampSeconds-manifest.frames[current].timestampSeconds;try{await load(next);}catch(e){stopPlayback();error(e);return;}if(playing)playbackTimer=setTimeout(playStep,elapsed*1000/Number($('speed').value));};
  $('play').onclick=togglePlayback;$('speed').onchange=()=>{if(playing){stopPlayback();togglePlayback();}};
  if($('fitFrame'))$('fitFrame').onchange=()=>{$('image').style.maxHeight=$('fitFrame').checked?'':'none';};
  const noModel=()=>{stopPlayback();error('Model predictions are disabled for blind Husky evaluation.');};
  $('showModel').onclick=noModel;if($('reviewModel'))$('reviewModel').onclick=noModel;
  $('draftDownload').onclick=()=>download(JSON.stringify(draft,null,2),'petlens-husky-evaluation-draft.json');
  $('reviewImport').onchange=async()=>{stopPlayback();try{const file=$('reviewImport').files[0];if(!file)return;const incoming=checkDraft(JSON.parse(await file.text()));draft=incoming;$('blindReviewer').value=draft.reviewer;save();labels();paint();$('error').textContent='';}catch(e){error(e);}};
  $('reviewExport').onclick=async()=>{stopPlayback();try{
   const snapshot=JSON.stringify(draft),response=await fetch('/api/export?group='+group,{method:'POST',headers:{'Content-Type':'application/json'},body:snapshot});
   if(!response.ok)throw Error(await response.text());
   const path=response.headers.get('X-PetLens-Export-Path');
   download(await response.blob(),path.split('/').at(-1),'application/zip');
   $('reviewStatus').textContent='Validated human evaluation export saved to '+path+'. Unreviewed/uncertain labels are retained. Training data unchanged.';$('error').textContent='';
  }catch(e){error(e);}};
  document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)||e.target.isContentEditable)return;if(['ArrowLeft','ArrowRight'].includes(e.key))e.preventDefault?.();if(e.key==='ArrowRight')move(1);if(e.key==='ArrowLeft')move(-1);});
  await load(targets[0]);
 }
 return {boot,bootBlind};
})();
