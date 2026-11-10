"""Annotation-blind observation retention with advisory multi-frame identity flags.

Coordinate eligibility and physical identity uncertainty are separate. Temporal
flags never remove observations or relabel paws. No speed/acceleration gates.
"""
from dataclasses import asdict, dataclass
import math

NAMES = ('left_back_paw', 'right_back_paw')

@dataclass(frozen=True)
class Rules:
    paw_score: float = .8
    overlap: float = .08  # body lengths; identity warning only
    swap_advantage: float = .2  # mean two-paw cost in body lengths
    swap_ratio: float = .6
    max_context_gap: float = .2  # seconds; does not affect coordinate retention


def valid(p, threshold):
    return p is not None and all(isinstance(p.get(k), (int,float)) and math.isfinite(p[k]) for k in ('x','y','rawScore')) and p['rawScore'] >= threshold


def track(records, width, height, rules=Rules()):
    if width <= 0 or height <= 0:
        raise ValueError('invalid image dimensions')
    records = sorted(records, key=lambda f:f['frameIndex'])
    if len({f['frameIndex'] for f in records}) != len(records):
        raise ValueError('duplicate frame index')
    frames, positions = [], []
    for i, f in enumerate(records):
        t = f['timestampSeconds']
        if not isinstance(t,(int,float)) or not math.isfinite(t) or (i and t <= records[i-1]['timestampSeconds']):
            raise ValueError('invalid or nonincreasing timestamp')
        points = {p['name']:p for p in f.get('keypoints',[])}
        row = {'frameIndex':f['frameIndex'], 'timestampSeconds':t, 'paws':{}}
        for n in NAMES:
            p, reasons = points.get(n), []
            if not f.get('detectionSuccess'):
                reasons.append('dog_detection_missing')
            if not valid(p, rules.paw_score):
                reasons.append('missing_nonfinite_or_low_score')
            elif not (0 <= p['x'] < width and 0 <= p['y'] < height):
                reasons.append('outside_image')  # independent geometric invalidity
            row['paws'][n] = {'coordinateStatus':'uncertain' if reasons else 'retained',
                             'coordinateReasons':reasons, 'observedPoint':dict(p) if p else None,
                             'point':None if reasons else dict(p), 'identityStatus':'unverified_model_label',
                             'identityFlags':[], 'temporalContext':'unavailable'}
        pos = None
        if all(row['paws'][n]['point'] for n in NAMES) and valid(points.get('neck'),.7) and valid(points.get('root_of_tail'),.8):
            a,b = points['neck'],points['root_of_tail']
            length = math.hypot(a['x']-b['x'], a['y']-b['y'])
            if length > 0:
                pos = [((points[n]['x']-(a['x']+b['x'])/2)/length, (points[n]['y']-(a['y']+b['y'])/2)/length) for n in NAMES]
        if pos and math.dist(*pos) <= rules.overlap:
            for p in row['paws'].values():
                p['identityFlags'].append('overlapping_candidates')
                p['identityStatus']='ambiguous'
        frames.append(row); positions.append(pos)

    def window_ok(start, end):
        return all(positions[j] is not None for j in range(start,end)) and all(
            records[j]['frameIndex']==records[j-1]['frameIndex']+1 and
            records[j]['timestampSeconds']-records[j-1]['timestampSeconds'] <= rules.max_context_gap
            for j in range(start+1,end))

    events = []
    # At each boundary compare TWO past and TWO future frames, all four pairs.
    # A crossing can resemble a swap: this is evidence for review, never proof.
    for i in range(2,len(records)-1):
        if not window_ok(i-2,i+2):
            continue
        for j in range(i-2,i+2):
            for p in frames[j]['paws'].values(): p['temporalContext']='available'
        if any(math.dist(*positions[j]) <= rules.overlap for j in range(i-2,i+2)):
            continue
        same = crossed = 0.
        for a in (i-2,i-1):
            for b in (i,i+1):
                same += sum(math.dist(positions[a][k],positions[b][k]) for k in (0,1))/4
                crossed += sum(math.dist(positions[a][k],positions[b][1-k]) for k in (0,1))/4
        if same-crossed >= rules.swap_advantage and crossed <= rules.swap_ratio*same:
            events.append({'fromFrame':records[i-1]['frameIndex'], 'toFrame':records[i]['frameIndex'],
                           'supportFrames':[records[j]['frameIndex'] for j in range(i-2,i+2)],
                           'sameLabelCost':same, 'crossedLabelCost':crossed, 'flag':'possible_identity_swap_or_crossing'})
            for j in (i-1,i):
                for p in frames[j]['paws'].values():
                    if 'possible_identity_swap_or_crossing' not in p['identityFlags']:
                        p['identityFlags'].append('possible_identity_swap_or_crossing')
                    p['identityStatus']='ambiguous'
    return {'rules':asdict(rules), 'frames':frames, 'identityEvents':events,
            'policy':'Retained means coordinate available, not verified localization or physical identity. Temporal flags are advisory only.'}
