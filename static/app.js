const ROLES = [
  ['CEO', '결론 내릴 사람', '👔'],
  ['마케팅팀장', '말은 매끈, 속은 계산', '📣'],
  ['디자이너', '픽셀에도 자존심 있음', '🎨'],
  ['개발자', '그건 개발 문제가 아닙니다', '💻'],
  ['운영 담당자', '결국 제가 하죠?', '📋'],
  ['소비자 대표', '오, 그건 좋은데요?', '🛒'],
  ['클라이언트', '조금만 더 크게요', '☝️'],
];

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

const ui = {
  setupView: $('#setupView'),
  meetingView: $('#meetingView'),
  topic: $('#topic'),
  participantGrid: $('#participantGrid'),
  participantCount: $('#participantCount'),
  secretaryHint: $('#secretaryHint'),
  startButton: $('#startButton'),
  formError: $('#formError'),
  agendaTitle: $('#agendaTitle'),
  roomStage: $('#roomStage'),
  table: $('#table'),
  seats: $('#seats'),
  seatWrapper: $('#seatWrapper'),
  roleLabels: $('#roleLabels'),
  turnLabel: $('#turnLabel'),
  timer: $('#timer'),
  secretaryDesk: $('#secretaryDesk'),
  secretaryText: $('#secretaryText'),
  minutesButton: $('#minutesButton'),
  minutesCount: $('#minutesCount'),
  minutesPanel: $('#minutesPanel'),
  minutesBackdrop: $('#minutesBackdrop'),
  minutesList: $('#minutesList'),
  meetingRecordMeta: $('#meetingRecordMeta'),
  finalSummary: $('#finalSummary'),
  minutesSectionTitle: $('#minutesSectionTitle'),
  activeSpeechBubble: $('#activeSpeechBubble'),
  bubbleSpeaker: $('#bubbleSpeaker'),
  bubbleText: $('#bubbleText'),
  endOverlay: $('#endOverlay'),
  endIcon: $('#endIcon'),
  endKicker: $('#endKicker'),
  endTitle: $('#endTitle'),
  endTimeSaved: $('#endTimeSaved'),
  endDecision: $('#endDecision'),
  meetingStatus: $('#meetingStatus'),
  newMeetingConfirm: $('#newMeetingConfirm'),
};

const state = {
  paused: false,
  human: false,
  holdCallback: null,
  holdRemaining: 0,
  holdDeadline: 0,
  currentSpeechId: null,
  humanSending: false,
  duration: 3,
  selected: new Set(),
  eventSource: null,
  meetingId: null,
  minutes: [],
  activeSpeaker: null,
  ended: false,
  participants: [],
  displayedMs: 180000,
  lastTimerFrameAt: performance.now(),
  timerRaf: null,
  timerRunning: false,
  summary: null,
  queue: [],
  queueBusy: false,
  queueTimer: null,
  queueGeneration: 0,
  timeExpired: false,
  topic: '',
  plannedMs: 180000,
  actualMeetingMs: null,
};

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text ?? '';
  return div.innerHTML;
}

/* ---------- Participant setup ---------- */
function buildParticipantCards() {
  ui.participantGrid.replaceChildren();

  ROLES.forEach(([role, tag, emoji]) => {
    const label = document.createElement('label');
    label.className = 'participant-card';
    label.innerHTML = `
      <input type="checkbox" value="${escapeHtml(role)}">
      <div class="mini-face" aria-hidden="true">${emoji}</div>
      <div>
        <span class="participant-name">${escapeHtml(role)}</span>
        <span class="participant-tag">${escapeHtml(tag)}</span>
      </div>`;

    const input = label.querySelector('input');
    input.addEventListener('change', () => {
      input.checked ? state.selected.add(role) : state.selected.delete(role);
      label.classList.toggle('selected', input.checked);
      refreshStartState();
    });

    ui.participantGrid.appendChild(label);
  });
}

function refreshStartState() {
  const count = state.selected.size;
  ui.participantCount.textContent = `${count}명 선택`;
  ui.startButton.disabled = count < 2 || !ui.topic.value.trim();

  if (count === 0) ui.secretaryHint.textContent = '서기: 최소 두 명은 불러주세요.';
  else if (count === 1) ui.secretaryHint.textContent = '서기: ……회의 맞습니까?';
  else if (count === 2) ui.secretaryHint.textContent = '서기: 1:1 면담… 아니, 회의로 기록하겠습니다.';
  else ui.secretaryHint.textContent = `서기: ${count}명. 키보드 예열 중입니다.`;
}

/* ---------- Seat geometry ---------- */
function getSeatGeometry(count) {
  const mobile = matchMedia('(max-width: 767px)').matches;
  const shortDesktop = innerHeight < 760 && !mobile;

  if (mobile) {
    return {
      cx: 50,
      cy: 59,
      rx: Math.min(33, 21 + count * 1.55),
      ry: Math.min(24, 16 + count * 1.05),
    };
  }

  if (shortDesktop) {
    return {
      cx: 50,
      cy: 55,
      rx: Math.min(31, 21 + count * 1.35),
      ry: Math.min(27, 18 + count * 1.05),
    };
  }

  return {
    cx: 50,
    cy: 55,
    rx: Math.min(33, 22 + count * 1.45),
    ry: Math.min(29, 19 + count * 1.1),
  };
}

function keepSeatsInsideStage() {
  const stage = ui.roomStage.getBoundingClientRect();
  const padding = 12;

  $$('.seat').forEach(seat => {
    const rect = seat.getBoundingClientRect();
    const centerX = seat.style.left.endsWith('%')
      ? parseFloat(seat.style.left) / 100 * stage.width
      : parseFloat(seat.style.left);
    const centerY = seat.style.top.endsWith('%')
      ? parseFloat(seat.style.top) / 100 * stage.height
      : parseFloat(seat.style.top);

    const halfW = rect.width / 2;
    const halfH = rect.height / 2;
    const minX = padding + halfW;
    const minY = padding + halfH;
    const maxX = Math.max(minX, stage.width - padding - halfW);
    const maxY = Math.max(minY, stage.height - padding - halfH);

    seat.style.left = `${clamp(centerX, minX, maxX)}px`;
    seat.style.top = `${clamp(centerY, minY, maxY)}px`;
  });
}

