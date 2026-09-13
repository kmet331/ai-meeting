from __future__ import annotations

"""Web adapter for the frozen character_meeting_v5 engine.

Important: conversational logic lives ONLY in character_meeting_v5.py.
This file translates web inputs/outputs and adds the secretary's final summary.
"""

import json
import os
import sys

import character_meeting_v5 as engine

ROLE_ORDER = [
    "CEO",
    "마케팅팀장",
    "디자이너",
    "개발자",
    "운영 담당자",
    "소비자 대표",
    "클라이언트",
]
NUMBER_TO_ROLE = {str(i + 1): role for i, role in enumerate(ROLE_ORDER)}


def parse_json(raw: str, fallback: dict) -> dict:
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end < start:
            return fallback
        return json.loads(raw[start:end + 1])
    except Exception:
        return fallback


def interpret_context(topic: str, participants: list[str]) -> dict:
    """Build a revisable plain-language reading without choosing a meeting mode."""
    raw = engine.ask(
        """회의가 시작되기 전에 사용자의 말을 문자 그대로 읽어 임시 해석문을 만든다.
회의/토론/잡담 같은 고정 유형을 붙이거나 해결책과 입장을 만들지 않는다.

참석자 중 주제 문장에 직접 등장하거나 명백히 행위자/요청자/대상인 사람만 관계를 적는다.
예: '클라이언트가 내일 미팅을 요청했다' → 클라이언트는 '미팅을 요청한 당사자'.
관계가 명시되지 않은 참석자는 빈 문자열로 둔다.
주제에 없는 PM, 팀장, 담당자, 제3자 같은 새 인물/직책을 만들지 않는다.

reading에는 사용자가 지금 누구에게 무엇을 듣고 싶어 하는지 자유로운 한두 문장으로 적는다.
requested_response에는 참석자들의 실제 발언에 무엇이 들어가야 하는지 구체적인 자유문장으로 적는다.
shared_result에는 사용자가 여러 의견 뒤에 하나의 공동 결과까지 명시적으로 요구한 경우에만 그 결과를 적고, 아니면 빈 문자열로 둔다.
participation_scope에는 누구의 답을 명시적으로 요구했는지 적는다. 문장에 없는 전원 참여를 추측하지 않는다.
nearby_mistake에는 원 요청과 비슷해 보이지만 대신 해서는 안 되는 다른 과업을 적는다. 고정 유형 이름을 붙이지 말고 이 문장 안에서만 구체적으로 구분한다.
둘 이상의 기대가 함께 있으면 하나를 버리지 말고 requested_response와 shared_result에 함께 보존한다.
둘 다 가능하면 하나를 추측해 확정하지 말고 uncertainty에 무엇이 모호한지 그대로 남긴다.
completion에는 실제 대화의 어떤 내용이 나오면 원 요청에 답했다고 볼 수 있는지 적는다. 진행 방법이나 준비 절차가 아니라 사용자가 받을 실제 결과를 기준으로 삼는다. 답 자체는 만들지 않는다.
이 해석은 이후 사용자의 설명으로 언제든 바뀔 수 있는 가설이다.
JSON만 출력한다.""",
        f"""회의 주제: {topic}
참석자: {', '.join(participants)}

JSON 형식:
{{
  "relations": {{"CEO":"", "운영 담당자":"", "마케팅팀장":"", "소비자 대표":"", "디자이너":"", "개발자":"", "클라이언트":""}},
  "reading": "사용자가 누구에게 무엇을 듣고 싶어 하는지",
  "requested_response": "참석자 발언에 실제로 들어가야 할 내용이나 행동",
  "shared_result": "명시적으로 요구된 공동 결과. 없으면 빈 문자열",
  "participation_scope": "명시적으로 답을 요구받은 사람 범위",
  "nearby_mistake": "비슷해 보이지만 대신 하면 안 되는 과업",
  "uncertainty": "아직 모호한 점. 없으면 없음",
  "completion": "어떤 실제 내용이 나오면 원 요청에 답한 것인지"
}}""",
    )
    data = parse_json(raw, {"relations": {}, "reading": topic, "uncertainty": "해석 실패", "completion": "사용자 말에 직접 답함"})
    relations = data.get("relations", {}) if isinstance(data, dict) else {}
    return {
        "relations": {
            role: str(relations.get(role, "")).strip()
            for role in participants
            if str(relations.get(role, "")).strip()
        },
        "reading": str(data.get("reading", topic)).strip() or topic,
        "requested_response": str(data.get("requested_response", data.get("completion", "사용자 말에 직접 답함"))).strip(),
        "shared_result": str(data.get("shared_result", "")).strip(),
        "participation_scope": str(data.get("participation_scope", "명시된 대상만")).strip(),
        "nearby_mistake": str(data.get("nearby_mistake", "원 요청 대신 진행 절차만 논의하는 것")).strip(),
        "uncertainty": str(data.get("uncertainty", "없음")).strip() or "없음",
        "completion": str(data.get("completion", "사용자 말에 직접 답함")).strip(),
    }


