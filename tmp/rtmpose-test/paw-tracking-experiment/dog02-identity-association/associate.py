"""Offline, annotation-blind two-identity association over unchanged V2 observations.

Exact width-four binary dynamic programming; no learned parameters or label prior.
Pairwise costs span four samples; midpoint consistency spans two time scales.
Motion costs rank hypotheses, never reject or repair observed coordinates.
"""
from dataclasses import dataclass, asdict
import importlib.util
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('identity_v2',HERE.parent/'dog02-temporal-tracker-v2/tracker.py')
v2=importlib.util.module_from_spec(_spec)
import sys
sys.modules[_spec.name]=v2
_spec.loader.exec_module(v2)
NAMES=v2.NAMES

@dataclass(frozen=True)
class Rules:
    horizon: int=4
    motion_cap: float=.15
    distance_weight: float=.02
    margin: float=.002
    maximum_link_seconds: float=.4


def associate(records,width,height,rules=Rules()):
    retained=v2.track(records,width,height)
    records=sorted(records,key=lambda r:r['frameIndex'])
    frames=retained['frames']; positions=[]
    for record,f in zip(records,frames):
        p={p['name']:p for p in record.get('keypoints',[])}
        a,b=p.get('neck'),p.get('root_of_tail');length=0.
        if v2.valid(a,.7) and v2.valid(b,.8):length=math.hypot(a['x']-b['x'],a['y']-b['y'])
        positions.append([((q['x']-(a['x']+b['x'])/2)/length,(q['y']-(a['y']+b['y'])/2)/length) if (q:=f['paws'][n]['point']) is not None and length>0 else None for n in NAMES])
    anchor=None
    for i in range(len(frames)-1):
        if all(all(p is not None for p in positions[j]) and math.dist(*positions[j])>v2.Rules().overlap for j in (i,i+1)) and frames[i+1]['frameIndex']==frames[i]['frameIndex']+1:
            anchor=i;break
    def link(a,b):
        # Never bridge absent source indices or long elapsed gaps.
        return frames[b]['frameIndex']-frames[a]['frameIndex']==b-a and 0<frames[b]['timestampSeconds']-frames[a]['timestampSeconds']<=rules.maximum_link_seconds
    cap2=rules.motion_cap**2
    def energy(i,states):
        start=i-len(states)+1
        point=lambda j,k:positions[j][k ^ states[j-start]]
        cost=0.
        for lag in range(1,min(rules.horizon,i)+1):
            j=i-lag
            if j<start or not link(j,i):continue
            for k in (0,1):
                a,b=point(j,k),point(i,k)
                if a is not None and b is not None:
                    cost+=rules.distance_weight*min(math.dist(a,b)**2,cap2)/lag
        for lag in (1,2):
            a,b=i-2*lag,i-lag
            if a<start or a<0 or not link(a,i):continue
            t=(frames[b]['timestampSeconds']-frames[a]['timestampSeconds'])/(frames[i]['timestampSeconds']-frames[a]['timestampSeconds'])
            for k in (0,1):
                p,q,r=point(a,k),point(b,k),point(i,k)
                if all(x is not None for x in (p,q,r)):
                    # Internal hypothesis score only; never output this midpoint.
                    chord=tuple(x+(z-x)*t for x,z in zip(p,r))
                    cost+=min(math.dist(q,chord)**2,cap2)/lag
        return cost
    def solve(forced=None,need_path=False):
        paths={(): (0.,[]) }
        for i in range(anchor,len(frames)):
            nxt={}
            for history,(cost,path) in paths.items():
                for s in (0,1):
                    if i==anchor and s!=0 or forced is not None and forced[0]==i and s!=forced[1]:continue
                    state=history+(s,);value=cost+energy(i,state);key=state[-rules.horizon:]
                    if key not in nxt or value<nxt[key][0]:nxt[key]=(value,path+[s] if need_path else [])
            paths=nxt
        return min(paths.values(),key=lambda r:r[0])
    best,path=solve(need_path=True) if anchor is not None else (None,[])
    output=[]
    for i,f in enumerate(frames):
        state=path[i-anchor] if anchor is not None and i>=anchor else None
        margin=None if state is None or i==anchor else max(0.,solve((i,1-state))[0]-best)
        common=[]
        if state is None:common.append('no_stable_identity_anchor_yet')
        elif i!=anchor and margin<rules.margin:common.append('competing_identity_paths')
        if all(p is not None for p in positions[i]) and math.dist(*positions[i])<=v2.Rules().overlap:common.append('overlapping_candidates')
        tracks=[]
        for k in (0,1):
            source=None if state is None else NAMES[k ^ state]
            p=f['paws'][source]['point'] if source else None
            reasons=common[:]
            if p is None:reasons.append('observation_unavailable')
            elif positions[i][k ^ state] is None:reasons.append('body_reference_unavailable')
            tracks.append({'identity':k,'status':'unresolved' if reasons else 'associated','reasons':reasons,
                           'sourceName':source if not reasons else None,'point':dict(p) if p is not None and not reasons else None,
                           'hypothesisSourceName':source})
        output.append({'frameIndex':f['frameIndex'],'timestampSeconds':f['timestampSeconds'],'stateHypothesis':state,
                       'alternativePathMargin':margin,'physicalTracks':tracks})
    return {'rules':asdict(rules),'anchorFrame':frames[anchor]['frameIndex'] if anchor is not None else None,
            'identityConvention':'Track 0 = original model LH at stable anchor; track 1 = RH there. These are arbitrary persistent IDs, not anatomical sides or human A/B.',
            'frames':output,'v2Observations':retained,
            'limitations':'Motion-only hypotheses are not proof of identity. Original observations survive even when identity is unresolved. Gaps can leave all subsequent identities unresolved; no silent identity reset.'}
