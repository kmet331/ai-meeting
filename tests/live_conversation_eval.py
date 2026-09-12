"""Manual, paid-API conversation evaluation for the development copy.

This is intentionally separate from the normal test suite. It runs only when
invoked with a named case and writes the full transcript for qualitative review.
"""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import character_meeting_v5 as engine
import meeting


CASES = {
    "short_meeting": {
        "topic": "회의는 짧은 게 좋은가?",
        "mode": "3",
        "participants": list(meeting.ROLE_ORDER),
        "human": [],
    },
    "quick_choice": {
        "topic": "오늘 점심은 짬뽕과 짜장 중 뭘 먹을까?",
        "mode": "1",
        "participants": ["CEO", "소비자 대표", "개발자", "마케팅팀장"],
        "human": [],
    },
    "after_work_chat": {
        "topic": "요즘 퇴근하고 뭐 하면서 쉬어?",
        "mode": "1",
        "participants": ["마케팅팀장", "디자이너", "개발자", "클라이언트"],
        "human": [],
    },
    "weekend_with_human": {
        "topic": "드디어 주말. 뭐 할 거야?",
        "mode": "3",
        "participants": list(meeting.ROLE_ORDER),
        "human": [
            (3, "저는 이번 주말 결혼식도 가고 개인 프로젝트도 하려고요."),
            (7, "다들 MBTI는 E예요, I예요?"),
        ],
    },
    "design_conflict": {
        "topic": "클라이언트는 장점을 최대한 많이 넣고 싶고 디자인팀은 덜어내고 싶다. 어디까지 넣을지 협의하자.",
        "mode": "3",
        "participants": ["CEO", "마케팅팀장", "디자이너", "개발자", "소비자 대표", "클라이언트"],
        "human": [(5, "메인 화면 말고 회사소개 페이지로 나누는 건 어때요?")],
    },
    "launch_budget": {
        "topic": "신제품 출시 첫 달 예산이 부족하다. 광고비와 프로모션 비용을 어떻게 배분할까?",
        "mode": "5",
        "participants": list(meeting.ROLE_ORDER),
        "human": [(6, "저는 초반 광고보다 실제 구매 프로모션에 더 쓰고 싶어요.")],
    },
    "four_day_week": {
        "topic": "우리 회사에 주 4일제를 도입하는 게 좋을까?",
        "mode": "5",
        "participants": list(meeting.ROLE_ORDER),
        "human": [(6, "급여가 줄어드는 방식이라면 저는 반대예요.")],
    },
}


def run_case(name: str) -> dict:
    case = CASES[name]
    engine.CHARACTERS = {
        role: engine.CHARACTERS[role]
        for role in meeting.ROLE_ORDER
        if role in case["participants"]
    }
    engine.MODEL = os.getenv("AI_MEETING_MODEL", engine.MODEL)
    request_context = meeting.interpret_context(case["topic"], case["participants"])
    meeting_topic = meeting.contextual_topic(case["topic"], request_context)
    lenses = engine.create_initial_lenses(meeting_topic)
    initial_lenses = json.loads(json.dumps(lenses, ensure_ascii=False))
    history = []
    human_lines = dict(case["human"])
    end_reason = "안전 최대 턴 도달"
    mode = engine.MODES[case["mode"]]

    for turn in range(1, mode["max_turns"] + 1):
        if turn in human_lines:
            history.append({"turn": len(history) + 1, "speaker": "나", "text": human_lines[turn]})

        verdict = engine.controller(meeting_topic, case["mode"], history, lenses)
        if history and history[-1]["speaker"] != "나" and not verdict["continue"]:
            end_reason = verdict.get("reason") or "더 이어질 살아 있는 대화가 없음"
            break

        speaker = engine.select_speaker(meeting_topic, case["mode"], history, lenses)
        speech = engine.speak(meeting_topic, case["mode"], speaker, history, lenses[speaker]).replace("\n", " ").strip()
        if not speech:
            lenses[speaker] = engine.spend_silent_impulse(lenses[speaker])
            continue
        history.append({"turn": len(history) + 1, "speaker": speaker, "text": speech})
        lenses[speaker]["expressed"] = True
        lenses[speaker] = engine.update_lens(meeting_topic, speaker, lenses[speaker], history)

    gate = meeting.goal_completion_gate(case["topic"], history, request_context)
    summary = meeting.final_summary(case["topic"], history, end_reason, gate["state"], request_context)
    return {
        "case": name,
        "topic": case["topic"],
        "mode": case["mode"],
        "participants": case["participants"] + (["나"] if case["human"] else []),
        "request_context": request_context,
        "initial_lenses": initial_lenses,
        "turns": history,
        "end_reason": end_reason,
        "gate": gate,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_case(args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{args.case}: {len(result['turns'])} turns, {result['gate']['state']}")


if __name__ == "__main__":
    main()