let carouselPhase = 0;
let carouselTarget = null;
let carouselFrame = null;

function updateMobileSeatFocus() {
  if (matchMedia('(max-width: 900px)').matches) return;
  if (carouselFrame) cancelAnimationFrame(carouselFrame);
  carouselFrame = null;
  carouselTarget = null;
  $$('.seat').forEach(node => {
    node.classList.remove('mobile-focus', 'mobile-peer');
    for (const prop of ['--seat-scale', '--seat-opacity', '--seat-visibility', '--carousel-size']) node.style.removeProperty(prop);
  });
  $$('.floating-role-badge').forEach(node => node.classList.remove('mobile-focus', 'mobile-peer'));
}

function positionCarousel(nodes, labels, width, tableTop, wrapperLeft, wrapperTop) {
  const count = nodes.length;
  const focus = Math.max(0, nodes.findIndex(n => n.dataset.role === state.activeSpeaker));
  const size = Math.min(150, Math.max(110, (width - 24) / (1 + .72 * (Math.min(Math.max(count, 3), 5) - 1))));
  const gap = size * .72;
  // Fade the whole person before it reaches a wrap point or the room edge.
  // There are no clipped boundary copies, including for two/three attendees.
  const edge = Math.min(count / 2, (width / 2 - size / 2 - 12) / gap);
  const fadeStart = Math.floor(edge - .001);
  const draw = phase => {
    nodes.forEach((node, index) => {
      const slot = count === 2 ? index - phase : ((index - phase + count / 2) % count + count) % count - count / 2;
      const distance = Math.abs(slot);
      const scale = distance < 1 ? 1 - distance * .16 : Math.max(.8, .84 - (distance - 1) * .02);
      const active = index === focus;
      const visibility = count === 2 ? 1 : clamp((edge - distance) / (edge - fadeStart), 0, 1);
      node.style.setProperty('--seat-opacity', visibility * (active ? 1 : .58));
      node.style.setProperty('--seat-visibility', visibility > 0 ? 'visible' : 'hidden');
      node.classList.toggle('mobile-focus', active);
      node.classList.toggle('mobile-peer', !active);
      node.style.setProperty('--carousel-size', `${size}px`);
      node.style.setProperty('--seat-scale', scale);
      node.style.left = `${width / 2 + slot * gap}px`;
      // Let the foreground table cover the speaker's lower body. A centered
      // carousel speaker is larger than peers, so the old 3px overlap made
      // that person look perched on the table edge at tablet/phone widths.
      node.style.top = `${tableTop - wrapperTop + (active ? 14 : 10)}px`;
      const label = labels.find(n => n.dataset.role === node.dataset.role);
      if (label) {
        label.classList.toggle('mobile-focus', active);
        label.classList.toggle('mobile-peer', !active);
        label.style.left = `${wrapperLeft + width / 2}px`;
        label.style.top = `${Math.round(tableTop + 14)}px`;
      }
    });
  };
  if (carouselTarget === null) {
    carouselPhase = focus;
    carouselTarget = focus;
  }
  const delta = count === 2 ? focus - carouselPhase : ((focus - carouselPhase + count / 2) % count + count) % count - count / 2;
  const target = carouselPhase + delta;
  if (carouselTarget !== focus) {
    if (carouselFrame) cancelAnimationFrame(carouselFrame);
    carouselTarget = focus;
    const from = carouselPhase;
    const started = performance.now();
    const tick = now => {
      const t = Math.min(1, (now - started) / 440);
      carouselPhase = from + (target - from) * (1 - Math.pow(1 - t, 3));
      draw(carouselPhase);
      carouselFrame = t < 1 ? requestAnimationFrame(tick) : null;
    };
    carouselFrame = requestAnimationFrame(tick);
  } else if (!carouselFrame) draw(carouselPhase);
}
function positionSeats() {
  const nodes = $$('.seat');
  const labels = $$('.floating-role-badge');
  if (!nodes.length) return;

  const mobile = matchMedia('(max-width: 900px)').matches;
  const phone = matchMedia('(max-width: 767px)').matches;
  const tabletRow = matchMedia('(min-width: 901px) and (max-width: 1560px)').matches;
  const stageRect = ui.roomStage.getBoundingClientRect();
  const seatWrapRect = ui.seatWrapper.getBoundingClientRect();
  const count = nodes.length;
  const tableRect = ui.table.getBoundingClientRect();
  const tableTop = tableRect.top - stageRect.top;
  const wrapperLeft = seatWrapRect.left - stageRect.left;

  const setLabel = (seat, localXPx) => {
    const label = labels.find(item => item.dataset.role === seat.dataset.role);
    if (!label) return;
    label.style.left = `${Math.round(wrapperLeft + localXPx)}px`;
    // Labels sit inside the tabletop, below its top edge.
    label.style.top = `${Math.round(tableTop + (mobile ? 14 : 13))}px`;
  };

  if (mobile) {
    if (!seatWrapRect.width) return;
    positionCarousel(nodes, labels, seatWrapRect.width, tableTop, wrapperLeft, seatWrapRect.top - stageRect.top);
  } else {
    updateMobileSeatFocus();
    nodes.forEach(node => node.classList.remove('mobile-focus','mobile-peer'));
    labels.forEach(node => node.classList.remove('mobile-focus','mobile-peer'));

    // Desktop seats live inside one centered max-width wrapper (~1200px).
    // This keeps the 7-seat line away from the secretary without ad-hoc last-seat offsets.
    const largestSeatHalf = Math.max(...nodes.map(n => n.getBoundingClientRect().width / 2), 54);
    const leftBound = 14 + largestSeatHalf;
    const rightBound = Math.max(leftBound + 120, seatWrapRect.width - 14 - largestSeatHalf);
    const usable = rightBound - leftBound;
    const spanRatio = count <= 2 ? .38 : count <= 4 ? .66 : 1;
    const span = usable * spanRatio;
    const startX = leftBound + (usable - span) / 2;
    const endX = startX + span;

    nodes.forEach((seat, index) => {
      const t = count === 1 ? .5 : index / (count - 1);
      const x = startX + (endX - startX) * t;
      seat.style.left = `${Math.round(x)}px`;

      // Keep every body on the same tabletop line. Mid-width screens use one small
      // shared drop; the active speaker must not sink farther than the other attendees.
      const tabletDrop = tabletRow ? 10 : 0;
      seat.style.top = `${Math.round(tableTop - 68 + tabletDrop)}px`;
      setLabel(seat, x);
    });
  }

  requestAnimationFrame(() => {
    if (state.activeSpeaker && !ui.activeSpeechBubble.classList.contains('hidden')) {
      positionSpeechBubble(state.activeSpeaker);
    }
  });
}
function buildSeats(participants) {
  if (carouselFrame) cancelAnimationFrame(carouselFrame);
  carouselFrame = null;
  carouselTarget = null;
  ui.seats.replaceChildren();
  ui.roleLabels?.replaceChildren();
  state.participants = [...participants];

  participants.forEach(role => {
    const seat = document.createElement('div');
    const emoji = role === '나' ? '🙋' : ROLES.find(item => item[0] === role)?.[2] || '•';
    seat.className = 'seat';
    seat.dataset.role = role;
    const characterAssets = {
      'CEO': ['ceo', 'ceo_base.png'],
      '운영 담당자': ['operation', 'operation_base.png'],
      '마케팅팀장': ['marketing', 'marketing_base.png'],
      '소비자 대표': ['consumer', 'consumer_base.png'],
      '디자이너': ['designer', 'designer_base.png'],
      '클라이언트': ['client', 'client_base.png'],
      '개발자': ['developer', 'developer_base.png'],
      '나': ['human', 'human_base.png'],
    };
    const asset = characterAssets[role];
    const avatarMarkup = asset
      ? `<div class="avatar avatar-asset ${asset[0]}-avatar"><img src="/static/assets/characters/${asset[0]}/${asset[1]}" data-folder="${asset[0]}" data-base-src="/static/assets/characters/${asset[0]}/${asset[1]}" alt="${escapeHtml(role)}"></div>`
      : `<div class="avatar human-avatar" aria-label="나"><i class="fa-solid fa-user" aria-hidden="true"></i></div>`;

    seat.innerHTML = avatarMarkup + '<span class="expression-mark" aria-hidden="true"></span>';
    ui.seats.appendChild(seat);
    if (asset) {
      ['talking', 'thinking', 'pleased'].forEach(expression => {
        const preload = new Image();
        preload.src = `/static/assets/characters/${asset[0]}/${asset[0]}_${expression}.png`;
      });
    }

    if (ui.roleLabels) {
      const badge = document.createElement('div');
      badge.className = 'floating-role-badge';
      badge.dataset.role = role;
      badge.innerHTML = `${emoji} ${escapeHtml(role)}`;
      ui.roleLabels.appendChild(badge);
    }
  });

  positionSeats();
}