def infer_context_roles(topic: str, participants: list[str]) -> dict[str, str]:
    """Compatibility helper for callers that only need stated actor relations."""
    return interpret_context(topic, participants)["relations"]


def contextual_topic(topic: str, context: dict) -> str:
    if "relations" in context:
        relations = context.get("relations", {})
        reading = str(context.get("reading", topic))
        uncertainty = str(context.get("uncertainty", "없음"))
        completion = str(context.get("completion", "사용자 말에 직접 답함"))
        requested_response = str(context.get("requested_response", completion))
        shared_result = str(context.get("shared_result", ""))
        participation_scope = str(context.get("participation_scope", "명시된 대상만"))
        nearby_mistake = str(context.get("nearby_mistake", "원 요청 대신 진행 절차만 논의하는 것"))
    else:
        relations = context
        reading, uncertainty, completion = topic, "없음", "사용자 말에 직접 답함"
        requested_response, shared_result = completion, ""
        participation_scope, nearby_mistake = "명시된 대상만", "원 요청 대신 진행 절차만 논의하는 것"
    relation_text = "\n".join(f"- {role}: {desc}" for role, desc in relations.items()) or "- 별도 당사자 관계 없음"
    attendees = ", ".join(engine.CHARACTERS.keys())
    return f"""{topic}

[현재 참석자]
{attendees}

[상황의 사실관계 역할 — 의견이 아니라 주제에 적힌 당사자 관계]
{relation_text}

[현재 질문에 대한 임시 해석 — 회의 모드나 확정 명령이 아님]
{reading}
모호한 점: {uncertainty}
사용자가 실제로 받고 싶은 반응: {requested_response}
명시적으로 필요한 공동 결과: {shared_result or '없음'}
누구의 답을 요구했는지: {participation_scope}
대신 하면 안 되는 가까운 다른 과업: {nearby_mistake}
답이 되려면: {completion}

[대화 시 사실관계 규칙]
- 자기 자신이 위 상황의 당사자라면 제3자로 부르지 말고 '제가/저희가'처럼 당사자 시점으로 말한다.
- 주제와 현재 참석자 목록에 없는 사람, 직책, 부서, PM 등을 새 사실처럼 만들어내지 않는다. 참석자를 지칭해야 하면 현재 참석자 역할명을 사용한다.
- 필요한 정보가 주제에 없으면 있다고 가정하지 말고 질문/조건으로 남긴다.
- 이 요청 프레임은 참고 장식이 아니라 다음 발언을 고르는 기준이다. 다음 말이 '사용자가 실제로 받고 싶은 반응'에 직접 기여하는지 먼저 본다.
- 위 해석은 임시 가설이다. 실제 사용자가 대화 중 뜻을 설명하거나 바로잡으면 가장 최근 설명이 즉시 우선한다. 사용자의 단순 취향 발언을 의도 수정으로 오해하지 않는다.
- 말로 낼 수 있는 결과를 요구받았다면 그 실제 결과를 말한다. 방법을 묻지 않았는데 순서·형식·시간·준비 절차만 논의하며 원 요청을 대체하지 않는다.
- 여러 의견과 공동 결과가 함께 요구되면 앞부분을 건너뛰고 성급히 결론만 만들거나, 반대로 의견만 늘어놓고 공동 결과를 잊지 않는다.
- 해석이 모호하면 공동 목표나 합의를 가정하지 말고, 문자 그대로 답하거나 자연스럽게 확인한다."""



