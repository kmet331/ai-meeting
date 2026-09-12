# AI 회의실

사용자가 주제를 던지거나 회의 중 직접 끼어들면, 서로 다른 관점과 성격을 가진 AI 캐릭터들이 대화하는 웹 애플리케이션입니다. 정답을 빨리 합의하는 것보다 실제 사람들과 이야기하는 듯한 반응, 이견, 질문과 새로운 관점을 만드는 데 초점을 둡니다.

## 주요 기능

- CEO, 마케팅팀장, 디자이너, 개발자, 운영 담당자, 소비자 대표, 클라이언트의 서로 다른 관점
- 참석자마다 공유 대화 이전에 만드는 독립적인 초기 시각
- 대화 흐름에 따른 자연스러운 다음 발화자 선택
- 1분, 3분, 5분의 탐색 깊이
- 회의 도중 사용자가 `나`라는 참석자로 자유롭게 끼어드는 기능
- 발언 일시정지와 이어보기
- 캐릭터별 기본·발화·생각·만족 표정과 반응 아이콘
- 원래 질문에 실제로 답했는지 확인하는 완료 판정과 회의록 요약
- 데스크톱, 태블릿, 모바일 대응

## 실행 방법

Python 3.10 이상을 권장합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`의 `OPENAI_API_KEY`를 본인의 키로 바꾼 뒤 실행합니다.

```powershell
python app.py
```

브라우저에서 `http://127.0.0.1:8000/`을 엽니다.

## 환경 변수

| 이름 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | 예 | 없음 | OpenAI API 키 |
| `AI_MEETING_MODEL` | 아니요 | `gpt-5.4-mini` | 회의와 요약에 사용할 모델 |
| `AI_MEETING_HOST` | 아니요 | `0.0.0.0` | 서버 바인딩 주소 |
| `AI_MEETING_PORT` | 아니요 | `8000` | 서버 포트 |
| `AI_MEETING_OPEN_BROWSER` | 아니요 | 없음 | `1`이면 실행 후 브라우저 열기 |

## 구조

- `app.py`: HTTP 서버와 회의 세션·스트리밍 관리
- `meeting.py`: 웹 입력/출력 어댑터와 최종 회의록 요약
- `character_meeting_v5.py`: 캐릭터, 개별 시각, 화자 선택, 발언, 상태 변화, 종료 판단을 담당하는 현재 회의 엔진
- `participant_session.py`: 사용자의 회의 참여 상태 관리
- `templates/index.html`: 화면 구조
- `static/`: 스타일, 동작, 글꼴, 캐릭터와 회의실 이미지
- `tests/`: API 비용 없이 실행 가능한 회귀·통합 테스트와 선택적 실대화 평가
- `PROJECT_STATE.md`: 확정된 설계, 금지된 과거 방식, 인수인계 상태

## 테스트

API 호출 없이 전체 자동 검사를 실행합니다.

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

실제 모델을 사용하는 대화 평가는 API 비용이 발생하므로 별도로 실행합니다.

```powershell
python tests/live_conversation_eval.py
```

## 주의

`.env`는 Git에 포함되지 않습니다. 공개 저장소에 API 키나 실제 회의 데이터가 들어가지 않았는지 커밋 전에 다시 확인하세요.
