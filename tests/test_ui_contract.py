import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

for element_id in (
    "roomStage", "activeSpeechBubble", "reactionLayer", "secretaryDesk", "minutesButton",
    "endOverlay", "endMinutesButton", "endNewMeetingButton", "timer",
    "turnLabel", "minutesPanel", "finalSummary", "meetingStatus",
):
    assert f'id="{element_id}"' in HTML

assert 'class="end-status"' in HTML
assert 'class="wall-poster"' in HTML
assert 'class="table-status-line"' in HTML
assert 'id="newMeetingConfirm"' in HTML
assert 'id="confirmNewMeeting"' in HTML
assert "(active ? 14 : 10)" in JS
assert "const tabletDrop = tabletRow ? 10 : 0;" in JS
assert "state.minutes.some(item => item.type === 'speech')" in JS
assert "hasPresentedSpeech ? '생각 중...' : '회의 준비 중...'" in JS
assert "function requestNewMeeting()" in JS
assert "ui.newMeetingConfirm.classList.remove('hidden')" in JS
assert "Noto+Sans+KR" in HTML
assert '--font: "Noto Sans KR", sans-serif' in CSS
assert "Malgun Gothic" not in CSS
assert "Consolas" not in CSS
assert "ui-monospace" not in CSS

# No explicitly tiny type outside compact character name badges.
css_without_role_badges = re.sub(
    r"\.(?:floating-)?role-badge\s*\{[^}]*\}",
    "",
    CSS,
    flags=re.S,
)
small_sizes = [
    float(match.group(1))
    for match in re.finditer(r"font-size\s*:\s*([0-9.]+)px", css_without_role_badges)
    if float(match.group(1)) < 12
]
assert not small_sizes, small_sizes

# Role labels must show the complete role name.
role_block = re.search(r"(?m)^\.role-badge\s*\{([^}]*)\}", CSS, re.S).group(1)
assert "width: max-content" in role_block
assert "white-space: nowrap" in role_block
assert "text-overflow: ellipsis" not in role_block

# Bubble has no internal scroll, and placement protects the current speaker.
bubble_block = re.search(r"\.active-speech-bubble\s*\{([^}]*)\}", CSS, re.S).group(1)
assert "overflow: visible" in bubble_block
assert "dataset.direction = 'top'" in JS

# Minutes hierarchy and result alignment.
assert 'class="summary-section"' in JS
assert ".summary-section + .summary-section" in CSS
end_status = re.search(r"\.end-status\s*\{([^}]*)\}", CSS, re.S).group(1)
assert "align-items: center" in end_status

# Refactor checks: legacy component systems and appended-version overrides are gone.
for legacy in (".live-bubble", ".mobile-speech-dock", ".wall-frame", "v3.3", "v3.4", "v3.5"):
    assert legacy not in CSS, legacy

assert "timerTargetMs" not in JS
assert "presentationQueue" not in JS  # state.queue replaces old duplicate globals
assert "state.queue" in JS
assert "requestAnimationFrame(timerLoop)" in JS

print("UI CONTRACT PASS")

assert "function reflowMeetingLayout()" in JS
assert "function positionReactionMarker(role)" in JS
assert ".reaction-layer" in CSS
assert "ResizeObserver" in JS

