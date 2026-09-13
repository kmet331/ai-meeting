import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=lambda **kwargs: None))
engine = importlib.import_module("character_meeting_v5")
meeting = importlib.import_module("meeting")


class CompletionScenarios(unittest.TestCase):
    def gate(self, topic, transcript, state):
        answer = json.dumps({"state": state, "reason": "fixture", "remaining_question": ""})
        with patch.object(engine, "ask", return_value=answer) as ask:
            result = meeting.goal_completion_gate(topic, transcript)
        return result, ask.call_args.args[0]

    def test_actual_menu_choice_can_be_decided(self):
        topic = "점심 메뉴를 김치찌개와 돈까스 중 하나로 정하자."
        turns = [{"speaker": "CEO", "text": "오늘은 돈까스로 갑시다."}]
        result, prompt = self.gate(topic, turns, "decided")
        self.assertEqual(result["state"], "decided")
        self.assertIn("실제 메뉴 하나를 골랐는지", prompt)

    def test_comparison_without_concept_choice_stays_incomplete(self):
        topic = "신제품 광고 콘셉트를 귀여운 방향과 강렬한 방향 중 어디로 잡을까?"
        turns = [{"speaker": "디자이너", "text": "귀여움은 친근하고 강렬함은 첫인상이 셉니다."}]
        result, prompt = self.gate(topic, turns, "incomplete")
        self.assertEqual(result["state"], "incomplete")
        self.assertIn("콘셉트 선택 질문", prompt)

    def test_kpi_is_not_budget_allocation(self):
        topic = "광고비와 프로모션 비용을 어떻게 배분할까?"
        turns = [{"speaker": "마케팅팀장", "text": "전환율을 보고 다음 달에 조정하죠."}]
        result, prompt = self.gate(topic, turns, "incomplete")
        self.assertEqual(result["state"], "incomplete")
        self.assertIn("KPI나 테스트·집행 방법만", prompt)

    def test_relative_allocation_can_be_decided(self):
        topic = "광고비와 프로모션 비용을 어떻게 배분할까?"
        turns = [{"speaker": "CEO", "text": "광고는 최소만 남기고 나머지는 프로모션에 씁시다."}]
        result, prompt = self.gate(topic, turns, "decided")
        self.assertEqual(result["state"], "decided")
        self.assertIn("상대적 배분", prompt)

    def test_request_frame_drives_unseen_verbal_task_without_a_special_mode(self):
        answer = json.dumps({
            "relations": {},
            "reading": "각 참석자가 제품을 날씨에 비유한 실제 표현을 듣고 싶다",
            "requested_response": "각자 떠올린 날씨 비유와 짧은 이유",
            "shared_result": "",
            "participation_scope": "각 참석자",
            "nearby_mistake": "비유를 만드는 방법이나 발표 순서를 정하는 것",
            "uncertainty": "없음",
            "completion": "실제 날씨 비유들이 제시됨",
        }, ensure_ascii=False)
        topic = "우리 제품을 날씨에 비유해서 한마디씩 해봐"
        with patch.object(engine, "ask", return_value=answer) as ask:
            context = meeting.interpret_context(topic, ["CEO", "디자이너"])
        prompt = ask.call_args.args[0]
        self.assertEqual(context["requested_response"], "각자 떠올린 날씨 비유와 짧은 이유")
        self.assertEqual(context["shared_result"], "")
        self.assertNotIn("자기소개", prompt)
        engine_source = (ROOT / "character_meeting_v5.py").read_text(encoding="utf-8")
        self.assertNotIn("자기소개 하기", engine_source)
        self.assertGreaterEqual(engine_source.count("사용자가 실제로 받고 싶은 반응"), 3)
        self.assertIn("의견을 나열한 뒤 곧바로 끝내지 않는다", engine_source)
        contextual = meeting.contextual_topic(topic, context)
        self.assertIn("사용자가 실제로 받고 싶은 반응", contextual)
        self.assertIn("비유를 만드는 방법이나 발표 순서를 정하는 것", contextual)

    def test_explicit_each_request_keeps_only_requested_responses_alive(self):
        topic = """제품을 날씨에 비유해 봐
명시적으로 실제 응답이 필요한 참석자: CEO, 디자이너"""
        lenses = {
            "CEO": {"mood": "", "lens": "", "want": "", "friction": "", "personal_detail": "", "private_texture": "", "private_spark": "", "quirk": "", "impulse": "", "interest": 0, "strength": 0, "expressed": True},
            "디자이너": {"mood": "", "lens": "", "want": "", "friction": "", "personal_detail": "", "private_texture": "", "private_spark": "", "quirk": "", "impulse": "", "interest": 0, "strength": 0, "expressed": False},
        }
        history = [{"speaker": "CEO", "text": "우리 제품은 맑고 바람 센 날 같아요."}]
        verdict = engine.controller(topic, "3", history, lenses)
        self.assertTrue(verdict["continue"])
        self.assertEqual(verdict["unexpressed"], ["디자이너"])

    def test_character_prompt_keeps_optional_human_oddness(self):
        lens = {"CEO": engine.CHARACTERS["CEO"]}
        generated = json.dumps({
            "mood": "가벼움", "lens": "오늘 입맛", "want": "돈까스",
            "fr":"없음", "personal_detail":"소스는 반만", "quirk":"양배추부터 먹으면 진 기분",
            "imp":"돈까스", "interest":70, "strength":60,
        }, ensure_ascii=False)
        with patch.object(engine, "CHARACTERS", lens), patch.object(engine, "ask", return_value=generated) as ask:
            state = engine.create_initial_lenses("점심 뭐 먹을까?")["CEO"]
        self.assertEqual(state["quirk"], "양배추부터 먹으면 진 기분")
        self.assertIn("조금 이상한 진심", ask.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
