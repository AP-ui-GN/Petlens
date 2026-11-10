'use strict';
const names=['LF','RF','LH','RH'];
const modelNames={LF:'left_front_paw',RF:'right_front_paw',LH:'left_back_paw',RH:'right_back_paw'};
const colors={LF:'#46dc46',RF:'#28beff',LH:'#e650e6',RH:'#ff8c1e'};
const $=id=>document.getElementById(id);
const datasetBase=new URLSearchParams(globalThis.location?.search||'').get('dataset')==='s004'?'s004/':new URLSearchParams(globalThis.location?.search||'').get('dataset')==='dalmatian'?'dalmatian/':new URLSearchParams(globalThis.location?.search||'').get('dataset')==='dog02'?'dog02/':'';
const localizationTask=datasetBase==='dog02/'&&new URLSearchParams(globalThis.location?.search||'').get('task')==='localization';
let playing=false, playbackTimer=null, loadRevision=0;
let manifest, data, storageKey, current=18, active='LF', originalImage, model=null, pairImages=null, reveal=false, pairIndices=null, pairRevision=0;
function emptyFrame(){return {paws:Object.fromEntries(names.map(p=>[p,{status:'unmarked',x:null,y:null}])),notes:'',modelExposed:false};}
function record(i){return data.frames[String(i)]??=emptyFrame();}
function eventRecord(i,p){const f=record(i);f.events??={};return f.events[p]??={type:'unreviewed',certainty:null};}
function setEvent(i,p,value){const [type,certainty]=value.split(':');const identity=record(i).paws[p].status;
 if(certainty==='certain'&&i===0)throw Error('Frame 0 has no preceding review frame; use uncertain.');
 if(certainty==='certain'&&identity!=='visible')throw Error('A certain event requires a visible, identity-certain paw. Otherwise use uncertain.');
 record(i).events??={};record(i).events[p]={type,certainty:certainty||null};persist();}
function invalidateEvents(i,p){const e=record(i).events?.[p];if(e?.certainty==='certain'){e.certainty='uncertain';e.invalidatedByIdentityEdit=true;}}
function stopPlayback(){playing=false;clearTimeout(playbackTimer);if($('play'))$('play').textContent='Play';}
async function playStep(){if(!playing)return;const q=queue(),next=q.find(i=>i>current);if(next===undefined){stopPlayback();return;}
 try{await load(next);}catch(e){stopPlayback();error(e);return;}
 if(playing)playbackTimer=setTimeout(playStep,1000/(manifest.fps*Number($('speed').value)));}
function togglePlayback(){if(playing){stopPlayback();return;}playing=true;$('play').textContent='Pause';playbackTimer=setTimeout(playStep,1000/(manifest.fps*Number($('speed').value)));}