def goal_completion_gate(topic: str, history: list[dict], request_context: dict | None = None) -> dict:
    """Label the result after the controller ends; never restart conversation."""
    transcript = "\n".join(f"{x['speaker']}: {x['text']}" for x in history)
    request_context = request_context or {}
    raw = engine.ask(
        """너는 회의 종료 직전의 '목표 완료 확인'만 한다. 회의를 진행하거나 해결책을 만들지 않는다.

현재 주제가 무언가를 정하기/선택하기/결정하기/어떻게 할지 정하기 위한 회의라면, 실제 대화만 보고 아래 중 하나를 고른다.
- decided: 주제가 요구한 핵심 선택이나 방향이 실제로 정해졌다. 세부 실행 항목이 남아 있어도 핵심 방향이 정해졌으면 decided다. 특히 'A는 확정하고, 확인 결과에 따라 B를 추가한다'처럼 핵심 답과 조건부 추가 규칙이 정해졌다면 남은 확인사항 때문에 deferred로 낮추지 않는다.
- deferred: 핵심 결정에 필요한 구체적인 외부 정보/확인이 없고 현재 참석자끼리 계속 이야기해도 핵심 답을 낼 수 없다는 근거와 확인할 대상이 실제 대화에 드러났다. 같은 blocker를 다시 진술할 필요는 없다.
- incomplete: 대화가 잠잠해졌을 뿐, 핵심 선택도 결정 보류 이유도 아직 정리되지 않았다.
- not_goal: 애초에 결정/선택을 목표로 하는 주제가 아니다.

중요:
- 먼저 사용자 원 질문에서 실제로 결정해 달라는 대상(requested decision dimension)을 식별하고, 실제 대화의 결정이 바로 그 대상에 답하는지 대조한다. '회의에서 무언가 결정됨'만으로는 decided가 아니다.
- 질문형이 아닌 갈등·문제 상황도 실제 요청 차원을 읽는다. 예를 들어 '클라이언트는 많이 넣고 싶고 디자인팀은 덜어내고 싶다'의 핵심은 포함 범위나 둘을 조정할 원칙이다.
- '핵심부터 좁혀보자', '항목을 분류하자', '기준을 정해보자'처럼 다음에 문제를 푸는 절차만 정한 것은 그 문제의 답이 아니다. 실제로 남길 핵심, 포함 범위, 우선순위 또는 갈등을 푸는 구체적 원칙이 채택되어야 decided다.
- '꼭 필요한 것은 남기고 보기 좋은 것만 뺀다'처럼 누구나 동의할 수 있지만 실제 항목을 가르지 못하는 말은 아직 적용 가능한 원칙이 아니다. 적어도 실제 항목·개수·우선순위·경계 중 하나가 정해지거나, 추가 회의 없이 사례를 가를 수 있을 만큼 기준이 구체적이어야 한다.
- 반대로 '주말에 뭐 할 거야?'처럼 각자 계획이나 생각을 묻는 열린 대화는 모두가 하나의 답을 채택해야 하는 목표가 아니므로 not_goal이 자연스럽다.
- 사용자가 말로 낼 실제 결과를 요구했으면 그 결과가 대화에 나왔는지 본다. 방법을 요청하지 않았는데 순서·형식·시간·준비 절차만 정한 것은 원 요청의 완료나 결정이 아니다.
- 메뉴 선택 질문은 실제 메뉴 하나를 골랐는지, 콘셉트 선택 질문은 실제 톤을 골랐는지 본다. 비교나 평가 기준·테스트 방법만 정했다면 핵심 답이 아니다.
- '광고비와 프로모션 비용을 어떻게 배분할까?'에서 KPI나 테스트·집행 방법만 정한 상태는 decided가 아니다. 광고에 더 많이 쓰고 프로모션은 최소 수준으로 둔다는 배분 방향이나 70/30 같은 배분 자체가 정해져야 한다. 숫자 비율은 필수가 아니다.
- 광고 안에서 어떤 메시지에 쓸지, 프로모션을 누구에게 줄지만 정한 것을 광고비 대 프로모션비 배분 결정으로 확대 해석하지 않는다.
- 모든 자원 배분(allocation) 질문에 공통으로, 대상별 역할·집행 순서·KPI만 정한 것은 requested decision dimension을 채우지 못한다. 상대적 배분 우선순위/방향이나 비중이 실제로 정해져야 decided다. 이 기준은 광고뿐 아니라 인력·시간·예산 등에도 적용한다.
- 예를 들어 '광고로 최소 유입을 먼저 만들고 프로모션은 그 유입을 당기는 용도'는 역할/순서일 뿐 배분 답이 아니다. '광고는 최소 예산만 유지하고 나머지를 프로모션에 집중'은 상대적 배분 방향이므로 decided가 가능하다. '최소 유입'이라는 성과와 '최소 예산'이라는 자원 배분을 혼동하지 않는다.
- 배분 방향 자체를 나중에 정할 액션으로 남겼다면 지금 decided로 인정하지 않는다. 정확한 숫자 없이도 상대적 배분 방향이 정해졌으면 숫자 확인만 남았다는 이유로 낮추지 않는다.
- 핵심 답이 없고 추가 논의가 가능하면 incomplete다. '더 비교해 보자'거나 막연히 정보가 부족해 보인다는 이유만으로 deferred로 처리하지 않는다.
- deferred는 원 질문을 지금 결정할 수 없는 명시적 blocker/필요 정보가 구체적이며 현재 참석자만으로 확보할 수 없다는 근거가 실제 대화에 있을 때만 인정한다. 이미 그 상태가 명확하면 형식적인 보류 선언이나 같은 확인 질문의 반복을 요구하지 않는다. 보류 이유를 추측해서 만들지 않는다.
- 단순히 의견이 갈리거나 참석자가 답할 수 있는 질문이 남은 것은 deferred 근거가 아니다. 새 정보나 실제 조건부 선택 가능성이 있으면 이를 함께 보고, 이미 핵심 답과 조건부 규칙이 정해진 회의를 blocker 때문에 낮추지 않는다.
- 'A부터 검토/비교하고 안 맞으면 B를 검토한다'는 검토 순서이며 A/B 선택 답이 아니다. 예: 강렬함부터 시안을 보고 안 맞으면 귀여움을 비교하자는 것은 아직 콘셉트를 고른 것이 아니다.
- 반면 '기본 콘셉트는 강렬함으로 채택하고, 제품 식별 기준을 충족하지 못하면 귀여움으로 전환한다'처럼 채택과 조건별 실행 선택이 실제로 정해졌으면 conditional decision이다. 검토 계획과 실제 채택을 혼동하지 않는다.
- 핵심 답과 조건부 추가 규칙이 이미 정해졌다면 decided를 유지한다. 다만 한쪽 조건만 말한 것은 완전한 조건부 결정이 아니다. 예를 들어 '금요일 업무 공백이 해결되지 않으면 주 4일제를 도입하지 않는다'만 있고, 공백이 해결될 때 도입할지도 정하지 않았다면 원래 도입 여부는 incomplete다. '조건을 충족하면 도입하고, 아니면 도입하지 않는다'처럼 핵심 선택의 양 갈래가 실제로 정해져야 conditional decision이다. 핵심 선택 자체를 나중으로 미룬 것과 구분한다.
- reason에는 원 질문의 결정 대상과 그것에 대한 실제 답 또는 아직 빠진 답/명시적 blocker를 연결해서 적는다.
- 다수 의견이 비슷하다는 이유만으로 decided를 만들지 않는다.
- 실제 발언에 없는 합의나 결론을 만들지 않는다.
- 선택 자체를 막는 필수 조건과 선택 후 실행할 세부사항을 분리한다. 인원·수량·담당·배달 여부가 미확인이라는 사실만으로 메뉴 선호 선택을 deferred로 만들지 않는다. 왜 그 정보 없이는 원 질문의 선택 자체를 못 하는지 실제 발언에 근거가 있어야 한다.
- 예: 피자/짬뽕 중 무엇을 먹을지 고르는데 '인원부터 알려주세요'가 반복됐다는 이유만으로 결정 보류에 합의했다고 보지 않는다. 메뉴가 아직 채택되지 않았고 단순 주문 정보만 남았다면 incomplete이며 remaining_question은 어떤 메뉴를 고를지다.
- 사용자 '짬뽕!!!'은 분명한 선호이지만 전원 합의의 증거로 부풀리지 않는다. 뒤의 실제 대화가 짬뽕을 선택해 이어졌다면 메뉴 결정은 decided 가능하고 인원 확인은 후속 실행이다. 반대로 심각한 알레르기 때문에 먹을 수 있는 메뉴인지 아직 확인해야 한다는 실제 근거 등은 선택 자체의 blocker가 될 수 있다.
- remaining_question에는 incomplete일 때 아직 정해지지 않은 핵심 한 가지만 적는다. 필수가 아닌 실행 정보 때문에 대화가 샜다면 그 정보를 다시 묻지 말고 원래 선택으로 돌아오게 적는다.
- 아래 임시 해석은 시작 시점의 가설일 뿐이다. 대화 중 사용자가 뜻을 설명하거나 바로잡았다면 최근 사용자 발언으로 해석을 갱신해서 판정한다.

JSON만 출력한다.""",
        f"""회의 주제: {topic}
시작 시 임시 해석: {request_context.get('reading', topic)}
시작 시 모호한 점: {request_context.get('uncertainty', '없음')}
사용자가 실제로 받고 싶은 반응: {request_context.get('requested_response', request_context.get('completion', '사용자 말에 직접 답함'))}
명시적으로 필요한 공동 결과: {request_context.get('shared_result', '') or '없음'}
요구된 참여 범위: {request_context.get('participation_scope', '명시된 대상만')}
대신 하면 안 되는 가까운 다른 과업: {request_context.get('nearby_mistake', '') or '없음'}
처음 예상한 답의 기준: {request_context.get('completion', '사용자 말에 직접 답함')}
대화:
{transcript}

JSON:
{{"state":"decided|deferred|incomplete|not_goal","reason":"판단 이유 한 문장","remaining_question":""}}""",
    )
    data = parse_json(raw, {"state": "incomplete", "reason": "목표 완료 여부 확인 실패", "remaining_question": ""})
    state = str(data.get("state", "incomplete")).strip().lower()
    if state not in {"decided", "deferred", "incomplete", "not_goal"}:
        state = "incomplete"
    return {
        "state": state,
        "reason": str(data.get("reason", "")).strip(),
        "remaining_question": str(data.get("remaining_question", "")).strip(),
    }



