import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

meeting_text = (ROOT / "meeting.py").read_text(encoding="utf-8")
meeting_tree = ast.parse(meeting_text)
meeting_functions = [n.name for n in meeting_tree.body if isinstance(n, ast.FunctionDef)]
assert len(meeting_functions) == len(set(meeting_functions))
for name in ("interpret_context", "contextual_topic", "goal_completion_gate", "final_summary"):
    assert name in meeting_functions

engine_text = (ROOT / "character_meeting_v5.py").read_text(encoding="utf-8")
engine_tree = ast.parse(engine_text)
engine_functions = [n.name for n in engine_tree.body if isinstance(n, ast.FunctionDef)]
assert len(engine_functions) == len(set(engine_functions))
for name in ("create_initial_lenses", "controller", "select_speaker", "speak", "update_lens"):
    assert name in engine_functions

combined = meeting_text + engine_text
for legacy in (
    "is_point_repeated",
    "PROPOSAL_MOVES",
    "ACCEPTANCE_CLICHE_RE",
    "DELIVERY_SHAPES",
    "has_repeated_opening",
):
    assert legacy not in combined, legacy
assert "전원이 말할 필요" in combined
assert "합의/결론을 판정하지 않는다" in combined
assert len(meeting_text.splitlines()) < 500

app = (ROOT / "app.py").read_text(encoding="utf-8")
assert "duration not in (1, 3, 5)" in app
assert "def cancel_session" in app
js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
assert "finishByTimeLimit" in js
assert "state.timeExpired" in js
assert "cancelActiveMeeting();" in js
print("CODE QUALITY PASS")