function invalidateVerdicts(index){for(const [key,v] of Object.entries(data.transitions)){const [,a,b]=key.split(':');if(+a===index||+b===index){v.verdict='unreviewed';v.reviewedWithModel=false;v.invalidatedByLabelEdit=true;}}}
function pairNames(){return $('limb').value==='hind'?['LH','RH']:['LF','RF'];}
function error(e){$('error').textContent=String(e.message||e);}
function pairError(e){error(e);$('pairStatus').textContent='Action failed: '+String(e.message||e);}
function persist(){data.updatedAt=new Date().toISOString();try{localStorage.setItem(storageKey,JSON.stringify(data));$('saved').textContent='Autosaved locally at '+new Date().toLocaleTimeString();}catch(e){$('saved').textContent='Local autosave failed. Download JSON now.';}}
function validateImport(d){
 if(d.schemaVersion!==1||d.datasetId!==manifest.datasetId||d.predictionSha256!==manifest.predictionSha256||d.videoSha256!==manifest.videoSha256)throw Error('Wrong annotation schema or source dataset.');
 if(d.eventSchemaVersion!==undefined&&d.eventSchemaVersion!==1)throw Error('Unknown event schema.');
 if(!d.frames||!d.transitions||typeof d.annotator!=='string')throw Error('Missing annotation fields.');
 for(const [k,f] of Object.entries(d.frames)){
  if(!/^\d+$/.test(k)||+k<0||+k>=manifest.frameCount)throw Error('Invalid frame index.');
  for(const [p,e] of Object.entries(f.events||{})){if(!names.includes(p)||!['unreviewed','none','touchdown','toe_off','uncertain'].includes(e.type)||!['certain','uncertain',null].includes(e.certainty))throw Error('Invalid event annotation.');
   if(['touchdown','toe_off'].includes(e.type)?!['certain','uncertain'].includes(e.certainty):e.certainty!==null)throw Error('Invalid event certainty.');
   if(e.certainty==='certain'&&+k===0)throw Error('Certain boundary event lacks preceding frame.');
   if(e.certainty==='certain'&&f.paws?.[p]?.status!=='visible')throw Error('Certain event requires certain visible identity.');}
  for(const p of names){const v=f.paws?.[p];if(!v||!['unmarked','visible','occluded','uncertain'].includes(v.status))throw Error('Invalid paw status.');
   if(v.status==='visible'){if(!Number.isFinite(v.x)||!Number.isFinite(v.y)||v.x<0||v.x>=manifest.frameWidth||v.y<0||v.y>=manifest.frameHeight)throw Error('Point outside original image.');}
   else if(v.x!==null||v.y!==null)throw Error('Nonvisible paws must have null coordinates.');}
 }
 for(const [key,v] of Object.entries(d.transitions)){const parts=key.split(':');const a=Number(parts[1]),b=Number(parts[2]);
 if(parts.length!==3||!['front','hind'].includes(parts[0])||!Number.isInteger(a)||b!==a+1||a<0||b>=manifest.frameCount||!['unreviewed','swap','no_swap','uncertain'].includes(v.verdict))throw Error('Invalid adjacent transition.');
 if(['swap','no_swap'].includes(v.verdict)&&(!v.reviewedWithModel||![a,b].every(i=>(parts[0]==='hind'?['LH','RH']:['LF','RF']).every(p=>d.frames[i]?.paws?.[p]?.status==='visible'))))throw Error('Definite verdict requires certain points and model review.');}
 return d;
}
function queue(){if(manifest.physicalEvents&&$('queue').value==='continuation')return manifest.continuationFrames;if(manifest.physicalEvents&&$('queue').value==='reviewed')return manifest.reviewedFrames;return $('queue').value==='all'?manifest.frames.map(f=>f.frameIndex):$('queue').value==='priority'?manifest.priorityFrames:$('queue').value==='random'?manifest.randomFrames:manifest.selectedFrames;}
function markers(ctx,index,includeModel=false){
 if(globalThis.physicalTracks?.enabled())physicalTracks.markers(ctx,index);
 const sx=ctx.canvas.width/manifest.frameWidth,sy=ctx.canvas.height/manifest.frameHeight;
 for(const p of (globalThis.physicalTracks?.enabled()?[]:names)){const v=record(index).paws[p];if(v.status!=='visible')continue;ctx.strokeStyle=colors[p];ctx.fillStyle=colors[p];ctx.lineWidth=3;ctx.beginPath();ctx.arc(v.x*sx,v.y*sy,9,0,Math.PI*2);ctx.stroke();ctx.font='16px sans-serif';ctx.fillText('human '+p,v.x*sx+12,v.y*sy-12);}
 if(includeModel){for(const p of model.frames.find(f=>f.frameIndex===index)?.keypoints||[]){const name=names.find(n=>modelNames[n]===p.name);if(!name)continue;const x=p.x*sx,y=p.y*sy;ctx.strokeStyle=colors[name];ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x-7,y-7);ctx.lineTo(x+7,y+7);ctx.moveTo(x-7,y+7);ctx.lineTo(x+7,y-7);ctx.stroke();ctx.fillStyle=colors[name];ctx.fillText(`model ${name} ${p.rawScore.toFixed(4)}`,x+10,y+22);}}
}
function paint(){if(!originalImage)return;const ctx=$('image').getContext('2d');ctx.drawImage(originalImage,0,0,$('image').width,$('image').height);markers(ctx,current);}
function showLabels(){
 const physical=globalThis.physicalTracks?.enabled();
 $('frameNotes').disabled=Boolean(physical);
 $('saveVerdict').disabled=Boolean(physical);
 if(physical){physicalTracks.labels();$('frameNotes').value='';$('frameStatus').textContent='Physical A/B tracks: no anatomical mapping. Model exposure is recorded in the separate track export.';if(!manifest.localizationEvaluation)$('progress').textContent='Physical hind paw tracking';return;}
 const f=record(current);$('paws').replaceChildren();
 for(const p of names){const row=document.createElement('div');row.className='paw'+(p===active?' selected':'');row.style.borderColor=colors[p];const button=document.createElement('button');button.textContent=p;button.onclick=()=>{active=p;showLabels();};row.append(button);
 const select=document.createElement('select');select.setAttribute('aria-label',p+' visibility');for(const [v,t] of [['unmarked','Unmarked'],['visible','Visible, certain identity'],['occluded','Occluded'],['uncertain','Uncertain identity / position']]){const o=new Option(t,v);select.add(o);}select.value=f.paws[p].status;
 select.onchange=()=>{stopPlayback();const v=select.value;if(v==='visible'&&f.paws[p].x===null){active=p;select.value=f.paws[p].status;$('frameStatus').textContent='Click the paw in the image to set its visible position.';showLabels();return;}invalidateEvents(current,p);f.paws[p]={status:v,x:v==='visible'?f.paws[p].x:null,y:v==='visible'?f.paws[p].y:null};invalidateVerdicts(current);persist();showLabels();paint();};row.append(select);
 const value=document.createElement('span');const v=f.paws[p];value.textContent=v.x===null?'No coordinate':`(${v.x.toFixed(2)}, ${v.y.toFixed(2)})`;row.append(value);
 if(manifest.eventAnnotation){const event=document.createElement('select');event.setAttribute('aria-label',p+' gait event');
 for(const [v,t] of [['unreviewed','Event: unreviewed'],['none','Reviewed: no event'],['touchdown:certain','Touchdown: certain'],['touchdown:uncertain','Touchdown: uncertain'],['toe_off:certain','Toe-off: certain'],['toe_off:uncertain','Toe-off: uncertain'],['uncertain','Event type/timing uncertain']])event.add(new Option(t,v));
 const e=eventRecord(current,p);event.value=e.type+(e.certainty?':'+e.certainty:'');event.onchange=()=>{stopPlayback();try{setEvent(current,p,event.value);$('error').textContent='';}catch(e){error(e);}showLabels();};row.append(event);}
 $('paws').append(row);
 }
 $('frameNotes').value=f.notes||'';$('frameStatus').textContent=f.modelExposed?'Model previously revealed for this frame; exposure recorded.':'Blind annotation: no model displayed.';
 const complete=manifest.selectedFrames.filter(i=>names.every(p=>record(i).paws[p].status!=='unmarked')).length;$('progress').textContent=`${complete}/${manifest.selectedFrames.length} selected frames completed`;
}
async function image(index){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Could not load original frame '+index));im.src=datasetBase+manifest.frames[index].image;});}
async function load(index){if(!Number.isInteger(index)||index<0||index>=manifest.frameCount)throw Error(`Frame ${index} is outside this queue (0–${manifest.frameCount-1}).`);const revision=++loadRevision;current=index;originalImage=null;$('frame').value=index;$('frameTitle').textContent=`Original frame ${index} · ${manifest.frames[index].timestampSeconds.toFixed(4)} s`;
 if($('navFrameStatus'))$('navFrameStatus').textContent=`Frame ${index} · ${manifest.frames[index].timestampSeconds.toFixed(4)} s`;
 showLabels();const token=index;const im=await image(index);if(current!==token||revision!==loadRevision)return;originalImage=im;paint();$('filmstrip').replaceChildren();for(let j=Math.max(0,index-3);j<=Math.min(manifest.frameCount-1,index+3);j++){const b=document.createElement('button');b.textContent='Frame '+j;b.disabled=j===index;b.onclick=()=>{stopPlayback();load(j).catch(error);};$('filmstrip').append(b);}}
function move(delta){stopPlayback();const q=queue();const choices=q.filter(i=>delta>0?i>current:i<current);if(choices.length)load(delta>0?choices[0]:choices.at(-1)).catch(error);}
function pairKey(){return `${$('limb').value}:${pairIndices[0]}:${pairIndices[1]}`;}
function sufficientlyCertain(){return pairIndices&&pairIndices.every(i=>pairNames().every(p=>record(i).paws[p].status==='visible'));}
async function loadPair(){
 const revision=++pairRevision;const [a,b]=$('transition').value.split(':').map(Number);
 pairIndices=[a,b];reveal=false;pairImages=null;$('error').textContent='';
 $('pairStatus').textContent=`Loading original frames ${a} → ${b}. Model hidden.`;
 $('showModel').disabled=true;$('saveVerdict').disabled=true;
 for(const id of ['before','after']){$(id).getContext('2d').clearRect(0,0,852,480);}
 const imgs=await Promise.all([image(a),image(b)]);if(pairRevision!==revision)return;
 pairImages=imgs;$('showModel').disabled=localizationTask;$('saveVerdict').disabled=localizationTask;renderPair();
 const verdict=data.transitions[pairKey()];$('verdict').value=verdict?.verdict||'unreviewed';$('pairNotes').value=verdict?.notes||'';
}
function renderPair(){
 if(!pairImages)return;
 for(let j=0;j<2;j++){const ctx=$(j===0?'before':'after').getContext('2d');ctx.drawImage(pairImages[j],0,0,ctx.canvas.width,ctx.canvas.height);markers(ctx,pairIndices[j],reveal);}
 const missing=reveal?pairIndices.filter(i=>!(model.frames.find(f=>f.frameIndex===i)?.keypoints||[]).some(p=>Object.values(modelNames).includes(p.name))):[];
 $('pairStatus').textContent=`Frames ${pairIndices.join(' → ')}. `+
  (reveal?'Model predictions revealed for visual inspection. ':'Model hidden; click Reveal to inspect even with uncertain labels. ')+
  (globalThis.physicalTracks?.enabled()?'Compare A/B physical tracks with model LH/RH visually; A/B has no anatomical mapping. Anatomical verdicts are available in the anatomical layer.':sufficientlyCertain()?'Human labels are certain for the selected pair.':'Definite swap/no-swap verdicts are blocked until both paws are visible and identity-certain at both frames; an uncertain verdict is allowed.')+
  (missing.length?` No saved paw predictions in frame(s) ${missing.join(', ')}.`:'');
}
async function boot(){
 manifest=await (await fetch(datasetBase+(localizationTask?'evaluation-manifest.json':'manifest.json'),{cache:'no-store'})).json();storageKey='petlens-human-v1:'+manifest.datasetId+(localizationTask?':localization-v1':'');data={schemaVersion:1,datasetId:manifest.datasetId,predictionSha256:manifest.predictionSha256,videoSha256:manifest.videoSha256,annotator:'',frames:{},transitions:{},eventSchemaVersion:1,createdAt:new Date().toISOString()};
 let saved=null;try{saved=localStorage.getItem(storageKey);}catch(e){$('saved').textContent='Local storage unavailable; download JSON regularly.';}if(saved){try{data=validateImport(JSON.parse(saved));}catch(e){error('Stored annotations invalid; import a valid backup. '+e.message);}}
 current=manifest.initialFrame??18;$('frame').max=manifest.frameCount-1;
 for(const id of ['image','before','after']){$(id).width=manifest.frameWidth;$(id).height=manifest.frameHeight;}
 if(manifest.eventAnnotation){$('queue').replaceChildren();for(const value of ['selected','all'])$('queue').add(new Option('Consecutive dog02 frames 0–30',value));$('queue').add(new Option('20-frame localization evaluation (through frame 59)','localization'));$('queue').value='selected';
 $('imageHelp').textContent=`Original ${manifest.frameWidth}×${manifest.frameHeight} pixels. Keys 1–4 select LF/RF/LH/RH; arrows step frames. Events refer to the transition from the previous frame into this frame. Frame 0 has no preceding frame in this review.`;}
 if(manifest.attribution){$('sourceAttribution').textContent=manifest.attribution;}
 if($('fitFrame'))$('fitFrame').onchange=()=>{$('image').style.maxHeight=$('fitFrame').checked?'':'none';};
 globalThis.physicalTracks?.boot();
 if(manifest.physicalEvents){$('labelLayer').value='physical';$('labelLayer').disabled=true;$('adjudication').hidden=true;$('download').hidden=true;$('import').disabled=true;
 $('queue').replaceChildren();for(const [v,t] of [['continuation','Continue: 73–90'],['reviewed','Reviewed: 46–72'],['selected','Primary: 46–90'],['priority','Secondary: 107–127'],['all','All frames: context']])$('queue').add(new Option(t,v));
 $('queue').value='continuation';
 $('annotationIntro').textContent='Continue at frame 73 after importing your reviewed A/B JSON. Seek the next verified touchdown of physical Paw B after frame 66 toe-off. Overlap does not establish continuity: mark uncertain when identity cannot be followed. Follow physical hind paws A/B. Predictions remain hidden. Assign A and B independently in each sequence unless continuity between sequences is established.';
 $('imageHelp').textContent='Original frames and timestamps are preserved. Arrows step the selected queue; use Reviewed: 46–72 or All frames: context to inspect earlier identity evidence. Download A/B tracks JSON to save the combined review.';
 $('eventHelp').textContent='Mark contact events and continuity separately for each paw. Certain events require a visible paw and reviewed identity continuity. Uncertain or occluded means no coordinate.';}

 if(manifest.reviewQueues){$('queue').replaceChildren();for(const [value,label] of manifest.reviewQueues)$('queue').add(new Option(label,value));$('queue').value='selected';
 $('annotationIntro').textContent='Track physical hind paws A/B using connected leg anatomy. Predictions stay hidden. Do not guess identity through overlap or occlusion.';
 $('imageHelp').textContent=`Original ${manifest.frameWidth}×${manifest.frameHeight} pixels. Arrows step frames; controls stay beside the canvas. Uncheck Fit frame to screen for a larger view.`;}

 if(localizationTask){
  $('labelLayer').value='physical';$('labelLayer').disabled=true;$('localizationSeed').hidden=false;
  $('queue').replaceChildren();for(const [v,t] of [['selected','20 evaluation targets'],['priority','6 development targets'],['random','14 frozen holdout targets'],['all','All 60 frames: identity context']])$('queue').add(new Option(t,v));$('queue').value='selected';
  $('annotationIntro').textContent='Label physical hind paws A/B, not anatomical left/right. Preserve the existing Paw A identity. Visible means location and physical identity are clear; otherwise choose occluded or uncertain, with no coordinate.';
  $('eventHelp').textContent='Label both A and B on the 20 targets. Use surrounding original frames to establish identity. Do not guess through an unresolved crossing. No gait-event labels are required.';
  $('imageHelp').textContent='Original 960×544 pixels. Target queue is sparse: use All 60 frames or neighboring-frame buttons for continuous identity context. Click the paw tip consistently. Existing A/B autosave resumes when available; import JSON only to restore a backup. No model labels are prefilled.';
  $('adjudication').hidden=true;$('download').hidden=true;$('import').disabled=true;
 }

 $('play').onclick=togglePlayback;
 $('speed').onchange=()=>{if(playing){stopPlayback();togglePlayback();}};
 $('annotator').value=globalThis.physicalTracks?.enabled()?physicalTracks.annotator():data.annotator;$('annotator').oninput=()=>{data.annotator=$('annotator').value;persist();};
 $('image').onclick=e=>{if(!originalImage)return;const rect=$('image').getBoundingClientRect();const x=Math.max(0,Math.min(manifest.frameWidth-0.0001,(e.clientX-rect.left-$('image').clientLeft)/(rect.width-2*$('image').clientLeft)*manifest.frameWidth));const y=Math.max(0,Math.min(manifest.frameHeight-0.0001,(e.clientY-rect.top-$('image').clientTop)/(rect.height-2*$('image').clientTop)*manifest.frameHeight));stopPlayback();if(globalThis.physicalTracks?.enabled()){physicalTracks.point(x,y);return;}invalidateEvents(current,active);record(current).paws[active]={status:'visible',x,y};invalidateVerdicts(current);persist();showLabels();paint();};
 $('clearPaw').onclick=()=>{stopPlayback();if(globalThis.physicalTracks?.enabled()){physicalTracks.status('unmarked');return;}if(globalThis.physicalTracks?.enabled()){physicalTracks.point(x,y);return;}invalidateEvents(current,active);record(current).paws[active]={status:'unmarked',x:null,y:null};invalidateVerdicts(current);persist();showLabels();paint();};
 $('frameNotes').oninput=()=>{record(current).notes=$('frameNotes').value;persist();};$('prev').onclick=()=>move(-1);$('next').onclick=()=>move(1);$('go').onclick=()=>{stopPlayback();load(Number($('frame').value)).catch(error);};$('queue').onchange=()=>{stopPlayback();if($('queue').value==='localization'){globalThis.location.search='?dataset=dog02&task=localization';return;}load(queue()[0]).catch(error);};
 $('download').onclick=()=>{stopPlayback();persist();const blob=new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=manifest.datasetId+'-human-annotations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 $('import').onchange=async()=>{try{const file=$('import').files[0];if(!file)return;stopPlayback();const incoming=validateImport(JSON.parse(await file.text()));data=incoming;$('annotator').value=data.annotator;persist();await load(current);}catch(e){error(e);}};
 for(let i=0;i<manifest.frameCount-1;i++){const cohort=manifest.reviewPairs.find(r=>r.fromFrame===i)?.cohort||'other';$('transition').add(new Option(`${i} → ${i+1} (${cohort})`,`${i}:${i+1}`));}$('transition').value=`${current}:${current+1}`;
 $('transition').onchange=()=>loadPair().catch(pairError);$('openPair').onclick=()=>loadPair().catch(pairError);$('limb').onchange=()=>loadPair().catch(pairError);
 $('showModel').onclick=async()=>{
  try{
   $('error').textContent='';if(localizationTask)throw Error('Model reveal is disabled during frozen localization evaluation.');if(!pairImages)throw Error('Original frames are not ready. Load the pair and wait, then click Reveal again.');
   const revision=pairRevision;$('pairStatus').textContent='Loading saved model predictions for visual inspection…';
   if(!model){
    if(manifest.physicalEvents)throw Error('Model reveal disabled for blind annotation.');const response=await fetch(datasetBase+'model-review.json');if(response.ok===false)throw Error(`Could not load model predictions (HTTP ${response.status}). Try Reveal again.`);
    const candidate=await response.json();if(candidate.datasetId!==manifest.datasetId||!Array.isArray(candidate.frames))throw Error('Saved model predictions have an invalid format or belong to a different dataset.');
    model=candidate;
   }
   if(pairRevision!==revision)throw Error('The frame pair changed while predictions loaded. Click Reveal for the current pair.');
   for(const i of pairIndices){
    const frame=model.frames.find(f=>f.frameIndex===i);if(!frame||!Array.isArray(frame.keypoints))throw Error(`Saved predictions for frame ${i} are missing or invalid.`);
    for(const p of frame.keypoints){if(Object.values(modelNames).includes(p.name)&&![p.x,p.y,p.rawScore].every(Number.isFinite))throw Error(`Invalid saved paw coordinates or score in frame ${i}.`);}
   }
   reveal=true;renderPair();if(globalThis.physicalTracks?.enabled())physicalTracks.expose(pairIndices);else {for(const i of pairIndices)record(i).modelExposed=true;persist();}showLabels();
  }catch(e){pairError(e);}
 };
 $('saveVerdict').onclick=()=>{try{$('error').textContent='';if(globalThis.physicalTracks?.enabled())throw Error('Anatomical verdicts require the anatomical layer; A/B has no LH/RH mapping.');if(!pairImages)throw Error('Wait for the original pair to load.');const v=$('verdict').value;if(['swap','no_swap'].includes(v)&&(!sufficientlyCertain()||!reveal))throw Error('Definite verdict requires certain human labels at both frames and explicit model review. Otherwise choose uncertain.');data.transitions[pairKey()]={verdict:v,notes:$('pairNotes').value,reviewedWithModel:reveal,reviewedAt:new Date().toISOString()};persist();$('pairStatus').textContent+=' Verdict saved.';}catch(e){pairError(e);}};
 document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)||e.target.isContentEditable)return;if(['ArrowLeft','ArrowRight'].includes(e.key))e.preventDefault?.();if(['1','2','3','4'].includes(e.key)){active=names[+e.key-1];showLabels();}if(e.key==='ArrowRight')move(1);if(e.key==='ArrowLeft')move(-1);});
 await load(current);await loadPair();
}
boot().catch(error);