def final_summary(topic: str, history: list[dict], end_reason: str, completion_state: str = "", request_context: dict | None = None) -> dict:
    transcript = "\n".join(f"{x['speaker']}: {x['text']}" for x in history)
    request_context = request_context or {}
    raw = engine.ask(
        """너는 회의 서기다. 아래 실제 대화에 나온 내용만 요약한다. 없는 합의나 담당자를 만들지 않는다.
- outcome: 주제가 요구한 핵심 결정이 실제로 정해졌으면 decided, 명시적 이유와 함께 미뤘으면 deferred, 애초에 공동 결정을 요구하지 않은 대화라면 discussed, 결정 주제였지만 답 없이 끝났으면 unresolved.
- decisions: 실제로 명시적으로 합의/결정된 내용만. 없으면 빈 배열.
- proposals: 합의되지는 않았지만 실제 대화에서 구체적으로 나온 방향/아이디어. 같은 뜻의 반복은 하나로 묶고 사람 수만큼 늘어놓지 않는다.
- issues: 아직 결정되지 않았거나 추가 선택이 필요한 핵심 쟁점. 핵심 방향이 결정된 뒤 남은 세부 실행 쟁점은 있어도 된다.
- actions: 대화가 끝난 뒤 실제로 하기로 제안하거나 약속한 후속 작업. 이미 대화에서 각자 의견을 말한 일을 미래 행동처럼 다시 적지 않는다. 담당자가 명시되지 않았으면 사람 이름을 만들지 않는다.
보류 상태와 '보류하기로 합의함'은 다르다. 질문이나 정보 요청의 반복을 '먼저 확인하기로 했다'는 결정으로 만들어내지 않는다. 사용자의 강한 선호는 그 사람의 의견으로 남기며 실제 채택이 있을 때만 회의 결정으로 쓴다.
'결정 없음'은 '논의 내용 없음'이 아니다. decisions가 비어 있어도 proposals에는 실제 논의를 남긴다.
같은 뜻을 말만 바꿔 반복한 발언은 proposals에서 하나로 합친다. 특히 '쉬다가 가볍게 나간다'처럼 차이가 없는 변형을 사람 수만큼 늘어놓지 않는다. 서로 실제로 다른 선택·구체적인 행동·이유만 나눠 적는다.
outcome이 discussed라면 issues에는 실제로 답하지 못한 질문이나 누군가 해결할 필요를 분명히 제기한 문제만 쓴다. 서로 다른 취향이나 관점을 그 자체로 해결해야 할 쟁점처럼 만들지 않는다.""",
        f"""주제:{topic}
시작 시 임시 해석:{request_context.get('reading', topic)}
사용자가 실제로 받고 싶은 반응:{request_context.get('requested_response', request_context.get('completion', '사용자 말에 직접 답함'))}
명시적으로 필요한 공동 결과:{request_context.get('shared_result', '') or '없음'}
대신 하면 안 되는 가까운 다른 과업:{request_context.get('nearby_mistake', '') or '없음'}
대화 중 사용자가 뜻을 바로잡았다면 그 최근 설명을 우선한다.
종료 이유:{end_reason}
종료 직전 목표완료 판정:{completion_state or '미제공'}
대화:
{transcript}
JSON만: {{"outcome":"decided|deferred|discussed|unresolved","decisions":[],"proposals":[],"issues":[],"actions":[]}}""",
    )
    data = parse_json(raw, {"outcome": "unresolved", "decisions": [], "proposals": [], "issues": [], "actions": []})

    def clean_item(item) -> str:
        # Some model responses wrap list items as {"content": "..."}.
        # The UI should receive plain text regardless of that harmless JSON variation.
        if isinstance(item, dict):
            item = item.get("content", item.get("text", item.get("value", "")))
        return str(item).strip()

    result = {
        key: [text for item in data.get(key, []) if (text := clean_item(item))]
        for key in ("decisions", "proposals", "issues", "actions")
    }
    outcome = str(data.get("outcome", "unresolved")).strip().lower()
    result["outcome"] = outcome if outcome in {"decided", "deferred", "discussed", "unresolved"} else "unresolved"
    # Keep the visible status consistent with the dedicated completion gate.
    if completion_state == "decided":
        result["outcome"] = "decided"
    elif completion_state == "deferred":
        result["outcome"] = "deferred"
    elif completion_state == "not_goal":
        result["outcome"] = "discussed"
    elif completion_state == "incomplete":
        result["outcome"] = "unresolved"
    return result


