from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
ENGINE_PATH = Path(os.environ.get("AI_MEETING_ENGINE", BASE_DIR / "meeting.py"))
HOST = os.environ.get("AI_MEETING_HOST", os.environ.get("HOST", "0.0.0.0"))
PORT = int(os.environ.get("AI_MEETING_PORT", os.environ.get("PORT", "8000")))
SESSION_TTL_SECONDS = 60 * 60

ROLE_TO_NUMBER = {
    "CEO": "1",
    "마케팅팀장": "2",
    "디자이너": "3",
    "개발자": "4",
    "운영 담당자": "5",
    "소비자 대표": "6",
    "클라이언트": "7",
}


def sse(event: str, data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@dataclass
class MeetingSession:
    id: str
    topic: str
    participants: list[str]
    duration: int
    events: "queue.Queue[tuple[str, dict]]" = field(default_factory=queue.Queue)
    all_lines: list[str] = field(default_factory=list)
    done: bool = False
    process: subprocess.Popen | None = None
    created_at: float = field(default_factory=time.time)
    human: bool = False
    input_lock: threading.Lock = field(default_factory=threading.Lock)
    ready: bool = False

    def command(self, data: dict) -> bool:
        with self.input_lock:
            if not self.human or self.done or not self.ready or not self.process or not self.process.stdin:
                return False
            try:
                self.process.stdin.write(json.dumps(data, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
                return True
            except (OSError, ValueError):
                return False

    def emit(self, name: str, data: dict) -> None:
        self.events.put((name, data))


SESSIONS: dict[str, MeetingSession] = {}
SESSIONS_LOCK = threading.Lock()


def prune_sessions() -> None:
    cutoff = time.time() - SESSION_TTL_SECONDS
    with SESSIONS_LOCK:
        stale = [sid for sid, session in SESSIONS.items() if session.done and session.created_at < cutoff]
        for sid in stale:
            SESSIONS.pop(sid, None)


def cancel_session(meeting_id: str) -> bool:
    with SESSIONS_LOCK:
        session = SESSIONS.get(meeting_id)

    if not session:
        return False

    process = session.process
    if process and process.poll() is None:
        process.terminate()
    return True


class OutputParser:
    TIMER_RE = re.compile(r"⏱️\s*(\d{2}):(\d{2})\.(\d{3})\s*\|\s*발언\s*#(\d+)")
    SPEAKER_RE = re.compile(r"^💬\s*(.+?)\s*$")
    META_RE = re.compile(r"^\[([^/\]]+)\s*/\s*([^\]]+)\]\s*$")

    def __init__(self, session: MeetingSession):
        self.session = session
        self.pending_speaker: str | None = None
        self.last_speech_turn: int | None = None
        self.expression = "neutral"

    def feed(self, raw_line: str) -> None:
        line = raw_line.rstrip("\r\n")
        self.session.all_lines.append(line)
        if line.startswith("@expression "):
            self.expression = line.split(" ", 1)[1]
            return
        if line.startswith("@event ") and self.session.human:
            try:
                event = json.loads(line[7:])
                if event.get('type') == 'seal':
                    with self.session.input_lock:
                        self.session.ready = False
                        self.session.process.stdin.write('{"type":"sealed"}\n')
                        self.session.process.stdin.flush()
                    return
                if event.get('type') == 'ready':
                    with self.session.input_lock:
                        self.session.ready = True
                if event.get("type") in {"speech", "summary", "ending", "ready", "error"}:
                    self.session.emit(event["type"], event.get("data", {}))
            except (ValueError, TypeError):
                self.session.emit("error", {"message": "참여 회의 응답을 읽지 못했습니다."})
            return

        if match := self.TIMER_RE.search(line):
            minutes, seconds, millis, turn = map(int, match.groups())
            remaining_ms = ((minutes * 60) + seconds) * 1000 + millis
            self.last_speech_turn = turn
            self.session.emit("timer", {"remaining_ms": remaining_ms, "turn": turn})
            return

        if match := self.SPEAKER_RE.match(line):
            self.pending_speaker = match.group(1).strip()
            return

        if self.pending_speaker and line.strip() and not line.startswith(("[", "↳")):
            self.session.emit(
                "speech",
                {
                    "speaker": self.pending_speaker,
                    "speech": line.strip(),
                    "turn": self.last_speech_turn,
                    "expression": self.expression,
                },
            )
            self.pending_speaker = None
            return

        if match := self.META_RE.match(line.strip()):
            self.session.emit(
                "speech_meta",
                {
                    "move": match.group(1).strip(),
                    "emotion": match.group(2).strip(),
                    "turn": self.last_speech_turn,
                },
            )
            return

        if line.startswith("📝 서기:"):
            self.session.emit("secretary", {"text": line.split(":", 1)[1].strip()})
        elif line.startswith("🤐 "):
            speaker = line[2:].split(":", 1)[0].strip()
            self.session.emit("reaction", {"speaker": speaker, "reaction": "skip"})
        elif "회의가 종료되었습니다." in line:
            self.session.emit("ending", {})


def extract_list_section(lines: list[str], heading: str, stop_headings: set[str]) -> list[str]:
    items: list[str] = []
    active = False

    for line in lines:
        stripped = line.strip()
        if stripped == heading:
            active = True
            continue
        if active and stripped in stop_headings:
            break
        if active and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item and item != "없음":
                items.append(item)

    return items


def extract_final_summary(lines: list[str]) -> dict:
    try:
        start = max(i for i, line in enumerate(lines) if "회의가 종료되었습니다." in line)
        tail = lines[start:]
    except ValueError:
        tail = lines

    headings = {
        "📌 최종 결정",
        "💡 미확정 제안",
        "✅ 후속 작업",
        "❔ 현재 필요한 미확인 정보",
        "❓ 남은 핵심 쟁점",
        "🧠 DEV - 최종 argument registry",
        "🧪 DEV - 회의 후 입장",
    }

    summary = {
        "status": "unresolved",
        "mode": "none",
        "decisions": extract_list_section(tail, "📌 최종 결정", headings),
        "proposals": extract_list_section(tail, "💡 미확정 제안", headings),
        "actions": extract_list_section(tail, "✅ 후속 작업", headings),
        "unknowns": extract_list_section(tail, "❔ 현재 필요한 미확인 정보", headings),
        "issues": extract_list_section(tail, "❓ 남은 핵심 쟁점", headings),
        "counts": {},
        "end_reason": "",
    }

    count_re = re.compile(
        r"^(CEO|마케팅팀장|디자이너|개발자|운영 담당자|소비자 대표|클라이언트):\s*(\d+)회$"
    )

    for line in tail:
        stripped = line.strip()
        if stripped == "✅ 결정 완료":
            summary["status"] = "decided"
        elif stripped == "⏸️ 결정 보류":
            summary["status"] = "deferred"
        elif stripped == "💬 의견 정리":
            summary["status"] = "discussed"
        elif stripped == "⚠️ 미해결":
            summary["status"] = "unresolved"
        elif stripped.startswith("결정 방식:"):
            summary["mode"] = (
                "leader_decision" if "결정권자" in stripped
                else "consensus" if "합의" in stripped
                else "none"
            )
        elif stripped.startswith("종료 이유:"):
            summary["end_reason"] = stripped.split(":", 1)[1].strip().replace("\\_", "_")
        elif match := count_re.match(stripped):
            summary["counts"][match.group(1)] = int(match.group(2))

    return summary


def run_engine(session: MeetingSession) -> None:
    parser = OutputParser(session)
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", AI_MEETING_HUMAN="1" if session.human else "0")

    participant_numbers = ",".join(ROLE_TO_NUMBER[role] for role in session.participants)
    stdin_payload = f"{session.topic}\n{participant_numbers}\n{session.duration}\n"
    session.emit(
        "setup",
        {
            "topic": session.topic,
            "participants": session.participants,
            "duration": session.duration,
        },
    )

    try:
        process = subprocess.Popen(
            [sys.executable, "-u", str(ENGINE_PATH)],
            cwd=str(BASE_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        session.process = process

        assert process.stdin is not None
        process.stdin.write(stdin_payload)
        process.stdin.flush()
        if session.human:
            session.ready = True
        else:
            process.stdin.close()

        assert process.stdout is not None
        for line in process.stdout:
            parser.feed(line)

        return_code = process.wait()
        if return_code:
            session.emit("error", {"message": f"회의 엔진이 종료 코드 {return_code}로 끝났습니다."})
        elif not session.human:
            session.emit("summary", extract_final_summary(session.all_lines))
    except Exception as exc:
        session.emit("error", {"message": f"회의 엔진 실행 오류: {exc}"})
    finally:
        if session.process and session.process.stdin and not session.process.stdin.closed:
            try:
                session.process.stdin.close()
            except OSError:
                pass
        session.done = True
        session.emit("done", {})


class Handler(BaseHTTPRequestHandler):
    server_version = "AIMeetingUI/4.0"

    def log_message(self, fmt: str, *args) -> None:
        return

    def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(body, "application/json; charset=utf-8", status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/preview-meeting"):
            return self.send_bytes(
                (TEMPLATE_DIR / "index.html").read_bytes(),
                "text/html; charset=utf-8",
            )

        if path.startswith("/static/"):
            return self.serve_static(path)

        if path == "/api/events":
            return self.stream_events(parsed.query)

        if path == "/api/health":
            return self.send_json({"ok": True, "engine": str(ENGINE_PATH)})

        return self.send_error(HTTPStatus.NOT_FOUND)

    def serve_static(self, path: str) -> None:
        target = (STATIC_DIR / path.removeprefix("/static/")).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return self.send_error(HTTPStatus.FORBIDDEN)

        if not target.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)

        mime = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(target.suffix, "text/plain; charset=utf-8")

        self.send_bytes(target.read_bytes(), mime)

    def stream_events(self, query: str) -> None:
        meeting_id = (parse_qs(query).get("id") or [""])[0]
        with SESSIONS_LOCK:
            session = SESSIONS.get(meeting_id)

        if not session:
            return self.send_error(HTTPStatus.NOT_FOUND, "unknown meeting")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        try:
            while True:
                try:
                    name, data = session.events.get(timeout=10)
                    self.wfile.write(sse(name, data))
                    self.wfile.flush()
                    if name == "done":
                        break
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    if session.done and session.events.empty():
                        break
        except (BrokenPipeError, ConnectionResetError):
            if session.human:
                cancel_session(session.id)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/cancel":
            meeting_id = (parse_qs(parsed.query).get("id") or [""])[0]
            if not meeting_id or not cancel_session(meeting_id):
                return self.send_json({"ok": False}, 404)
            return self.send_json({"ok": True})

        if parsed.path == "/api/command":
            meeting_id = (parse_qs(parsed.query).get("id") or [""])[0]
            with SESSIONS_LOCK:
                session = SESSIONS.get(meeting_id)
            if not session or not session.human:
                return self.send_json({"error": "참여 중인 회의를 찾을 수 없습니다."}, 404)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 8192:
                    raise ValueError()
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or data.get("type") not in {"human", "ack"}:
                    raise ValueError()
                if not isinstance(data.get("id"), str) or not 1 <= len(data["id"]) <= 80:
                    raise ValueError()
                if data["type"] == "human":
                    if not isinstance(data.get("text"), str) or not 1 <= len(data["text"].strip()) <= 1000:
                        raise ValueError()
                    data["text"] = data["text"].strip()
            except (ValueError, TypeError):
                return self.send_json({"error": "발언은 1~1000자로 입력해 주세요."}, 400)
            if not session.command(data):
                return self.send_json({"error": "회의가 준비 중이거나 종료되었습니다."}, 409)
            return self.send_json({"ok": True}, 202)

        if parsed.path != "/api/start":
            return self.send_error(HTTPStatus.NOT_FOUND)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            topic = str(payload.get("topic", "")).strip()
            participants = payload.get("participants", [])
            duration = int(payload.get("duration", 3))
            human = payload.get("human", False)
            if not isinstance(human, bool):
                raise ValueError()
        except (TypeError, ValueError, json.JSONDecodeError):
            return self.send_json({"error": "invalid request"}, 400)

        if not topic:
            return self.send_json({"error": "회의 주제를 입력해 주세요."}, 400)
        if len(topic) > 500:
            return self.send_json({"error": "회의 주제는 500자 이하로 입력해 주세요."}, 400)
        if not isinstance(participants, list) or len(participants) < 2:
            return self.send_json({"error": "참석자는 최소 2명이어야 합니다."}, 400)
        if any(not isinstance(role, str) for role in participants):
            return self.send_json({"error": "참석자 정보가 올바르지 않습니다."}, 400)
        if len(set(participants)) != len(participants) or any(role not in ROLE_TO_NUMBER for role in participants):
            return self.send_json({"error": "참석자 정보가 올바르지 않습니다."}, 400)
        if duration not in (1, 3, 5):
            return self.send_json({"error": "회의 시간은 1/3/5분만 선택할 수 있습니다."}, 400)

        prune_sessions()
        meeting_id = uuid.uuid4().hex
        session = MeetingSession(meeting_id, topic, participants, duration, human=human)

        with SESSIONS_LOCK:
            SESSIONS[meeting_id] = session

        threading.Thread(target=run_engine, args=(session,), daemon=True).start()
        self.send_json({"id": meeting_id}, 201)


def main() -> None:
    if not ENGINE_PATH.exists():
        raise SystemExit(f"meeting.py를 찾을 수 없습니다: {ENGINE_PATH}")

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 62)
    print("AI MEETING WEB UI")
    print(f"브라우저 주소: http://127.0.0.1:{PORT}/")
    print("종료: Ctrl+C")
    print("=" * 62)

    # Hosting environments should never try to open a browser.
    if os.environ.get("AI_MEETING_OPEN_BROWSER") == "1":
        threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