function setSeatSprite(node, expression = 'neutral', active = false) {
  const img = node.querySelector('.avatar-asset img');
  if (!img) return;
  const folder = img.dataset.folder;
  const state = active
    ? ({thinking: 'thinking', unconvinced: 'thinking', pleased: 'pleased'}[expression] || 'talking')
    : 'base';
  const nextSrc = state === 'base'
    ? img.dataset.baseSrc
    : `/static/assets/characters/${folder}/${folder}_${state}.png`;
  if (img.getAttribute('src') === nextSrc) return;
  img.onerror = () => {
    img.onerror = null;
    img.src = img.dataset.baseSrc;
  };
  img.src = nextSrc;
}

/* ---------- Speech bubble placement ---------- */
function intersectionArea(a, b) {
  const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
  const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  return width * height;
}

function localRect(rect, stage, padding = 0) {
  return {
    left: rect.left - stage.left - padding,
    top: rect.top - stage.top - padding,
    right: rect.right - stage.left + padding,
    bottom: rect.bottom - stage.top + padding,
  };
}

function positionSpeechBubble(role) {
  const seat = $$('.seat').find(node => node.dataset.role === role);
  if (!seat || ui.activeSpeechBubble.classList.contains('hidden')) return;

  const stage = ui.roomStage.getBoundingClientRect();
  if (!stage.width || !stage.height) return;

  const mobile = matchMedia('(max-width: 767px)').matches;
  const narrow = matchMedia('(max-width: 900px)').matches;
  const margin = mobile ? 10 : 14;
  const gap = mobile ? 68 : 70;

  ui.activeSpeechBubble.style.left = '';
  ui.activeSpeechBubble.style.top = '';
  ui.activeSpeechBubble.style.right = '';
  ui.activeSpeechBubble.style.bottom = '';
  ui.activeSpeechBubble.dataset.direction = 'top';

  // Everyone sits on one horizontal table line, so every bubble opens ABOVE the speaker.
  const targetWidth = mobile
    ? Math.max(220, stage.width - margin * 2)
    : Math.min(380, stage.width - margin * 2);
  ui.activeSpeechBubble.style.width = `${targetWidth}px`;

  const speaker = localRect(seat.getBoundingClientRect(), stage, 2);
  const bubbleRect = ui.activeSpeechBubble.getBoundingClientRect();
  const width = bubbleRect.width;
  const height = bubbleRect.height;
  const cx = narrow ? ui.roomStage.clientWidth / 2 : (speaker.left + speaker.right) / 2;

  const left = clamp(cx - width / 2, margin, Math.max(margin, stage.width - width - margin));
  const poster = $('.wall-poster')?.getBoundingClientRect();
  const posterBottom = poster ? poster.bottom - stage.top + 10 : margin;
  const preferredTop = speaker.top - height - gap;
  const top = clamp(preferredTop, Math.max(margin, posterBottom), Math.max(margin, stage.height - height - margin));

  ui.activeSpeechBubble.style.left = `${left}px`;
  const appliedTop = mobile ? 'calc(50% - 140px)' : `${top}px`;
  ui.activeSpeechBubble.style.top = appliedTop;
  ui.activeSpeechBubble.style.setProperty('--bubble-left', `${left}px`);
  ui.activeSpeechBubble.style.setProperty('--bubble-top', appliedTop);
  ui.activeSpeechBubble.style.setProperty('--bubble-width', `${width}px`);

  // Tail never disappears. On mobile the focused speaker is always centered, so keep the tail centered too.
  const tailX = narrow ? width / 2 : clamp(cx - left, 20, width - 20);
  ui.activeSpeechBubble.style.setProperty('--tail-x', `${tailX}px`);
}
function reflowMeetingLayout() {
  if (ui.meetingView.classList.contains('hidden')) return;
  positionSeats();
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (state.activeSpeaker && !ui.activeSpeechBubble.classList.contains('hidden')) {
        positionSpeechBubble(state.activeSpeaker);
      }
    });
  });
}

