"""Optional live participation transport; the v4 selector and lenses stay intact."""
import json
import queue
import sys
import threading
import uuid

import character_meeting_v5 as engine


def emit(kind, data):
    print('@event ' + json.dumps({'type': kind, 'data': data}, ensure_ascii=False), flush=True)


class Inbox:
    def __init__(self, stream):
        self.commands = queue.Queue()
        self.history = []
        self.seen = set()
        self.waiting = None
        self.closed = False
        self.sealed = False
        threading.Thread(target=self.read, args=(stream,), daemon=True).start()

    def read(self, stream):
        for line in stream:
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    self.commands.put(data)
            except ValueError:
                continue
        self.commands.put({'type': 'eof'})

    def apply(self, data):
        kind = data.get('type')
        if kind == 'eof':
            self.closed = True
        elif kind == 'sealed':
            self.sealed = True
        elif kind == 'ack' and data.get('id') == self.waiting:
            self.waiting = None
        elif kind == 'human' and data.get('id') not in self.seen:
            identity, text = data.get('id'), data.get('text', '').strip()
            if not identity or not text:
                return
            self.seen.add(identity)
            self.history.append({'turn': len(self.history) + 1, 'speaker': '나', 'text': text})
            self.waiting = identity
            emit('speech', {'speaker': '나', 'speech': text, 'id': identity, 'expression': 'neutral'})

    def checkpoint(self):
        """Drain inputs and wait for the last visible speech to be read."""
        before = len(self.history)
        while True:
            try:
                self.apply(self.commands.get_nowait())
            except queue.Empty:
                if self.closed or not self.waiting:
                    return len(self.history) != before
                self.apply(self.commands.get())

    def finish_barrier(self):
        # The server serializes this marker after all accepted HTTP commands.
        # No accepted user utterance can disappear behind the final summary.
        before = len(self.history)
        self.sealed = False
        emit('seal', {})
        while not self.sealed and not self.closed:
            self.apply(self.commands.get())
        if len(self.history) != before:
            emit('ready', {})
            self.checkpoint()
            return False
        return not self.closed


def run_participating(topic, meeting_topic, mode_key, lenses, completion, summarize, inbox=None):
    inbox = inbox or Inbox(sys.stdin)
    history = inbox.history
    turns = 0
    emit('ready', {})
    while not inbox.closed:
        inbox.checkpoint()
        if inbox.closed:
            return
        # Every model result is checked against newly arrived human input before
        # it can become a visible speech, completion verdict or final summary.
        needs_human_response = bool(history and history[-1]['speaker'] == '나')
        if needs_human_response:
            verdict = {
                'continue': True,
                'reason': '아직 실제 참석자의 최신 발언에 대한 반응이 없음',
                'unexpressed': [],
            }
        else:
            verdict = engine.controller(meeting_topic, mode_key, history, lenses)
        if inbox.checkpoint():
            continue
        gate = {'state': 'incomplete'}
        end = turns >= engine.MODES[mode_key]['max_turns'] and not needs_human_response
        reason = '안전 최대 턴 도달' if end else verdict.get('reason', '')
        if history and (end or not verdict['continue']):
            gate = completion(topic, history)
            if inbox.checkpoint():
                continue
            end = True
            reason = reason or gate.get('reason') or '더 이어질 살아 있는 대화가 없음'
        if end:
            summary = summarize(topic, history, reason, gate['state'])
            if inbox.checkpoint():
                continue
            if not inbox.finish_barrier():
                continue
            summary.update(status=summary['outcome'], end_reason=reason, unknowns=[], counts={}, mode='none')
            emit('ending', {})
            emit('summary', summary)
            return
        turn_topic = meeting_topic
        if history and history[-1]['speaker'] == '나':
            turn_topic += '\n[방금 실제 참석자 나의 발언에 자연스럽게 반응할 사람이 이어간다. 무조건 동의하지 않는다.]'
        speaker = engine.select_speaker(turn_topic, mode_key, history, lenses,
                                        preferred=verdict.get('unexpressed', []))
        if inbox.checkpoint():
            continue
        text = engine.speak(turn_topic, mode_key, speaker, history, lenses[speaker]).replace('\n', ' ').strip()
        if not text:
            lenses[speaker] = engine.spend_silent_impulse(lenses[speaker])
            continue
        if inbox.checkpoint():
            continue
        if inbox.closed:
            return
        turns += 1
        history.append({'turn': len(history) + 1, 'speaker': speaker, 'text': text})
        lenses[speaker]['expressed'] = True
        identity = uuid.uuid4().hex
        inbox.waiting = identity
        emit('speech', {'speaker': speaker, 'speech': text, 'id': identity,
                        'expression': engine.LAST_EXPRESSION.get(speaker, 'neutral')})
        inbox.checkpoint()
        if inbox.closed:
            return
        lenses[speaker] = engine.update_lens(meeting_topic, speaker, lenses[speaker], history)


