"""Offline prompt contracts, not measurements of model judgement accuracy."""
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault('dotenv', types.SimpleNamespace(load_dotenv=lambda: None))
sys.modules.setdefault('openai', types.SimpleNamespace(OpenAI=lambda **kwargs: None))
engine = importlib.import_module('character_meeting_v5')
meeting = importlib.import_module('meeting')

TOPIC = '내일 점심 피자 먹을까요?'
HISTORY = [
    {'speaker': '개발자', 'text': '몇 명인지랑 배달 되는지 먼저 확인하죠.'},
    {'speaker': '나', 'text': '짬뽕!!! 짬뽕!!!!!!!'},
    {'speaker': '운영 담당자', 'text': '몇 명인지 알려주시면 주문하겠습니다.'},
]


class DecisionScope(unittest.TestCase):
    def test_logistics_request_is_not_deferral_agreement(self):
        with patch.object(engine, 'ask', return_value=json.dumps({'state':'incomplete', 'remaining_question':'피자와 짬뽕 중 무엇을 고를까?'})) as ask:
            result = meeting.goal_completion_gate(TOPIC, HISTORY)
            self.assertEqual(result['state'], 'incomplete')
            prompt, transcript = ask.call_args.args
            self.assertIn('선택 후 실행할 세부사항', prompt)
            self.assertIn('결정 보류에 합의했다고 보지 않는다', prompt)
            self.assertIn(HISTORY[1]['text'], transcript)
        with patch.object(engine, 'ask', return_value='{"outcome":"deferred","decisions":[],"proposals":[],"issues":[],"actions":[]}') as ask:
            self.assertEqual(meeting.final_summary(TOPIC,HISTORY,'종료',result['state'])['outcome'],'unresolved')
            self.assertIn("보류 상태와 '보류하기로 합의함'은 다르다", ask.call_args.args[0])

    def test_adopted_menu_and_real_blocker_fixtures(self):
        cases = [('짬뽕으로 정하죠. 인원은 주문할 때 세면 됩니다.', 'decided'),
                 ('심한 알레르기가 있어 성분을 확인하기 전에는 이 메뉴를 고를 수 없어요.', 'deferred')]
        for text, state in cases:
            with patch.object(engine,'ask',return_value=json.dumps({'state':state})) as ask:
                self.assertEqual(meeting.goal_completion_gate(TOPIC,HISTORY+[{'speaker':'CEO','text':text}])['state'],state)
                self.assertIn('선택 자체의 blocker',ask.call_args.args[0])

    def test_repetition_guidance_reaches_every_character(self):
        lens = {'lens':'인원 확인','impulse':'몇 명일까','interest':50,'strength':50,'expressed':True}
        for role in engine.CHARACTERS:
            with patch.object(engine,'ask',return_value='짧은 반응') as ask:
                engine.speak(TOPIC,'3',role,HISTORY,lens)
                self.assertIn('이미 충분히 말한 생각은 다시 설명하지 말고',ask.call_args.args[0])
                self.assertIn('회의 진행자나 요약자가 아니라',ask.call_args.args[0])
                self.assertIn(HISTORY[1]['text'],ask.call_args.args[1])

    def test_selector_and_evolution_receive_new_preference(self):
        lenses={role:{'lens':'인원','impulse':'인원 확인','interest':50,'strength':50,'expressed':True} for role in engine.CHARACTERS}
        with patch.object(engine,'ask',return_value='CEO') as ask:
            self.assertEqual(engine.select_speaker(TOPIC,'3',HISTORY,lenses),'CEO')
            self.assertIn('감정이나 생각이 움직인 사람',ask.call_args.args[0])
        with patch.object(engine,'ask',return_value='{"lens":"짬뽕 취향","impulse":"나도 먹고 싶다","interest":30,"strength":30}') as ask:
            updated = engine.update_lens(TOPIC,'CEO',lenses['CEO'],HISTORY)
            self.assertIn('말하고 싶은 압력은 여기서 소진된다',ask.call_args.args[0])
            self.assertIn(HISTORY[1]['text'],ask.call_args.args[1])
            self.assertEqual(updated['impulse'], '없음')
            self.assertEqual(updated['strength'], 0)

    def test_direct_question_and_fact_owner_reach_selected_speaker(self):
        history = [
            {'speaker':'소비자 대표','text':'주말엔 하나만 하고 쉬고 싶어요.'},
            {'speaker':'나','text':'오, 뭐 할 건데요?'},
        ]
        lenses = {
            role: {'lens':'','want':'','friction':'','impulse':'','interest':20,'strength':0,'expressed':True}
            for role in engine.CHARACTERS
        }
        selection = json.dumps({
            'speaker':'소비자 대표',
            'target':'나의 바로 이어진 질문',
            'impulse':'내 실제 주말 계획을 답한다',
            'question':'오, 뭐 할 건데요?',
            'facts':'나가 서점과 결혼식 계획을 말했다',
        }, ensure_ascii=False)
        with patch.object(engine, 'ask', return_value=selection) as ask:
            self.assertEqual(engine.select_speaker('주말 뭐 할 거야?', '3', history, lenses), '소비자 대표')
            selector_prompt = ask.call_args.args[0]
        self.assertIn('바로 앞 화자에게 이어 묻는 질문', selector_prompt)
        self.assertIn('모두가 답할 의무가 없다', selector_prompt)

        with patch.object(engine, 'ask', return_value='{"text":"저는 영화 볼 거예요.","expression":"talking"}') as ask:
            engine.speak('주말 뭐 할 거야?', '3', '소비자 대표', history, lenses['소비자 대표'])
            speech_prompt = ask.call_args_list[0].args[0]
        self.assertIn('오, 뭐 할 건데요?', speech_prompt)
        self.assertIn('나가 서점과 결혼식 계획을 말했다', speech_prompt)
        self.assertIn('발화 첫 문장 안에서 실제 답부터 말한다', speech_prompt)
        self.assertIn('다른 사람이 말한 일정', speech_prompt)

    def test_first_speaker_cannot_react_to_unseen_private_lens(self):
        lenses = {
            role: {'lens':'비공개 생각','want':'','friction':'','personal_detail':'',
                   'private_texture':'','impulse':'한마디','interest':40,'strength':40,'expressed':False}
            for role in engine.CHARACTERS
        }
        selection = json.dumps({
            'speaker':'마케팅팀장', 'target':'클라이언트의 비공개 생각',
            'impulse':'내 답을 말한다', 'question':'', 'facts':'', 'new_part':'내 답'
        }, ensure_ascii=False)
        with patch.object(engine, 'ask', return_value=selection):
            engine.select_speaker('퇴근하고 뭐 하면서 쉬어?', '1', [], lenses)
        self.assertEqual(engine.LAST_SELECTION_TARGET['마케팅팀장'], '퇴근하고 뭐 하면서 쉬어?')
        self.assertEqual(engine.LAST_SELECTION_QUESTION['마케팅팀장'], '')

    def test_latest_human_fact_is_repaired_without_polishing_every_turn(self):
        human_history = [{'speaker':'나','text':'이번 주말 결혼식에 가요.'}]
        lens = {'lens':'휴식','want':'쉬기','friction':'없음','personal_detail':'게임하기',
                'private_texture':'혼자 쉬기','impulse':'반응','interest':30,'strength':20}
        draft = '{"text":"저도 결혼식부터 가고 쉴게요.","expression":"thinking"}'
        fixed = '{"text":"결혼식까지 가면 바쁘겠네요. 저는 게임이나 할게요."}'
        with patch.object(engine, 'ask', side_effect=[draft, fixed]) as ask:
            result = engine.speak('주말 뭐 할 거야?', '3', '개발자', human_history, lens)
        self.assertEqual(result, '결혼식까지 가면 바쁘겠네요. 저는 게임이나 할게요.')
        self.assertEqual(ask.call_count, 2)
        self.assertIn('자신의 경험처럼', ask.call_args_list[1].args[0])

    def test_open_question_needs_one_real_answer_not_a_roll_call(self):
        history = [{'speaker':'나','text':'다들 MBTI E예요, I예요?'}]
        lenses = {
            role: {'lens':'','want':'','friction':'','personal_detail':'I에 가깝고 혼자 쉬며 충전함',
                   'impulse':'','interest':20,'strength':0,'expressed':True}
            for role in engine.CHARACTERS
        }
        selection = json.dumps({
            'speaker':'개발자', 'target':'나의 열린 질문', 'impulse':'내 성향을 답한다',
            'question':'다들 MBTI E예요, I예요?', 'facts':'', 'new_part':'나는 I에 가깝다',
        }, ensure_ascii=False)
        with patch.object(engine, 'ask', return_value=selection) as ask:
            engine.select_speaker('주말 뭐 할 거야?', '3', history, lenses)
            selector_prompt = ask.call_args.args[0]
        self.assertIn('모두가 답할 의무가 없다', selector_prompt)
        self.assertIn('자기 답을 꺼낸다', selector_prompt)

        with patch.object(engine, 'ask', return_value='{"text":"저는 I에 가까워요.","expression":"neutral"}') as ask:
            engine.speak('주말 뭐 할 거야?', '3', '개발자', history, lenses['개발자'])
            prompt = ask.call_args_list[0].args[0]
        self.assertIn('다들 MBTI E예요, I예요?', prompt)
        self.assertIn('특정 지목인지 열린 질문인지와 관계없이', prompt)
        self.assertIn('나는 I에 가깝다', prompt)

    def test_initial_private_state_can_hold_a_concrete_personal_answer(self):
        one = {'개발자': engine.CHARACTERS['개발자']}
        raw = json.dumps({
            'mood':'느긋함', 'lens':'혼자 몰입할 시간', 'want':'밀린 게임 끝내기',
            'friction':'없음', 'personal_detail':'토요일 밤에 밀린 게임 엔딩 보기',
            'impulse':'이번엔 게임이나 끝내야지', 'interest':55, 'strength':45,
        }, ensure_ascii=False)
        with patch.object(engine, 'CHARACTERS', one), patch.object(engine, 'ask', return_value=raw) as ask:
            lenses = engine.create_initial_lenses('주말에 뭐 할 거야?')
        self.assertEqual(lenses['개발자']['personal_detail'], '토요일 밤에 밀린 게임 엔딩 보기')
        self.assertIn('안전한 평균 답으로', ask.call_args.args[0])
        self.assertIn('허구 인물의 가벼운 취향', ask.call_args.args[0])
        self.assertIn('private_texture', lenses['개발자'])

    def test_discussed_summary_does_not_invent_agenda_or_completed_action(self):
        with patch.object(engine, 'ask', return_value='{"outcome":"discussed","decisions":[],"proposals":[],"issues":[],"actions":[]}') as ask:
            result = meeting.final_summary('주말에 뭐 할 거야?', HISTORY, '대화가 자연해짐', 'not_goal')
        self.assertEqual(result['outcome'], 'discussed')
        prompt = ask.call_args.args[0]
        self.assertIn('이미 대화에서 각자 의견을 말한 일', prompt)
        self.assertIn('서로 다른 취향이나 관점', prompt)
        self.assertIn('사람 수만큼 늘어놓지 않는다', prompt)

    def test_completion_labels_result_but_does_not_drive_conversation(self):
        lenses = {
            role: {'lens':'','impulse':'','interest':0,'strength':0,'expressed':True}
            for role in engine.CHARACTERS
        }
        with patch.object(engine, 'ask', return_value='not json'):
            verdict = engine.controller(TOPIC, '3', HISTORY, lenses)
        self.assertFalse(verdict['continue'])

        with patch.object(engine, 'ask', return_value='{"outcome":"unresolved","decisions":[],"proposals":[],"issues":[],"actions":[]}'):
            result = meeting.final_summary('드디어 주말. 뭐할 거야?', HISTORY, '대화가 자연해짐', 'not_goal')
        self.assertEqual(result['outcome'], 'discussed')

    def test_process_plan_is_not_the_conflict_resolution(self):
        topic = '클라이언트는 많이 넣고 싶고 디자인팀은 덜어내고 싶다'
        history = [
            {'speaker':'클라이언트','text':'어디까지 넣을지 같이 보고 싶어요.'},
            {'speaker':'CEO','text':'핵심부터 좁혀서 정리하죠.'},
        ]
        with patch.object(engine, 'ask', return_value='{"state":"incomplete","reason":"포함 범위가 정해지지 않음"}') as ask:
            result = meeting.goal_completion_gate(topic, history)
        self.assertEqual(result['state'], 'incomplete')
        self.assertIn('다음에 문제를 푸는 절차만 정한 것은', ask.call_args.args[0])
        self.assertIn('실제 항목을 가르지 못하는 말', ask.call_args.args[0])

    def test_selector_sees_current_pressure_and_last_speech(self):
        lenses = {
            role: {'lens':'휴식','want':'쉬기','friction':'','impulse':'쉬고 싶다',
                   'interest':30,'strength':20,'expressed':True}
            for role in engine.CHARACTERS
        }
        with patch.object(engine, 'ask', return_value='CEO') as ask:
            engine.select_speaker('주말 뭐 할 거야?', '3', HISTORY, lenses)
        prompt = ask.call_args.args[1]
        self.assertIn('strength=20', prompt)
        self.assertIn('최근 자기 발언=', prompt)

    def test_topic_interpretation_is_freeform_and_revisable(self):
        raw = json.dumps({
            'relations': {},
            'reading': '각 참석자의 개인적인 주말 계획을 듣고 싶어 한다.',
            'uncertainty': '함께 할 계획인지 여부는 명시되지 않았다.',
            'completion': '각자 자기 계획을 말하면 질문에 답한 것이다.',
        }, ensure_ascii=False)
        with patch.object(engine, 'ask', return_value=raw) as ask:
            request = meeting.interpret_context('드디어 주말. 뭐 할 거야?', list(engine.CHARACTERS))
        self.assertNotIn('meeting_type', request)
        self.assertIn('각 참석자의 개인적인', request['reading'])
        self.assertIn('고정 유형을 붙이거나', ask.call_args.args[0])

        context = meeting.contextual_topic('드디어 주말. 뭐 할 거야?', request)
        self.assertIn(request['reading'], context)
        self.assertIn('가장 최근 설명이 즉시 우선한다', context)

    def test_one_sided_condition_is_not_a_complete_conditional_decision(self):
        topic = '우리 회사에 주 4일제를 도입하는 게 좋을까?'
        history = [{'speaker':'CEO','text':'금요일 업무 공백을 해결하지 못하면 도입하지 맙시다.'}]
        with patch.object(engine, 'ask', return_value='{"state":"incomplete"}') as ask:
            result = meeting.goal_completion_gate(topic, history)
        self.assertEqual(result['state'], 'incomplete')
        self.assertIn('한쪽 조건만 말한 것은', ask.call_args.args[0])
        self.assertIn('조건을 충족하면 도입하고', ask.call_args.args[0])

    def test_completion_reconsiders_latest_user_clarification(self):
        request = {
            'reading': '함께 할 일을 고르는 질문일 수 있다.',
            'uncertainty': '각자 계획인지 모호하다.',
            'completion': '질문의 뜻에 맞게 답한다.',
        }
        history = [{'speaker':'나', 'text':'각자 쉬는 날 뭐 할 거냐는 질문이야.'}]
        with patch.object(engine, 'ask', return_value='{"state":"not_goal"}') as ask:
            result = meeting.goal_completion_gate('드디어 주말. 뭐 할 거야?', history, request)
        self.assertEqual(result['state'], 'not_goal')
        self.assertIn(request['reading'], ask.call_args.args[1])
        self.assertIn(history[0]['text'], ask.call_args.args[1])
        self.assertIn('최근 사용자 발언으로 해석을 갱신', ask.call_args.args[0])

    def test_private_mood_cannot_invent_external_circumstances(self):
        one = {'CEO': engine.CHARACTERS['CEO']}
        with patch.object(engine, 'CHARACTERS', one), \
             patch.object(engine, 'ask', return_value='{"mood":"느긋함","lens":"휴식","want":"쉬기","friction":"없음","impulse":"쉬고 싶다","interest":30,"strength":30}') as ask:
            engine.create_initial_lenses('주말 뭐 할 거야?')
        self.assertIn('질병·알레르기·약속·마감·예산', ask.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