function setSpeaker(role, speech, expression = 'neutral') {
  $$('.seat').forEach(node => node.classList.remove('active', 'skip'));
  $$('.floating-role-badge').forEach(node => node.classList.remove('active', 'skip'));
  const seat = $$('.seat').find(node => node.dataset.role === role);
  if (!seat) return;

  state.activeSpeaker = role;
  seat.classList.add('active');
  $$('.floating-role-badge').find(node => node.dataset.role === role)?.classList.add('active');
  updateMobileSeatFocus();
  if (matchMedia('(max-width: 1560px)').matches) positionSeats();
  ui.bubbleSpeaker.textContent = role;
  renderSpeech(ui.bubbleText, speech);
  const reactionAssets = {
    neutral: '',
    talking: '',
    thinking: '/static/assets/reactions/reaction_lightbulb.png',
    surprised: '/static/assets/reactions/reaction_exclamation.png',
    pleased: '/static/assets/reactions/reaction_heart.png',
    unconvinced: '/static/assets/reactions/reaction_question.png',
  };
  const reactionAsset = reactionAssets[expression] || '';
  $$('.seat, .loop-copy').forEach(node => {
    const current = node.dataset.role === role;
    node.dataset.expression = current ? expression : 'neutral';
    setSeatSprite(node, current ? expression : 'neutral', current);
    const mark = node.querySelector('.expression-mark');
    if (mark) mark.innerHTML = current && reactionAsset
      ? `<img src="${reactionAsset}" alt="">`
      : '';
  });
  ui.activeSpeechBubble.classList.remove('hidden');
  requestAnimationFrame(() => positionSpeechBubble(role));
}

function closeActiveSpeech() {
  state.activeSpeaker = null;
  ui.activeSpeechBubble.classList.add('hidden');
  ui.bubbleSpeaker.textContent = '';
  ui.bubbleText.textContent = '';
  $$('.seat').forEach(node => node.classList.remove('active', 'skip'));
  $$('.seat').forEach(node => setSeatSprite(node));
  $$('.floating-role-badge').forEach(node => node.classList.remove('active', 'skip'));
  updateMobileSeatFocus();
  if (matchMedia('(max-width: 1560px)').matches) positionSeats();
}

function reactSkip(role) {
  const seat = $$('.seat').find(node => node.dataset.role === role);
  if (!seat || state.ended) return;
  seat.classList.add('skip');
  setTimeout(() => seat.classList.remove('skip'), 850);
}

/* ---------- Paced presentation ---------- */
function speechHoldMs(text) {
  return Math.round(clamp(3000 + [...String(text || '').replaceAll('**', '')].length * 34, 3000, 7000) * 1.35);
}

function clearPresentationQueue() {
  state.queueGeneration += 1;
  state.queue = [];
  state.queueBusy = false;
  clearTimeout(state.queueTimer);
  state.queueTimer = null;
  state.holdCallback = null;
  state.holdRemaining = 0;
}

function enqueuePresentation(item) {
  if (state.timeExpired || state.ended) return;
  state.queue.push(item);
  if (item.type === 'speech') {
    ui.meetingStatus.classList.remove('waiting');
    ui.secretaryDesk.classList.remove('waiting');
  }
  pumpPresentationQueue();
}

function pumpPresentationQueue() {
  if (state.paused || state.queueBusy || state.ended || !state.queue.length) return;

  state.queueBusy = true;
  const generation = state.queueGeneration;
  const item = state.queue.shift();
  let hold = 450;

  if (item.type === 'speech') {
    setPlaybackClock(true);
    state.currentSpeechId = item.data.id || null;
    setSpeaker(item.data.speaker, item.data.speech, item.data.expression);
    addMinute('speech', item.data.speaker, item.data.speech);
    ui.turnLabel.textContent = '회의 중';
    ui.meetingStatus.textContent = '회의 중';
    hold = speechHoldMs(item.data.speech);
  } else if (item.type === 'secretary') {
    ui.secretaryText.textContent = item.data.text;
    addMinute('secretary', '서기', item.data.text);
    hold = 1500;
  } else if (item.type === 'reaction') {
    reactSkip(item.data.speaker);
    hold = 500;
  } else if (item.type === 'ending') {
    closeActiveSpeech();
    ui.secretaryText.textContent = '결론 정리 중...';
    ui.meetingStatus.textContent = '결론 정리 중';
    hold = 1100;
  } else if (item.type === 'summary') {
    state.queueBusy = false;
    showSummary(item.data);
    return;
  }

  schedulePresentation(() => {
    if (generation !== state.queueGeneration) return;
    state.queueBusy = false;
    if (item.type === 'speech' && item.data.id) sendMeetingCommand('ack', {id: item.data.id}).catch(error => { $('#humanFeedback').textContent = error.message; });
    state.currentSpeechId = null;
    if (state.timeExpired) { finishByTimeLimit(); return; }
    schedulePresentation(() => {
      if (generation !== state.queueGeneration) return;
      if (!state.queue.length) setPlaybackClock(false);
      pumpPresentationQueue();
    }, 420);
  }, hold);
}

function renderSpeech(element, text) {
  element.replaceChildren();
  // Only paired bold markers are supported; HTML remains literal text.
  const parts = String(text).split(/(\*\*[^*\n]+\*\*)/g);
  for (const part of parts) {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      const strong = document.createElement('strong');
      strong.textContent = part.slice(2, -2);
      element.appendChild(strong);
    } else element.appendChild(document.createTextNode(part));
  }
}

function schedulePresentation(callback, ms) {
  clearTimeout(state.queueTimer);
  state.holdCallback = callback;
  state.holdRemaining = ms;
  state.holdDeadline = performance.now() + ms;
  if (state.paused) return;
  state.queueTimer = setTimeout(() => {
    state.queueTimer = null;
    state.holdCallback = null;
    callback();
  }, ms);
}

