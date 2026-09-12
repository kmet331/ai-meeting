"""Offline interruption, presentation acknowledgement and finalization regressions."""
import importlib
import io
import json
from pathlib import Path
import queue
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault('dotenv', types.SimpleNamespace(load_dotenv=lambda: None))
sys.modules.setdefault('openai', types.SimpleNamespace(OpenAI=lambda **kw: None))
live = importlib.import_module('participant_session')
app = importlib.import_module('app')


class Participation(unittest.TestCase):
    def mailbox(self):
        box = live.Inbox.__new__(live.Inbox)
        box.commands = queue.Queue()
        box.history, box.seen = [], set()
        box.waiting = None
        box.closed = box.sealed = False
        return box

    def run_meeting(self, interrupt_at=None):
        box, events, summaries = self.mailbox(), [], []
        injected = False

        def interrupt(point):
            nonlocal injected
            if not injected and interrupt_at == point:
                injected = True
                box.commands.put({'type': 'human', 'id': 'human1', 'text': '예산은 500만원입니다.'})

        def emit(kind, data):
            events.append((kind, data))
            if kind == 'speech':
                box.commands.put({'type': 'ack', 'id': 'obsolete'})
                box.commands.put({'type': 'ack', 'id': data['id']})
            if kind == 'seal':
                interrupt('seal')
                box.commands.put({'type': 'sealed'})

        def speak(*args):
            interrupt('speak')
            return '예산에 맞춰야죠.' if any(x['speaker'] == '나' for x in box.history) else '비싼 안으로 갑시다.'

        def summarize(topic, history, reason, state):
            summaries.append(list(history))
            interrupt('summary')
            return {'outcome': state, 'decisions': [], 'proposals': [], 'issues': [], 'actions': []}

        with patch.object(live, 'emit', side_effect=emit), \
             patch.object(live.engine, 'controller', side_effect=lambda *args: {'continue': not box.history, 'reason': '끝'}), \
             patch.object(live.engine, 'select_speaker', return_value='CEO'), \
             patch.object(live.engine, 'speak', side_effect=speak), \
             patch.object(live.engine, 'update_lens', side_effect=lambda a,b,c,d: c):
            live.run_participating('예산 배분', '예산 배분', '1', {'CEO': {}},
                lambda *args: {'state': 'decided'}, summarize, box)
        return box, events, summaries

    def test_stale_generation_never_emitted(self):
        box, events, summaries = self.run_meeting('speak')
        speeches = [data for kind,data in events if kind == 'speech']
        self.assertEqual([x['speaker'] for x in speeches], ['나', 'CEO'])
        self.assertNotIn('비싼 안으로 갑시다.', [x['speech'] for x in speeches])
        self.assertEqual(summaries[-1][-2]['text'], '예산은 500만원입니다.')
        self.assertEqual(summaries[-1][-1]['text'], '예산에 맞춰야죠.')

    def test_input_during_summary_recalculates_summary(self):
        _, events, summaries = self.run_meeting('summary')
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[-1][-2]['speaker'], '나')
        self.assertEqual(summaries[-1][-1]['speaker'], 'CEO')
        self.assertEqual(sum(kind == 'summary' for kind,_ in events), 1)

    def test_accepted_input_before_seal_is_not_lost(self):
        _, events, summaries = self.run_meeting('seal')
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[-1][-2]['speaker'], '나')
        self.assertEqual(summaries[-1][-1]['speaker'], 'CEO')
        self.assertEqual(sum(kind == 'summary' for kind,_ in events), 1)

    def test_duplicate_human_and_stale_ack(self):
        box = self.mailbox()
        with patch.object(live, 'emit'):
            command = {'type': 'human', 'id': 'a', 'text': '전 B가 좋아요.'}
            box.apply(command)
            box.apply(command)
        box.apply({'type': 'ack', 'id': 'old'})
        self.assertEqual(box.waiting, 'a')
        self.assertEqual(len(box.history), 1)
        box.apply({'type': 'ack', 'id': 'a'})
        self.assertIsNone(box.waiting)

    def test_server_barrier_serializes_accepted_input(self):
        session = app.MeetingSession('a', 'topic', ['CEO','디자이너'], 1, human=True)
        session.process = types.SimpleNamespace(stdin=io.StringIO())
        session.ready = True
        self.assertTrue(session.command({'type': 'human', 'id': 'a', 'text': 'B'}))
        parser = app.OutputParser(session)
        parser.feed('@event {"type":"seal","data":{}}')
        self.assertFalse(session.command({'type': 'human', 'id': 'b', 'text': 'C'}))
        commands = [json.loads(line)['type'] for line in session.process.stdin.getvalue().splitlines()]
        self.assertEqual(commands, ['human', 'sealed'])
        parser.feed('@event {"type":"ready","data":{}}')
        self.assertTrue(session.command({'type': 'ack', 'id': 'a'}))

    def test_expression_fallback_keeps_text(self):
        for raw, expected in [('짧게 말합니다.', 'neutral'),
            ('{"text":"좋네요.","expression":"pleased"}', 'pleased'),
            ('{"text":"그건 어렵습니다.","expression":"invalid"}', 'neutral')]:
            with patch.object(live.engine, 'ask', return_value=raw):
                self.assertTrue(live.engine.speak('주제', '1', 'CEO', [], {'lens':'결정','impulse':'선택','interest':50,'strength':50}))
            self.assertEqual(live.engine.LAST_EXPRESSION['CEO'], expected)


if __name__ == '__main__':
    unittest.main()