def print_summary(summary: dict, end_reason: str) -> None:
    print("회의가 종료되었습니다.", flush=True)
    print("📌 최종 결정", flush=True)
    for item in summary["decisions"]:
        print(f"- {item}", flush=True)
    if not summary["decisions"]:
        print("- 없음", flush=True)

    print("💡 미확정 제안", flush=True)
    for item in summary["proposals"]:
        print(f"- {item}", flush=True)
    if not summary["proposals"]:
        print("- 없음", flush=True)

    print("✅ 후속 작업", flush=True)
    for item in summary["actions"]:
        print(f"- {item}", flush=True)
    if not summary["actions"]:
        print("- 없음", flush=True)

    print("❓ 남은 핵심 쟁점", flush=True)
    for item in summary["issues"]:
        print(f"- {item}", flush=True)
    if not summary["issues"]:
        print("- 없음", flush=True)

    print(f"종료 이유: {end_reason}", flush=True)
    if summary.get("outcome") == "decided":
        status = "✅ 결정 완료"
    elif summary.get("outcome") == "deferred":
        status = "⏸️ 결정 보류"
    elif summary.get("outcome") == "discussed":
        status = "💬 의견 정리"
    else:
        status = "⚠️ 미해결"
    print(status, flush=True)


def main() -> None:
    topic = input().strip()
    participant_numbers = [x.strip() for x in input().strip().split(",") if x.strip()]
    mode_key = input().strip()

    participants = [NUMBER_TO_ROLE[n] for n in participant_numbers if n in NUMBER_TO_ROLE]
    if mode_key not in engine.MODES or len(participants) < 2:
        raise SystemExit(2)

    # The web process runs one meeting per subprocess. Filtering the engine's character
    # registry here keeps the frozen v4 logic intact while respecting UI selections.
    engine.CHARACTERS = {
        name: engine.CHARACTERS[name]
        for name in ROLE_ORDER
        if name in participants
    }
    engine.MODEL = os.getenv("AI_MEETING_MODEL", engine.MODEL)

    request_context = interpret_context(topic, participants)
    meeting_topic = contextual_topic(topic, request_context)
    completion = lambda raw_topic, turns: goal_completion_gate(raw_topic, turns, request_context)
    summarize = lambda raw_topic, turns, reason, state: final_summary(
        raw_topic, turns, reason, state, request_context
    )
    lenses = engine.create_initial_lenses(meeting_topic)
    if os.getenv("AI_MEETING_HUMAN") == "1":
        from participant_session import run_participating
        run_participating(topic, meeting_topic, mode_key, lenses,
                          completion, summarize)
        return
    history: list[dict] = []
    end_reason = "안전 최대 턴 도달"
    mode = engine.MODES[mode_key]
    final_gate = None

    for turn in range(1, mode["max_turns"] + 1):
        verdict = engine.controller(meeting_topic, mode_key, history, lenses)
        if history and not verdict["continue"]:
            end_reason = verdict.get("reason") or "더 이어질 살아 있는 대화가 없음"
            final_gate = completion(topic, history)
            break

        speaker = engine.select_speaker(meeting_topic, mode_key, history, lenses)
        speech = engine.speak(
            meeting_topic, mode_key, speaker, history, lenses[speaker]
        ).replace("\n", " ").strip()
        if not speech:
            lenses[speaker] = engine.spend_silent_impulse(lenses[speaker])
            continue
        history.append({"turn": turn, "speaker": speaker, "text": speech})
        lenses[speaker]["expressed"] = True

        print("@expression " + engine.LAST_EXPRESSION.get(speaker, "neutral"), flush=True)
        print(f"💬 {speaker}", flush=True)
        print(speech, flush=True)

        lenses[speaker] = engine.update_lens(
            meeting_topic, speaker, lenses[speaker], history
        )
    else:
        end_reason = "안전 최대 턴 도달"

    if final_gate is None:
        final_gate = completion(topic, history) if history else {"state": "incomplete"}
    summary = summarize(topic, history, end_reason, final_gate.get("state", ""))
    print_summary(summary, end_reason)


if __name__ == "__main__":
    main()