function togglePause() {
  if (state.ended || state.timeExpired) return;
  state.paused = !state.paused;
  const button = $('#pauseMeeting');
  button.setAttribute('aria-label', state.paused ? '계속' : '일시정지');
  button.title = state.paused ? '계속' : '일시정지';
  button.setAttribute('aria-pressed', String(state.paused));
  button.innerHTML = `<i class="fa-solid ${state.paused ? 'fa-play' : 'fa-pause'}" aria-hidden="true"></i>`;
  ui.roomStage.classList.toggle('playback-paused', state.paused);
  if (state.paused) {
    state.holdRemaining = Math.max(0, state.holdDeadline - performance.now());
    clearTimeout(state.queueTimer);
    state.queueTimer = null;
    setPlaybackClock(false);
    ui.meetingStatus.textContent = '일시정지';
    ui.turnLabel.textContent = '일시정지';
  } else {
    if (state.holdCallback) schedulePresentation(state.holdCallback, state.holdRemaining);
    setPlaybackClock(state.queueBusy && Boolean(state.activeSpeaker));
    ui.meetingStatus.textContent = state.activeSpeaker ? '회의 중' : '생각 중...';
    ui.turnLabel.textContent = state.activeSpeaker ? '회의 중' : '생각 중...';
    if (!state.queueBusy) pumpPresentationQueue();
  }
}

async function sendMeetingCommand(type, data = {}) {
  if (!state.human || !state.meetingId || state.ended) return;
  const response = await fetch(`/api/command?id=${encodeURIComponent(state.meetingId)}`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type, ...data})
  });
  if (!response.ok) throw new Error((await response.json()).error || '전송하지 못했습니다.');
}

async function submitHuman(event) {
  event.preventDefault();
  const input = $('#humanText');
  const text = input.value.trim();
  if (!text || state.humanSending || state.ended || state.timeExpired) return;
  state.humanSending = true;
  $('#humanSend').disabled = true;
  $('#humanFeedback').textContent = '의견 전달 중…';
  try {
    await sendMeetingCommand('human', {text, id: crypto.randomUUID()});
    input.value = '';
    $('#humanFeedback').textContent = '의견을 전달했습니다.';
  } catch (error) { $('#humanFeedback').textContent = error.message; }
  finally { state.humanSending = false; $('#humanSend').disabled = state.ended || state.timeExpired || $('#humanText').disabled; }
}

