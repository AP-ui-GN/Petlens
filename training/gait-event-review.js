'use strict';
// Extension of the existing original-frame canvas/navigation. No legacy boot,
// storage, labels, overlays, predictions, or automatic event proposals are used.
globalThis.gaitEventReview = (() => {
  const fields = [
    ['initialContactLastAirborne', 'Initial contact: last definitely airborne'],
    ['initialContactFirstContacting', 'Initial contact: first definitely contacting'],
    ['liftOffLastContacting', 'Lift-off: last definitely contacting'],
    ['liftOffFirstAirborne', 'Lift-off: first definitely airborne'],
    ['nextContactLastAirborne', 'Next contact: last definitely airborne'],
    ['nextContactFirstContacting', 'Next contact: first definitely contacting'],
  ];
  let base, draft = null, key, group, selectedPaw = 'A';

  function status(message) { $('eventStatus').textContent = message; }
  function save() {
    if (!draft) return;
    try { localStorage.setItem(key, JSON.stringify(draft)); }
    catch (e) { status('Autosave unavailable; download a draft backup now.'); }
  }
  function control(tag, label, value) {
    const element = document.createElement(tag);
    element.setAttribute('aria-label', label);
    if (value !== undefined) element.value = value;
    return element;
  }
  function select(label, choices, value, change) {
    const element = control('select', label);
    for (const choice of choices) element.add(new Option(choice, choice));
    element.value = value;
    element.onchange = () => { stopPlayback(); change(element.value); save(); };
    return element;
  }
  function button(label, action) {
    const element = control('button', label);
    element.textContent = label;
    element.onclick = () => { stopPlayback(); action(); };
    return element;
  }
  function download(payload, name) {
    const url = URL.createObjectURL(payload instanceof Blob ? payload :
      new Blob([JSON.stringify(payload, null, 2) + '\n'], {type: 'application/json'}));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = name; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function post(endpoint, value) {
    const response = await fetch('/api/' + endpoint + '?group=' + group, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value),
    });
    if (!response.ok) throw Error(await response.text());
    return response;
  }
  function renderStrides() {
    $('eventStrides').replaceChildren();
    if (!draft) return;
    for (const stride of draft.strides) {
      const card = document.createElement('div'); card.className = 'card';
      const heading = document.createElement('p');
      heading.textContent = 'Human stride assertion ' + stride.id.slice(0, 8);
      card.append(heading,
        select('Stride ' + stride.id + ' physical paw', ['A', 'B'], stride.physicalPaw,
          value => { stride.physicalPaw = value; stride.status = 'unreviewed'; renderStrides(); }),
        select('Stride ' + stride.id + ' status',
          ['unreviewed', 'complete', 'occluded', 'uncertain', 'unassessable'], stride.status,
          value => { stride.status = value; }));
      for (const [field, label] of fields) {
        const row = document.createElement('div');
        const text = document.createElement('p'), boundary = stride.boundaries[field];
        text.textContent = label + ': ' + (boundary ?
          `frame ${boundary.frameIndex} · ${boundary.timestampSeconds.toFixed(6)} s` : 'not marked');
        row.append(text, button('Set ' + label + ' to displayed frame', () => {
          if (!manifest.selectedFrames.includes(current)) return status('Context only: event boundary must be inside the review window.');
          stride.boundaries[field] = {frameIndex: current,
            timestampSeconds: manifest.frames[current].timestampSeconds};
          stride.status = 'unreviewed'; save(); renderStrides();
        }), button('Clear ' + label, () => {
          stride.boundaries[field] = null; stride.status = 'unreviewed'; save(); renderStrides();
        }));
        card.append(row);
      }
      const notes = control('textarea', 'Stride ' + stride.id + ' evidence', stride.notes);
      notes.placeholder = 'Physical-paw continuity, contact evidence, and any uncertainty';
      notes.oninput = () => { stride.notes = notes.value; save(); };
      card.append(notes, button('Delete assertion ' + stride.id.slice(0, 8), () => {
        draft.strides = draft.strides.filter(row => row !== stride); save(); renderStrides();
      }));
      $('eventStrides').append(card);
    }
  }
  function labels() {
    $('paws').replaceChildren();
    if (!draft) { $('frameStatus').textContent = 'Enter your reviewer ID, then start your own blank review.'; return; }
    if (!manifest.selectedFrames.includes(current)) {
      $('frameStatus').textContent = 'Original context frame only. No annotations are recorded here.'; return;
    }
    $('frameStatus').textContent = 'Human-entered observations only. A/B are physical paws, not anatomical sides.';
    const pawSelector = select('Physical paw to review', ['A', 'B'], selectedPaw,
      value => { selectedPaw = value; labels(); });
    $('paws').append(pawSelector);
    const observation = draft.observations[String(current)][selectedPaw];
    const choices = {
      visibility: ['unreviewed', 'visible', 'occluded', 'uncertain', 'unassessable'],
      continuity: ['unreviewed', 'start', 'continuous', 'broken', 'uncertain', 'unassessable'],
      supportState: ['unreviewed', 'airborne', 'contacting', 'occluded', 'uncertain', 'unassessable'],
    };
    for (const [field, options] of Object.entries(choices)) {
      const row = document.createElement('label'); row.textContent = selectedPaw + ' ' + field;
      row.append(select(selectedPaw + ' ' + field, options, observation[field], value => {
        if (field === 'supportState' && ['airborne', 'contacting'].includes(value) && observation.visibility !== 'visible') {
          status('A definite support observation requires visibility = visible.'); labels(); return;
        }
        observation[field] = value;
        if (field === 'visibility' && value !== 'visible' && ['airborne', 'contacting'].includes(observation.supportState))
          observation.supportState = 'unreviewed';
        labels();
      }));
      $('paws').append(row);
    }
    const notes = control('textarea', selectedPaw + ' frame evidence', observation.notes);
    notes.placeholder = 'Visibility / continuity evidence or reason this frame is unassessable';
    notes.oninput = () => { observation.notes = notes.value; save(); };
    $('paws').append(notes);
    $('progress').textContent = Object.values(draft.observations).reduce((n, paws) =>
      n + Object.values(paws).filter(o => o.visibility !== 'unreviewed').length, 0) +
      '/' + (manifest.selectedFrames.length * 2) + ' paw-frames marked; not adjudicated';
  }
  async function boot() {
    group = new URLSearchParams(location.search).get('dataset') || 'gait-dalmatian';
    if (!['gait-dalmatian', 'gait-dog02'].includes(group)) throw Error('Unknown blind event review source');
    const response = await fetch('/api/session?group=' + group);
    if (!response.ok) throw Error(await response.text());
    base = await response.json(); manifest = structuredClone(base.source);
    data = {frames: {}, transitions: {}}; model = null; reveal = false; pairImages = null;
    // Existing paint()/load()/move() remain in use. Never draw any markers.
    markers = () => {}; showLabels = labels; renderPair = () => {};
    image = async i => new Promise((resolve, reject) => {
      const im = new Image(); im.onload = () => resolve(im);
      im.onerror = () => reject(Error('Verified original source frame unavailable'));
      im.src = `/api/frame?group=${group}&index=${i}`;
    });
    $('image').width = manifest.frameWidth; $('image').height = manifest.frameHeight;
    $('image').setAttribute('aria-label', 'Unmarked original source video frame');
    $('image').onclick = null; $('image').style.cursor = 'default';
    $('download').closest('details').hidden = true;
    $('physicalControls').hidden = true; $('clearPaw').hidden = true;
    $('frameNotes').disabled = true;
    $('annotationIntro').textContent = 'Independent human event review. A/B must follow the same physical paws; never use screen order or infer anatomical sides. No predictions or previous labels are loaded.';
    document.querySelector('.warning').textContent = 'Mark only what you can see. Occluded, uncertain, broken continuity, and unassessable are valid outcomes. Do not force a complete stride.';
    $('sourceAttribution').textContent = manifest.attribution + ' Source SHA256: ' + manifest.sourceVideo.sha256;
    $('eventHelp').textContent = 'Review every intervening frame. Contact is bracketed by last definitely airborne / first definitely contacting. Lift-off is bracketed by last definitely contacting / first definitely airborne. Repeat the contact bracket for the SAME physical paw. Annotations describe visible contact, not force. A complete assertion requires all six boundaries and visible, continuous physical identity throughout.';
    $('imageHelp').textContent = 'Original source pixels, numbers and native PTS. No markers are drawn. Use arrows, frame jump, or slow playback; observe a full sequence before entering event brackets.';
    $('annotationIntro').insertAdjacentHTML('afterend', `
      <div class="card"><label>Reviewer ID <input id="eventReviewer" autocomplete="off"></label>
      <button id="eventStart">Start / resume only my review</button>
      <label>Independence declaration <select id="eventIndependence" disabled>
      <option value="unreviewed">Not declared</option>
      <option value="no_prior_exposure">I have not seen predictions or prior event labels for this review footage</option>
      <option value="prior_exposure">I have prior exposure; retain my work as non-independent</option></select></label>
      <p id="eventStatus" aria-live="polite"></p>
      <button id="eventBackup">Download my draft backup</button>
      <label>Resume my event-review JSON <input id="eventImport" type="file" accept=".json"></label>
      <button id="eventValidate">Check review</button><button id="eventExport">Validate, save & download versioned ZIP</button>
      </div>`);
    $('paws').insertAdjacentHTML('afterend', `
      <div class="card"><p>Describe the physical identities from visible leg anatomy; do not import an anatomical mapping.</p>
      <label>Physical A description <textarea id="eventPawA" disabled></textarea></label>
      <label>Physical B description <textarea id="eventPawB" disabled></textarea></label>
      <button id="eventAddStride">Add blank assertion for selected physical paw</button>
      <div id="eventStrides"></div></div>`);
    function activate(incoming) {
      draft = incoming;
      $('eventIndependence').disabled = false;
      $('eventIndependence').value = draft.independenceDeclaration;
      for (const paw of ['A', 'B']) {
        $('eventPaw' + paw).disabled = false;
        $('eventPaw' + paw).value = draft.pawDescriptions[paw];
      }
      labels(); renderStrides();
    }
    $('eventStart').onclick = async () => {
      stopPlayback();
      try {
        const reviewer = $('eventReviewer').value.trim();
        if (!reviewer) throw Error('Enter your own reviewer ID. Use a different ID for the independent reviewer.');
        const ownKey = 'petlens-blind-gait-events-v1:' + base.manifestSha256 + ':' + group + ':' + encodeURIComponent(reviewer);
        const stored = localStorage.getItem(ownKey);
        const incoming = stored ? JSON.parse(stored) : structuredClone(base.draft);
        if (stored && incoming.reviewer !== reviewer) throw Error('Stored reviewer mismatch; draft preserved.');
        incoming.reviewer = reviewer;
        await post('validate', incoming);
        key = ownKey; activate(incoming); save();
        status(stored ? 'Resumed only your own event draft.' : 'Started a blank human review. No labels were generated.');
      } catch (e) { status(e.message); }
    };
    $('eventIndependence').onchange = () => { if (draft) { draft.independenceDeclaration = $('eventIndependence').value; save(); } };
    for (const paw of ['A', 'B']) $('eventPaw' + paw).oninput = () => {
      if (draft) { draft.pawDescriptions[paw] = $('eventPaw' + paw).value; save(); }
    };
    $('eventAddStride').onclick = () => {
      stopPlayback(); if (!draft) return status('Start your own review first.');
      draft.strides.push({id: crypto.randomUUID(), physicalPaw: selectedPaw, status: 'unreviewed',
        boundaries: Object.fromEntries(fields.map(([field]) => [field, null])), notes: ''});
      save(); renderStrides();
    };
    $('eventBackup').onclick = () => {
      if (!draft) return status('Start your own review first.');
      download(draft, group + '-my-event-review-draft.json');
    };
    $('eventImport').onchange = async () => {
      stopPlayback(); try {
        if (!draft) throw Error('Start your reviewer session before resuming a backup.');
        const file = $('eventImport').files[0]; if (!file) return;
        const incoming = JSON.parse(await file.text());
        if (incoming.reviewer !== draft.reviewer) throw Error('Cannot load another reviewer\'s labels into an independent review.');
        await post('validate', incoming); activate(incoming); save(); status('Resumed your source-verified draft.');
      } catch (e) { status(e.message); }
    };
    $('eventValidate').onclick = async () => {
      stopPlayback(); try {
        if (!draft) throw Error('Start your own review first.');
        const report = await (await post('validate', draft)).json();
        status(`${report.humanAssertedCompleteStrides} human complete assertions; ${report.unreviewedPawFrames} unreviewed paw-frames. Not adjudicated. Independence declared: ${report.independenceDeclared}.`);
      } catch (e) { status(e.message); }
    };
    $('eventExport').onclick = async () => {
      stopPlayback(); try {
        if (!draft) throw Error('Start your own review first.');
        const response = await post('export', draft), path = response.headers.get('X-PetLens-Export-Path');
        download(await response.blob(), path.split('/').at(-1));
        status('Saved ' + path + '. Human assertions only; second review and adjudication still required.');
      } catch (e) { status(e.message); }
    };
    $('frame').max = manifest.frameCount - 1;
    $('queue').replaceChildren(new Option(`Review frames ${manifest.reviewStart}–${manifest.reviewEnd}`, 'selected'),
      new Option('All original source frames: context', 'all'));
    $('queue').value = 'selected';
    $('prev').onclick = () => move(-1); $('next').onclick = () => move(1);
    $('go').onclick = () => { stopPlayback(); load(Number($('frame').value)).catch(error); };
    $('queue').onchange = () => { stopPlayback(); load(queue()[0]).catch(error); };
    playStep = async () => {
      if (!playing) return;
      const next = queue().find(i => i > current);
      if (next === undefined) { stopPlayback(); return; }
      try { await load(next); } catch (e) { stopPlayback(); error(e); return; }
      const following = queue().find(i => i > current);
      if (playing && following !== undefined) playbackTimer = setTimeout(playStep,
        (manifest.frames[following].timestampSeconds - manifest.frames[current].timestampSeconds) * 1000 / Number($('speed').value));
      else stopPlayback();
    };
    // Display each frame for its native source interval, including the first.
    togglePlayback = () => {
      if (playing) { stopPlayback(); return; }
      const next = queue().find(i => i > current); if (next === undefined) return;
      playing = true; $('play').textContent = 'Pause';
      playbackTimer = setTimeout(playStep,
        (manifest.frames[next].timestampSeconds - manifest.frames[current].timestampSeconds) * 1000 / Number($('speed').value));
    };
    $('play').onclick = togglePlayback;
    $('speed').onchange = () => { if (playing) { stopPlayback(); togglePlayback(); } };
    $('fitFrame').onchange = () => { $('image').style.maxHeight = $('fitFrame').checked ? '' : 'none'; };
    document.addEventListener('keydown', e => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.target.isContentEditable) return;
      if (['ArrowLeft', 'ArrowRight'].includes(e.key)) e.preventDefault();
      if (e.key === 'ArrowRight') move(1); if (e.key === 'ArrowLeft') move(-1);
    });
    await load(manifest.reviewStart);
  }
  return {boot};
})();
