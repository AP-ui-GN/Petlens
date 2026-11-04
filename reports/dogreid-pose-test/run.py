import sys,importlib.util,json,time,hashlib,platform
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
study=ROOT/'tmp/rtmpose-test/multi-video-evaluation'
spec=importlib.util.spec_from_file_location('existing_evaluation',study/'evaluate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

prov=json.loads((study/'models/provenance.json').read_text());model_path=study/'models/rtmpose-ap10k.onnx'
assert hashlib.sha256(model_path.read_bytes()).hexdigest()==prov['files']['rtmpose-ap10k.onnx']['sha256']
from rtmlib import RTMPose
import onnxruntime as ort
import csv
t0=time.perf_counter()
pose=RTMPose(onnx_model=str(model_path),model_input_size=(256,256),backend='onnxruntime',device='cpu',to_openpose=False)
opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
pose.session=ort.InferenceSession(str(model_path),sess_options=opts,providers=['CPUExecutionProvider'])
load_seconds=time.perf_counter()-t0
class Model:
 def __call__(self,im):
  gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
  if self.prev is not None and self.features is not None:
   nxt,status,err=cv2.calcOpticalFlowPyrLK(self.prev,gray,self.features,None)
   valid=status.reshape(-1).astype(bool)
   if valid.sum()>=5:
    delta=np.median((nxt-self.features).reshape(-1,2)[valid],axis=0);self.box+=np.tile(delta,2)
  self.prev=gray
  mask=np.zeros(gray.shape,np.uint8);x1,y1,x2,y2=self.box.astype(int);mask[max(0,y1):min(gray.shape[0],y2),max(0,x1):min(gray.shape[1],x2)]=255
  self.features=cv2.goodFeaturesToTrack(gray,80,.02,8,mask=mask)
  points,scores=pose(im,bboxes=[self.box.tolist()])
  return dict(detectionSuccess=True,boundingBoxXyxy=self.box.tolist(),keypoints=[dict(name=n,x=float(p[0]),y=float(p[1]),rawScore=float(v)) for n,p,v in zip(m.NAMES,points[0],scores[0])])
model=Model()
results={}
for number,count in [(115,60),(198,90)]:
 bbox=json.loads((ROOT/'reports/dogreid-1553/preview-manifest.json').read_text())[number-1];x,y,w,h=[float(bbox[k]) for k in ['x_top_left','y_top_left','width','height']];model.box=np.array([x,y,x+w,y+h]);model.prev=None;model.features=None
 cap=cv2.VideoCapture(str(ROOT/f'reports/dogreid-1553/videos/{number}.mp4'));fps=cap.get(cv2.CAP_PROP_FPS);records=[];stills=[];writer=None
 for idx in range(count):
  ok,im=cap.read()
  if not ok:break
  pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
  t=time.perf_counter();r=model(im);elapsed=time.perf_counter()-t
  r.update(frameIndex=idx,timestampSeconds=pts,inferenceSeconds=elapsed);records.append(r)
  pts_by_name={p['name']:p for p in r['keypoints']}
  for chain in [('left_shoulder','left_elbow','left_front_paw'),('right_shoulder','right_elbow','right_front_paw'),('left_hip','left_knee','left_back_paw'),('right_hip','right_knee','right_back_paw')]:
   color=(0,180,255) if chain[0].startswith('left') else (255,100,0)
   for a,b in zip(chain,chain[1:]):
    if a in pts_by_name and b in pts_by_name and min(pts_by_name[a]['rawScore'],pts_by_name[b]['rawScore'])>=.5:
     cv2.line(im,tuple(int(pts_by_name[a][v]) for v in ['x','y']),tuple(int(pts_by_name[b][v]) for v in ['x','y']),color,3)
  for p in r['keypoints']:
   xy=(int(p['x']),int(p['y']));color=(0,180,255) if p['name'].startswith('left') else (255,100,0)
   cv2.circle(im,xy,5,color,-1 if p['rawScore']>=.5 else 1)
   if 'paw' in p['name']:cv2.putText(im,p['name']+' %.2f'%p['rawScore'],xy,cv2.FONT_HERSHEY_SIMPLEX,.45,color,1)
  cv2.putText(im,f'#{number} frame {idx} t={pts:.3f}s | raw AP10K | threshold .5',(15,30),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,255),2)
  scale=min(1,960/im.shape[1],720/im.shape[0]);im=cv2.resize(im,None,fx=scale,fy=scale)
  if writer is None:writer=cv2.VideoWriter(str(OUT/f'{number}-overlay.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(im.shape[1],im.shape[0]))
  writer.write(im)
  if idx in [0,10,20,30,40,50,60,80]:
   cv2.imwrite(str(OUT/f'{number}-frame-{idx:03}.jpg'),im);stills.append(im)
  if idx%15==0: print(number,idx,round(elapsed,3),flush=True)
 cap.release();writer.release()
 (OUT/f'{number}-predictions.json').write_text(json.dumps(records,indent=2))
 times=[r['inferenceSeconds'] for r in records];paw_stats={}
 for name in [n for n in m.NAMES if 'paw' in n]:
  good=0;jumps=[];prev=None
  for r in records:
   p=next((p for p in r['keypoints'] if p['name']==name and p['rawScore']>=.5),None)
   if p:good+=1
   box=r.get('boundingBoxXyxy');norm=np.hypot(box[2]-box[0],box[3]-box[1]) if box else 1
   if p and prev:jumps.append(float(np.hypot(p['x']-prev['x'],p['y']-prev['y'])/norm))
   prev=p
  paw_stats[name]={'coverage_at_raw_score_0.5':good/len(records),'median_step_box_diagonal':float(np.median(jumps)) if jumps else None,'p95_step_box_diagonal':float(np.percentile(jumps,95)) if jumps else None}
 results[number]={'frames':len(records),'source_fps':fps,'supplied_or_flow_tracked_box_frames':sum(r['detectionSuccess'] for r in records),'median_seconds':float(np.median(times)),'p95_seconds':float(np.percentile(times,95)),'total_inference_seconds':sum(times),'paws':paw_stats}
 # Contact sheet preserves aspect ratio with padding.
 tiles=[]
 for im in stills:
  tile=np.full((300,480,3),245,np.uint8);s=min(480/im.shape[1],300/im.shape[0]);small=cv2.resize(im,None,fx=s,fy=s);tile[:small.shape[0],:small.shape[1]]=small;tiles.append(tile)
 while len(tiles)%4:tiles.append(np.full((300,480,3),245,np.uint8))
 cv2.imwrite(str(OUT/f'{number}-sheet.jpg'),np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,len(tiles),4)]))
 (OUT/'metrics.json').write_text(json.dumps({'load_seconds':load_seconds,'python':sys.version,'platform':platform.platform(),'onnx_threads':2,'bbox_method':'Dataset first-frame box plus median sparse optical-flow translation; no learned detector','onnx_providers_available':ort.get_available_providers(),'provenance':prov,'clips':results},indent=2))
 print(results[number],flush=True)