/* ---------- Timer ---------- */
function formatMs(ms) {
  const value = Math.max(0, Math.round(ms));
  const minutes = Math.floor(value / 60000);
  const seconds = Math.floor((value % 60000) / 1000);
  const millis = value % 1000;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`;
}

function renderTimer() {
  ui.timer.textContent = formatMs(state.displayedMs);
  ui.timer.classList.toggle('danger', state.displayedMs <= 30000 && !state.ended);
}

function timerLoop(now) {
  const elapsed = Math.max(0, now - state.lastTimerFrameAt);
  state.lastTimerFrameAt = now;

  if (state.ended) {
    renderTimer();
    state.timerRaf = null;
    return;
  }

  if (state.timerRunning && !state.paused) {
    state.displayedMs = Math.max(0, state.displayedMs - elapsed);
    if (state.displayedMs <= 0 && !state.timeExpired) {
      state.timeExpired = true;
      state.timerRunning = false;
      state.queue = [];
      state.eventSource?.close();
      state.eventSource = null;
      cancelActiveMeeting();
      // The currently visible speaker is allowed to finish its presentation hold.
      // If no speech is being presented, finish immediately.
      if (!state.queueBusy) finishByTimeLimit();
    }
  }

  renderTimer();
  state.timerRaf = requestAnimationFrame(timerLoop);
}

function startTimerLoop(initialMs) {
  if (state.timerRaf) cancelAnimationFrame(state.timerRaf);
  state.displayedMs = initialMs;
  state.lastTimerFrameAt = performance.now();
  state.timerRunning = false;
  renderTimer();
  state.timerRaf = requestAnimationFrame(timerLoop);
}

function setPlaybackClock(running) {
  state.timerRunning = Boolean(running) && !state.ended && !state.paused;
  state.lastTimerFrameAt = performance.now();

  const waiting = !state.timerRunning && !state.ended && !state.paused;
  ui.meetingStatus.classList.toggle('waiting', waiting);
  ui.secretaryDesk.classList.toggle('waiting', waiting);
  ui.table.classList.toggle('waiting', waiting);
  // Before a meeting the table says it is preparing. Once started, waiting for
  // the next model response is thinking time, shown on the same line as the spinner.
  if (waiting) {
    const hasPresentedSpeech = state.minutes.some(item => item.type === 'speech');
    const waitingText = hasPresentedSpeech ? '생각 중...' : '회의 준비 중...';
    ui.turnLabel.textContent = waitingText;
    ui.meetingStatus.textContent = waitingText;
  } else if (state.timerRunning) {
    ui.meetingStatus.textContent = '회의 중';
  }

  if (waiting && !state.queueBusy && !state.queue.length) {
    ui.secretaryText.textContent = '다음 발언 준비 중...';
  }
}

function finishByTimeLimit() {
  if (state.ended) return;
  state.displayedMs = 0;
  showSummary({
    status: 'unresolved',
    mode: 'none',
    decisions: [],
    proposals: [],
    actions: [],
    unknowns: [],
    issues: ['시간 제한으로 회의가 종료되었습니다.'],
    counts: {},
    end_reason: 'time',
  });
}

function formatDurationLabel(ms) {
  const totalSeconds = Math.max(0, Math.round(Number(ms || 0) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes && seconds) return `${minutes}분 ${seconds}초`;
  if (minutes) return `${minutes}분`;
  return `${seconds}초`;
}

function currentActualMeetingMs() {
  if (state.actualMeetingMs !== null) return state.actualMeetingMs;
  return Math.max(0, Number(state.plannedMs || 0) - Number(state.displayedMs || 0));
}

function conclusionHtml() {
  if (!state.summary) return '<p class="empty-note">회의 진행 중</p>';
  return `<div class="record-status">${escapeHtml(summaryStatusLabel(state.summary.status))}</div>${renderSummarySections(state.summary)}`;
}

function renderMeetingRecord() {
  const topic = state.topic || ui.agendaTitle.textContent.trim() || '-';
  const participants = state.participants.length ? state.participants.join(', ') : '-';
  const planned = formatDurationLabel(state.plannedMs);
  const actual = formatDurationLabel(currentActualMeetingMs());

  ui.meetingRecordMeta.innerHTML = `
    <dl class="meeting-record-grid">
      <div><dt>회의 주제</dt><dd>${escapeHtml(topic)}</dd></div>
      <div><dt>참석자</dt><dd>${escapeHtml(participants)}</dd></div>
      <div class="meeting-time-row"><dt>회의 시간</dt><dd>${escapeHtml(planned)} <span class="actual-time-inline">(실제 회의 시간 ${escapeHtml(actual)})</span></dd></div>
    </dl>`;

  ui.finalSummary.innerHTML = `<h4 class="record-section-title">결론</h4>${conclusionHtml()}`;
  ui.finalSummary.classList.remove('hidden');
}

function copyConclusionText() {
  if (!state.summary) return '회의 진행 중';
  const sections = summarySections(state.summary);
  const status = summaryStatusLabel(state.summary.status);
  const body = sections.map(section => {
    const items = section.items.length
      ? section.items.map(item => `- ${summaryItemText(item)}`).join('\n')
      : '- 없음';
    return `[${section.title}]\n${items}`;
  }).join('\n\n');
  return `${status}\n${body}`;
}

/* ---------- Minutes + summary ---------- */
function addMinute(type, speaker, text) {
  state.minutes.push({ type, speaker, text });
  ui.minutesCount.textContent = state.minutes.length;

  const item = document.createElement('div');
  item.className = `minute-item${type === 'secretary' ? ' secretary' : ''}`;

  if (speaker) {
    const strong = document.createElement('strong');
    strong.textContent = speaker;
    item.appendChild(strong);
  }

  const span = document.createElement('span');
  span.textContent = text;
  item.appendChild(span);
  ui.minutesList.appendChild(item);
  if (ui.minutesPanel.classList.contains('open')) renderMeetingRecord();
}

function summaryStatusLabel(status) {
  if (status === 'decided') return '✅ 결정 완료';
  if (status === 'deferred') return '⏸️ 결정 보류';
  if (status === 'discussed') return '💬 의견 정리';
  return '⚠️ 미해결';
}

function summarySections(data) {
  const sections = [];
  if (data.decisions?.length) sections.push({ title: '결정된 내용', items: data.decisions });
  if (data.proposals?.length) sections.push({ title: '논의된 방향 · 미확정 제안', items: data.proposals });
  if (data.actions?.length) sections.push({ title: '다음 액션', items: data.actions });
  if (data.issues?.length && data.status !== 'decided') sections.push({ title: '남은 쟁점', items: data.issues });
  if (data.unknowns?.length && data.status !== 'decided') sections.push({ title: '확인이 필요한 정보', items: data.unknowns });
  if (!sections.length) sections.push({ title: '결과', items: [] });
  return sections;
}

function summaryItemText(item) {
  if (item && typeof item === 'object') return String(item.content ?? item.text ?? item.value ?? '');
  return String(item ?? '');
}

function renderSummarySections(data) {
  return summarySections(data).map(section => `
    <section class="summary-section">
      <h4>${escapeHtml(section.title)}</h4>
      ${section.items.length
        ? `<ul>${section.items.map(item => `<li>${escapeHtml(summaryItemText(item))}</li>`).join('')}</ul>`
        : '<p class="empty-note">정리된 항목이 없습니다.</p>'}
    </section>
  `).join('');
}

function endTitleFor(data) {
  if (data.status === 'decided') return '결론이 정리되었습니다.';
  if (data.status === 'deferred') return '지금은 결정하지 않기로 했습니다.';
  if (data.status === 'discussed') return '나온 이야기를 정리했습니다.';
  if (data.end_reason === 'stalled') return '같은 논의가 반복돼 여기서 끊었습니다.';
  if (data.end_reason === 'time') return '회의 시간이 끝났습니다.';
  return '결론 없이 회의가 끝났습니다.';
}

function showSummary(data) {
  state.ended = true;
  $('#pauseMeeting').disabled = true;
  $('#humanSend').disabled = true;
  $('#humanText').disabled = true;
  state.summary = data;
  state.actualMeetingMs = Math.max(0, Number(state.plannedMs || 0) - Number(state.displayedMs || 0));
  state.timerRunning = false;

  ui.meetingStatus.classList.remove('waiting');
  ui.secretaryDesk.classList.remove('waiting');
  if (state.timerRaf) cancelAnimationFrame(state.timerRaf);
  state.timerRaf = null;

  closeActiveSpeech();
  ui.secretaryDesk.classList.add('stopped');
  ui.meetingStatus.textContent = '회의 종료';

  renderMeetingRecord();

  ui.secretaryText.textContent =
    data.status === 'decided' ? '결론까지 기록 완료.' :
    data.status === 'deferred' ? '모르는 걸 아는 척하지 않은 회의였습니다.' :
    data.status === 'discussed' ? '각자의 이야기를 그대로 정리했습니다.' :
    '결론은 없지만 기록은 남겼습니다.';

  ui.turnLabel.textContent = '회의 종료';
  ui.endIcon.dataset.status = data.status || 'unresolved';
  ui.endIcon.className = `end-icon fa-solid ${
    data.status === 'decided' ? 'fa-circle-check' :
    data.status === 'deferred' ? 'fa-circle-pause' :
    data.status === 'discussed' ? 'fa-comments' :
    'fa-triangle-exclamation'
  }`;

  ui.endKicker.textContent =
    data.status === 'decided' ? '회의 종료' :
    data.status === 'deferred' ? '오늘은 여기까지' :
    data.status === 'discussed' ? '이야기 정리' :
    '회의 종료 · 미해결';

  ui.endTitle.textContent = endTitleFor(data);
  ui.endTimeSaved.textContent = state.displayedMs > 900
    ? `${formatMs(state.displayedMs)} 남김`
    : '시간을 거의 다 썼습니다.';
  ui.endDecision.innerHTML = renderSummarySections(data);
  ui.endOverlay.classList.remove('hidden');
}

/* ---------- Meeting lifecycle ---------- */
function resetMeetingState() {
  clearPresentationQueue();
  state.ended = false;
  state.paused = false;
  state.humanSending = false;
  state.currentSpeechId = null;
  $('#pauseMeeting').disabled = false;
  $('#pauseMeeting').setAttribute('aria-label', '일시정지');
  $('#pauseMeeting').setAttribute('aria-pressed', 'false');
  $('#pauseMeeting').innerHTML = '<i class="fa-solid fa-pause" aria-hidden="true"></i>';
  ui.roomStage.classList.remove('playback-paused');
  $('#humanText').disabled = false;
  $('#humanText').value = '';
  $('#humanSend').disabled = false;
  $('#humanFeedback').textContent = '';
  state.timeExpired = false;
  state.timerRunning = false;
  state.summary = null;
  state.minutes = [];
  state.activeSpeaker = null;
  state.participants = [];
  state.topic = '';
  state.plannedMs = state.duration * 60 * 1000;
  state.actualMeetingMs = null;

  if (state.timerRaf) cancelAnimationFrame(state.timerRaf);
  state.timerRaf = null;
  state.displayedMs = state.duration * 60 * 1000;
  state.lastTimerFrameAt = performance.now();

  closeActiveSpeech();
  ui.seats.replaceChildren();
  ui.minutesList.replaceChildren();
  ui.minutesCount.textContent = '0';
  ui.finalSummary.replaceChildren();
  ui.finalSummary.classList.add('hidden');
  ui.endDecision.replaceChildren();
  ui.endTimeSaved.textContent = '';
  ui.endOverlay.classList.add('hidden');
  ui.endIcon.dataset.status = 'decided';
  ui.endIcon.className = 'end-icon fa-solid fa-circle-check';
  ui.secretaryDesk.classList.remove('stopped', 'waiting');
  ui.table.classList.remove('waiting');
  ui.secretaryText.textContent = '회의록 준비 중...';
  ui.turnLabel.textContent = '회의 준비 중...';
  ui.meetingStatus.textContent = '회의 준비 중...';
  ui.meetingStatus.classList.remove('waiting');
  renderTimer();
}

async function startMeeting() {
  ui.formError.textContent = '';
  ui.startButton.disabled = true;
  ui.startButton.textContent = '회의실 여는 중...';

  const payload = {
    topic: ui.topic.value.trim(),
    human: $('#joinHuman').checked,
    participants: [...state.selected],
    duration: state.duration,
  };

  try {
    const response = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '회의 시작 실패');

    state.meetingId = data.id;
    enterMeeting(payload);
    connectEvents(data.id);
  } catch (error) {
    ui.formError.textContent = error.message;
    ui.startButton.textContent = '회의 시작';
    refreshStartState();
  }
}

function enterMeeting(payload) {
  resetMeetingState();
  ui.agendaTitle.textContent = payload.topic;
  state.topic = payload.topic;
  state.plannedMs = payload.duration * 60 * 1000;
  state.actualMeetingMs = null;
  state.human = Boolean(payload.human);
  $('#humanComposer').classList.toggle('hidden', !state.human);
  ui.meetingView.classList.toggle('with-human', state.human);
  buildSeats(state.human ? [...payload.participants, '나'] : payload.participants);
  renderMeetingRecord();
  ui.setupView.classList.add('hidden');
  ui.meetingView.classList.remove('hidden');
  ui.secretaryText.textContent = '참석자들이 안건 읽는 중...';
  startTimerLoop(payload.duration * 60 * 1000);
  setPlaybackClock(false);
  requestAnimationFrame(positionSeats);
}

function connectEvents(id) {
  state.eventSource?.close();
  state.eventSource = new EventSource(`/api/events?id=${encodeURIComponent(id)}`);

  state.eventSource.addEventListener('setup', () => {
    ui.secretaryText.textContent = '회의록 준비 완료. 손가락도 준비 완료.';
  });

  ['speech', 'secretary', 'reaction'].forEach(type => {
    state.eventSource.addEventListener(type, event => {
      const data = JSON.parse(event.data);
      if (type === 'speech' && data.speaker === '나' && !state.paused) {
        // The user interrupts the displayed speech; no unshown AI backlog survives.
        if (state.currentSpeechId) sendMeetingCommand('ack', {id: state.currentSpeechId}).catch(() => {});
        const waitingHumans = state.queue.filter(item => item.type === 'speech' && item.data.speaker === '나');
        clearPresentationQueue();
        state.queue = waitingHumans;
      }
      enqueuePresentation({ type, data });
    });
  });

  state.eventSource.addEventListener('ending', () => {
    $('#humanText').disabled = true;
    $('#humanSend').disabled = true;
    enqueuePresentation({ type: 'ending', data: {} });
  });

  state.eventSource.addEventListener('summary', event => {
    enqueuePresentation({ type: 'summary', data: JSON.parse(event.data) });
  });

  state.eventSource.addEventListener('error', event => {
    if (!event.data) return;
    try {
      const data = JSON.parse(event.data);
      addMinute('secretary', '서기', `오류: ${data.message}`);
      handleMeetingError(data.message);
    } catch (_) {
      // Native EventSource error events have no JSON payload.
    }
  });

  state.eventSource.addEventListener('done', () => {
    state.eventSource?.close();
    state.eventSource = null;
  });
}

function handleMeetingError(message) {
  state.timerRunning = false;
  state.ended = true;
  if (state.timerRaf) cancelAnimationFrame(state.timerRaf);
  state.timerRaf = null;

  clearPresentationQueue();
  closeActiveSpeech();
  ui.secretaryDesk.classList.add('stopped');
  ui.secretaryDesk.classList.remove('waiting');
  ui.meetingStatus.classList.remove('waiting');
  ui.meetingStatus.textContent = '회의 오류';
  ui.secretaryText.textContent = message || '회의를 계속할 수 없습니다.';
}

function cancelActiveMeeting() {
  if (!state.meetingId || state.ended) return;
  fetch(`/api/cancel?id=${encodeURIComponent(state.meetingId)}`, {
    method: 'POST',
    keepalive: true,
  }).catch(() => {});
}

function resetMeeting() {
  ui.newMeetingConfirm.classList.add('hidden');
  cancelActiveMeeting();
  state.eventSource?.close();
  state.eventSource = null;
  state.meetingId = null;
  closeMinutes();
  resetMeetingState();
  ui.meetingView.classList.add('hidden');
  ui.setupView.classList.remove('hidden');
  ui.startButton.textContent = '회의 시작';
  refreshStartState();
}

function requestNewMeeting() {
  const inProgress = !ui.meetingView.classList.contains('hidden') && !state.ended && Boolean(state.meetingId);
  if (!inProgress) {
    resetMeeting();
    return;
  }
  ui.newMeetingConfirm.classList.remove('hidden');
  $('#keepCurrentMeeting').focus();
}

function keepCurrentMeeting() {
  ui.newMeetingConfirm.classList.add('hidden');
}

/* ---------- Minutes panel ---------- */
function openMinutes() {
  renderMeetingRecord();
  ui.minutesPanel.classList.add('open');
  ui.minutesBackdrop.classList.remove('hidden');
  ui.minutesPanel.setAttribute('aria-hidden', 'false');
}

function closeMinutes() {
  ui.minutesPanel.classList.remove('open');
  ui.minutesBackdrop.classList.add('hidden');
  ui.minutesPanel.setAttribute('aria-hidden', 'true');
}

async function copyMinutes() {
  const topic = state.topic || ui.agendaTitle.textContent.trim() || '-';
  const participants = state.participants.length ? state.participants.join(', ') : '-';
  const planned = formatDurationLabel(state.plannedMs);
  const actual = formatDurationLabel(currentActualMeetingMs());
  const transcript = state.minutes.length
    ? state.minutes.map(item => `${item.speaker ? `${item.speaker}: ` : ''}${item.text}`).join('\n\n')
    : '아직 기록된 발언이 없습니다.';

  const text = [
    `회의 주제: ${topic}`,
    `참석자: ${participants}`,
    `회의 시간: ${planned}`,
    `실제 회의 시간: ${actual}`,
    `결론:\n${copyConclusionText()}`,
    `회의록:\n${transcript}`,
  ].join('\n\n');

  const button = $('#copyMinutes');

  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const helper = document.createElement('textarea');
    helper.value = text;
    helper.readOnly = true;
    helper.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
    document.body.appendChild(helper);
    helper.select();
    document.execCommand('copy');
    helper.remove();
  }

  button.textContent = '복사 완료';
  setTimeout(() => { button.textContent = '전체 복사'; }, 1000);
}

/* ---------- Events ---------- */
let resizeTimer = null;
addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(reflowMeetingLayout, 90);
});

if ('ResizeObserver' in window) {
  const layoutObserver = new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(reflowMeetingLayout, 50);
  });
  layoutObserver.observe(ui.roomStage);
  layoutObserver.observe(ui.activeSpeechBubble);
}

buildParticipantCards();
ui.topic.addEventListener('input', refreshStartState);

$$('.duration').forEach(button => {
  button.addEventListener('click', () => {
    $$('.duration').forEach(item => {
      const selected = item === button;
      item.classList.toggle('selected', selected);
      item.setAttribute('aria-pressed', String(selected));
    });

    state.duration = Number(button.dataset.duration);
    if (ui.meetingView.classList.contains('hidden')) {
      state.displayedMs = state.duration * 60 * 1000;
      renderTimer();
    }
  });
});

$('#pauseMeeting').addEventListener('click', togglePause);
$('#humanComposer').addEventListener('submit', submitHuman);
addEventListener('pagehide', cancelActiveMeeting);
ui.startButton.addEventListener('click', startMeeting);
ui.minutesButton.addEventListener('click', openMinutes);
$('#endMinutesButton').addEventListener('click', openMinutes);
$('#closeMinutes').addEventListener('click', closeMinutes);
ui.minutesBackdrop.addEventListener('click', closeMinutes);
$('#copyMinutes').addEventListener('click', copyMinutes);
$('#newMeetingButton').addEventListener('click', requestNewMeeting);
$('#endNewMeetingButton').addEventListener('click', resetMeeting);
$('#confirmNewMeeting').addEventListener('click', resetMeeting);
$('#keepCurrentMeeting').addEventListener('click', keepCurrentMeeting);

refreshStartState();

/* ---------- Development meeting preview ----------
   /preview-meeting is intentionally API-free so CSS can be edited and
   the browser can be refreshed without returning to the setup screen. */
function initPreviewMeeting() {
  if (window.location.pathname !== '/preview-meeting') return;

  const payload = {
    topic: '신제품 광고 콘셉트를 어떻게 잡을까?',
    participants: ROLES.map(([role]) => role),
    duration: 3,
  };

  enterMeeting(payload);

  // Keep the preview visually stable: no API connection and no countdown.
  setPlaybackClock(false);
  state.displayedMs = 138000;
  renderTimer();
  ui.meetingStatus.classList.remove('waiting');
  ui.secretaryDesk.classList.remove('waiting');
  ui.table.classList.remove('waiting');
  ui.meetingStatus.textContent = '회의 진행 중 · CSS 프리뷰';
  ui.turnLabel.textContent = '회의 중';
  ui.secretaryText.textContent = 'CSS 확인용 고정 프리뷰입니다.';

  setSpeaker(
    '마케팅팀장',
    '일단 눈에 띄어야 하니까 조금 과감하게 가는 게 좋을 것 같습니다.'
  );

  addMinute('speech', 'CEO', '좋아요. 오늘은 광고 콘셉트 방향부터 정하죠.');
  addMinute('speech', '마케팅팀장', '일단 눈에 띄어야 하니까 조금 과감하게 가는 게 좋을 것 같습니다.');
  addMinute('secretary', '서기', 'CSS 확인용 샘플 회의록입니다.');

  requestAnimationFrame(() => {
    reflowMeetingLayout();
    positionSpeechBubble('마케팅팀장');
  });
}

initPreviewMeeting();


if (document.fonts?.ready) {
  document.fonts.ready.then(reflowMeetingLayout);
}

