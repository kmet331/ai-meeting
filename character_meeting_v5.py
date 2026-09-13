import os
import json
import random
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-5.4-mini"

MODES = {
    "1": {
        "label": "⚡ 초스피드",
        "minutes": 1,
        "max_turns": 8,
        "depth": "핵심 반응과 가장 중요한 충돌만 본다. 곁가지는 거의 따라가지 않는다.",
    },
    "3": {
        "label": "☕ 적당히",
        "minutes": 3,
        "max_turns": 18,
        "depth": "서로 다른 관점과 중요한 반응, 새 아이디어가 생기면 적당히 따라가 본다.",
    },
    "5": {
        "label": "🔥 제대로",
        "minutes": 5,
        "max_turns": 30,
        "depth": "의미 있는 관점 충돌과 새 아이디어의 가지를 충분히 탐색하되 끝난 이야기는 늘이지 않는다.",
    },
}

CHARACTERS = {
    "CEO": {
        "card": """성질이 조금 급하고 결론 없는 회의를 싫어하는 회사 대표.
결정과 속도를 먼저 본다. 선택지를 늘리기보다 줄이고, 지금 무엇을 고르면 되는지 핵심 질문을 집는다.
짧고 단정하게 끊는다. 이유가 필요하면 핵심만 말하며 장황한 분석 보고서는 하지 않는다.
좋은 이유를 들으면 빠르게 생각을 바꿀 수 있고, 모든 분야 전문가인 척하거나 매번 결론을 선언하지 않는다. 회의는 결정을 위한 도구라고 여기며, 결정할 것이 없다면 15분도 길다고 느낀다.""",
        "talk": 0.82,
    },
    "마케팅팀장": {
        "card": """사람 반응과 회의 분위기를 빨리 읽는 능글맞은 사람.
반응·설득·사람 심리가 먼저 눈에 들어온다. 상대가 어느 말에 혹하고 어디서 마음을 닫을지 상상하며 생각한다.
남의 말에 웃으며 한마디 찌르거나 즉각 반응한다. CEO에게도 은근히 깐족거릴 수 있고 좋은 아이디어는 솔직하게 좋아한다.
딱딱한 보고서체로 매번 분석하지 않는다. '오', 'ㅋㅋ', '그건 ~겠는데요'를 고정 도입부나 반복 말버릇으로 쓰지 않는다.
능글맞음은 정해진 문구가 아니라 방금 들은 말의 허점이나 사람 마음을 짚는 데서 드러난다.
회의 전체를 해설하거나 사람들의 숨은 심리를 계속 규정하지 않는다. 한 번 던진 관찰이나 농담은 그 자리에서 놓고 자기 취향과 이해관계로 돌아온다.
개인적인 질문에는 다른 사람의 반응을 분석하기 전에 자기 답을 솔직하게 말한다. 아이디어가 살아나는 잡담과 옆길을 즐긴다. 반응이 살아 있다면 한 시간 아이디어 회의도 아깝지 않다고 느낀다.""",
        "talk": 0.72,
    },
    "디자이너": {
        "card": """미묘한 어색함을 그냥 지나치지 못하는 예민한 완벽주의자.
인상·형태·경험·장면을 먼저 본다. 눈앞에 어떤 모습으로 보이고 손에 닿거나 사용될 때 어떤 느낌일지 구체적으로 그리며 생각한다.
감각적으로 걸리는 한 부분을 툭 짚거나 잠깐 멈춰 되묻는다. 좋으면 바로 인정하고 답답하면 짧고 직설적이다.
남의 말에서 시각적으로 재미있는 실마리를 발견하면 생각이 뻗기도 한다. 항상 반대하지 않으며 KPI만으로 좋고 나쁨을 판단하지 않는다. 10분짜리 성급한 피드백보다 40분 동안 실제 화면을 보며 고치는 대화를 선호한다. 충분한 맥락 없이 빨리 자르면 미묘한 문제를 놓친다고 느낀다.""",
        "talk": 0.64,
    },
    "개발자": {
        "card": """회의 자체를 별로 좋아하지 않는 극도로 건조한 사람.
실제 구현·복잡도·예외가 자기 관심사다. 기술 문제가 나오면 무엇을 만들어야 하고 어디서 꼬일지부터 본다.
짧고 건조하게 필요한 부분만 답한다. 자기 영역과 무관하면 거리두기나 관심 없음도 자연스럽고 끝까지 침묵해도 이상하지 않다.
발언하게 됐다고 마케팅·전략 전문가 행세를 하거나 관심 없는 주제에 그럴듯한 분석을 덧붙이지 않는다.
기술 문제가 실제로 나오면 정확히 답하되 주제에 없는 구현 문제를 억지로 만들지 않는다.
마케팅/디자인/운영 전략의 결론을 주도하거나 광고 유입·프로모션 전환의 원리를 전문가처럼 설명하지 않는다.
자기 영역 밖에서는 짧게 거리를 두고, 실제 관련이 있을 때만 측정 가능성·데이터 분리·구현 복잡도·시스템 예외처럼 기술적으로 확인 가능한 부분에 한정한다.
거리두기 뒤에 남의 분야 전략 분석을 덧붙이지 않는다. 특정 거리두기 문장을 고정 말버릇으로 삼지 않는다. 회의보다 문서·메시지를 선호한다. 다만 함께 화면을 보며 버그를 푸는 시간이라면 길이보다 실제 해결 여부를 본다.""",
        "talk": 0.30,
    },
    "운영 담당자": {
        "card": """실무 경험이 많은 현실적인 해결사. 약간 지친 결이 있다.
실행·담당·일정·운영부담을 먼저 본다. 누가 언제 처리하고 이후 반복해서 챙길 일이 무엇인지 실제 작업으로 바꿔 생각한다.
거창한 전략 대신 당장 걸리는 일 하나를 현실적으로 짚거나 담당과 일정을 짧게 묻는다. 매번 한숨이나 불평을 반복하지 않는다.
방법이 보이면 그냥 처리하고 실제 운영 문제가 없으면 리스크를 억지로 찾아내지 않는다. 추상 전략론이나 없는 담당자를 만들지 않는다. 회의가 짧아도 담당과 다음 일이 빠져 다시 모이면 더 피곤하다고 느낀다. 필요한 확인이 끝날 때까지는 30분을 넘겨도 낫다고 본다.
취향 문제에는 아무거나 괜찮을 수도 있다.""",
        "talk": 0.38,
    },
    "소비자 대표": {
        "card": """감정 표현이 솔직하고 밝은 사람.
내가 실제로 사고 쓰는 상황부터 생각한다. 광고를 보고 누를지, 가격이나 할인 조건에서 멈출지, 써 보고 다시 살지를 자기 행동으로 말한다.
1인칭 일상어로 좋으면 좋다, 귀찮으면 안 하겠다고 툭 말한다. 다른 모든 소비자의 마음을 대표하는 정답처럼 말하지 않는다.
회사 내부 KPI나 마케팅 전문용어를 남발하거나 회사의 전략을 대신 정리하지 않는다.
친구에게 보여주고 싶은지, 부담스러운지 같은 생활 속 반응이 자연스럽게 실마리가 된다. 가벼운 감탄도 매번 반복하지 않는다. 회사 내부 회의 형식에는 큰 애착이 없다. 내가 알아들을 수 있고 내 의견이 실제로 반영되지 않으면 짧든 길든 솔직히 관심이 없다.""",
        "talk": 0.66,
    },
    "클라이언트": {
        "card": """원하는 결과를 떠올리며 듣는 해맑고 즉흥적인 사람.
남의 아이디어를 쉽게 좋아하고 듣다가 자기 눈에 보고 싶은 결과나 새 요구·아이디어가 떠오르곤 한다.
생각이 정리되기 전에 묻거나 말을 덧붙였다가 스스로 너무 커졌나 싶어 멈출 수도 있다. 제약을 설명받으면 금방 납득하기도 한다.
매번 선택지·이유·조건을 논리적으로 완벽하게 정리하는 컨설턴트가 아니다. 고정 감탄사를 되풀이하지 않는다.
매번 새 요구를 낼 의무는 없다. 현재 주제와 실제 대화에서 이어지는 생각만 말한다. 여러 아이디어를 듣는 시간을 좋아한다. 재미있는 제안이 계속 나오면 회의가 길어져도 괜찮지만 기술 설명만 이어지면 금방 놓친다.""",
        "talk": 0.70,
    },
}

# Display-only hints. They never affect speaker selection or completion.
EXPRESSIONS = {"neutral", "talking", "thinking", "surprised", "pleased", "unconvinced"}
LAST_EXPRESSION = {}
LAST_SELECTION_IMPULSE = {}
LAST_SELECTION_TARGET = {}
LAST_SELECTION_QUESTION = {}
LAST_SELECTION_FACTS = {}
LAST_SELECTION_NEW_PART = {}
LAST_ALIVE_OPENING = ""


# A loose private-life nudge prevents every fictional participant from collapsing
# into the same safe cafe/walk/Netflix answer. It is not a required hobby or a
# stance assignment: the model may ignore it when it does not fit the topic.
PERSONAL_TEXTURES = {
    "CEO": [
        "쉬는 날에도 하나는 확실히 해치우고 나머지는 비워두는 편",
        "좋은 식사나 짧은 드라이브처럼 만족감이 분명한 선택을 좋아함",
        "갑자기 마음이 가면 예약 없이 바로 움직이는 편",
        "사람을 오래 만나기보다 목적 있는 약속 하나를 선호함",
    ],
    "마케팅팀장": [
        "새로 뜬 장소나 사람들이 몰리는 장면을 직접 구경하는 걸 좋아함",
        "친한 사람과 가볍게 떠들거나 재미있는 일을 주변에 공유하는 편",
        "사진·짧은 영상·요즘 유행을 보다가 즉흥적으로 계획을 바꾸기도 함",
        "혼자 쉬어도 결국 사람 반응이 궁금해 연락을 한 번 돌리는 편",
    ],
    "디자이너": [
        "서점·전시·문구점처럼 눈과 손이 즐거운 곳에서 오래 머무는 편",
        "빛, 날씨, 음악, 공간 분위기가 마음에 들면 계획 없이 걷기도 함",
        "집에서 책상이나 방 한구석을 자기 방식으로 정리하며 쉬기도 함",
        "사람 많은 명소보다 작고 조용한 공간을 발견하는 걸 좋아함",
    ],
    "개발자": [
        "밀린 게임이나 개인 프로젝트처럼 혼자 깊게 빠질 일을 좋아함",
        "집에서 고양이·책·영상과 조용히 지내는 쪽이 편함",
        "기술과 무관한 일엔 아무 생각 없이 늦잠부터 잘 수도 있음",
        "밖에 나가더라도 목적 하나만 끝내고 빨리 돌아오는 편",
    ],
    "운영 담당자": [
        "밀린 집안일이나 장보기를 끝내야 비로소 마음 놓고 쉬는 편",
        "사람 많은 일정 하나보다 가까운 곳에서 끼니와 볼일을 함께 해결하는 편",
        "평소 못 잔 잠을 보충하거나 아무 연락도 안 받고 쉬고 싶어 함",
        "계획을 세우기보다 그날 체력에 맞춰 가장 덜 번거로운 걸 고름",
    ],
    "소비자 대표": [
        "먹고 싶던 메뉴·세일·새로 나온 물건처럼 생활 속 작은 즐거움에 잘 움직임",
        "후기만 보다가 직접 써보거나 먹어보고 싶어지는 편",
        "혼자 쉬는 것도 좋지만 심심하면 가까운 사람을 가볍게 만남",
        "비싸거나 번거로우면 기대했어도 바로 포기할 수 있음",
    ],
    "클라이언트": [
        "새 카페·짧은 나들이·갑자기 떠오른 취미를 즉흥적으로 해보고 싶어 함",
        "누가 재미있는 제안을 하면 원래 계획을 잊고 금방 따라갈 수 있음",
        "하고 싶은 걸 둘셋 떠올렸다가 당일 기분에 하나를 고르는 편",
        "좋아 보이는 경험은 주변 사람과 함께 해보고 싶어 함",
    ],
}

DEFAULT_TOPICS = [
    "회사 마스코트를 귀엽고 무난하게 만들지, 일부러 못생기고 이상해서 기억에 남게 만들지 정한다.",
    "오늘 퇴근 후 갑자기 전 직원 회식을 할지 말지 정한다.",
    "출시 일주일 전 클라이언트가 전체 디자인을 바꾸고 싶다고 했다. 어떻게 할지 정한다.",
]

def ask(system, user):
    r = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return r.output_text.strip()

def compact_history(history, limit=14):
    if not history:
        return "(아직 발언 없음)"
    return "\n".join(f"{x['speaker']}: {x['text']}" for x in history[-limit:])

def create_private_sparks(topic):
    """Give each independent lens a different doorway into the same topic."""
    cast = "\n".join(f"- {name}: {info['card']}" for name, info in CHARACTERS.items())
    system = """너는 회의 전에 배우별 사적인 출발점을 건네는 캐스팅 디렉터다.
찬성·반대 역할이나 발언 순서를 배정하지 않는다. 결론도 만들지 않는다.
각 인물이 자기 성격으로 이 주제를 볼 때 남들과 다른 문으로 들어갈 수 있도록, 개인적으로 걸릴 질문·장면·이해관계 하나를 짧게 건넨다.
억지로 모두를 다르게 만들 필요는 없지만 같은 모범 답안의 표현만 바꾼 단서는 피한다. 누군가는 관심 없거나 질문 자체를 이상하게 볼 수도 있다.
주제에 없는 질병·약속·마감·예산 같은 외부 사실은 만들지 않는다. 이 단서들은 서로에게 공개되지 않는다. JSON만 출력한다."""
    raw = ask(system, f"""주제: {topic}

캐릭터:
{cast}

JSON: {{"sparks": {{"캐릭터 이름":"그 사람만 보는 사적인 출발점"}}}}""")
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        sparks = data.get("sparks", {})
        if isinstance(sparks, dict):
            return {name: str(sparks.get(name, "")).strip() for name in CHARACTERS}
    except (ValueError, TypeError):
        pass
    return {name: "" for name in CHARACTERS}


def create_initial_lenses(topic):
    """
    '찬성/반대/절충안'을 미리 만들지 않는다.
    각 캐릭터가 이 주제를 보자마자 개인적으로 무엇에 꽂히는지만 독립 생성한다.
    """
    lenses = {}
    private_sparks = create_private_sparks(topic)
    for name, info in CHARACTERS.items():
        texture = random.choice(PERSONAL_TEXTURES.get(name, ["특별한 생활 단서 없음"]))
        system = f"""너는 회의 시작 직전의 {name}이다.

[이 사람]
{info['card']}

[가벼운 생활 단서]
{texture}

[이 사람만 받은 사적인 출발점]
{private_sparks.get(name) or '별도 단서 없음'}

아직 다른 참석자의 말은 하나도 듣지 못했다. 이 사람 혼자 주제를 본 첫 반응을 만든다.
위 캐릭터 설명은 참고 예시가 아니라 이 사람에 관한 사실이다. 주제가 설명 속 선호와 직접 맞닿으면 lens·want·impulse에 그 선호가 드러나야 하며, 무난한 일반론으로 약화하거나 반대 성향으로 바꾸지 않는다.
사적인 출발점은 남에게 공개되지 않았고 결론을 강제하지 않는다. 캐릭터가 동의하지 않으면 버릴 수 있다. 캐릭터의 실제 성격과 선호를 안전한 평균 답으로 누그러뜨리지 않는다. 분명히 좋거나 싫으면 그대로 두고, 관심이 없으면 관심 없다고 둔다. 정말 마음이 갈릴 때가 아니면 '좋지만 조건이 필요하다'는 양쪽 답으로 피하지 않는다.

지금 가장 먼저 당기는 것, 거슬리는 것, 궁금한 것 중 하나를 잡는다. 다른 사람과 달라지려고 반대하거나 아직 해결책을 완성하지 않는다. 직업과 상관없는 일상 주제라면 직무 대신 개인 취향으로 답한다.
개인 질문에는 추상적인 휴식보다 행동·장소·물건 하나가 보이는 작은 장면을 만들 수 있다. quirk는 상황과 맞을 때만 나오는 조금 이상한 진심이며 없어도 된다.
허구 인물의 가벼운 취향은 상상할 수 있지만 질병·알레르기·약속·마감·예산처럼 결정을 바꾸는 외부 사실은 만들지 않는다. 메뉴 선택을 인원이나 주문 절차 문제로 바꾸지 않는다.
생활 단서는 결론이나 의무 설정이 아니므로 어울리지 않으면 무시한다."""

        user = f"""회의 주제:
{topic}

JSON 하나만 출력:
{{
  "mood": "오늘 이 사람의 에너지와 기분을 짧게",
  "lens": "이 사람이 이 주제에서 개인적으로 먼저 꽂힌 지점",
  "want": "지금 개인적으로 원하는 것. 없으면 없음",
  "friction": "쉽게 넘기기 어려운 불편이나 한계. 없으면 없음",
  "personal_detail": "개인 질문에 답할 때 꺼낼 구체적인 자기 답. 해당 없으면 없음",
  "quirk": "관련 있을 때만 나올 사소하고 조금 이상한 진심이나 장면. 없으면 없음",
  "impulse": "그 지점 때문에 지금 떠오르는 짧은 생각/욕망/질문. 결론일 필요 없음",
  "interest": 0부터 100 사이 정수,
  "strength": 0부터 100 사이 정수
}}"""
        raw = ask(system, user)
        try:
            d = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
            lenses[name] = {
                "mood": str(d.get("mood", "평소와 비슷함")),
                "lens": str(d.get("lens", "특별히 꽂힌 지점 없음")),
                "want": str(d.get("want", "없음")),
                "friction": str(d.get("friction", "없음")),
                "personal_detail": str(d.get("personal_detail", "없음")),
                "private_texture": texture,
                "private_spark": private_sparks.get(name, ""),
                "quirk": str(d.get("quirk", "없음")),
                "impulse": str(d.get("impulse", "별 생각 없음")),
                "interest": max(0, min(100, int(d.get("interest", 30)))),
                "strength": max(0, min(100, int(d.get("strength", 30)))),
                "expressed": False,
            }
        except Exception:
            lenses[name] = {
                "mood": "평소와 비슷함",
                "lens": raw[:160] or "특별히 꽂힌 지점 없음",
                "want": "없음",
                "friction": "없음",
                "personal_detail": "없음",
                "private_texture": texture,
                "private_spark": private_sparks.get(name, ""),
                "quirk": "없음",
                "impulse": "별 생각 없음",
                "interest": 30,
                "strength": 30,
                "expressed": False,
            }
    return lenses

def controller(topic, mode_key, history, lenses):
    """
    합의/결론을 판정하지 않는다.
    아직 꺼낼 가치가 있는 개인 관점 또는 살아 있는 대화 가지가 있는지만 본다.
    """
    global LAST_ALIVE_OPENING
    mode = MODES[mode_key]
    if not history:
        LAST_ALIVE_OPENING = ""
        return {"continue": True, "reason": "대화 시작", "unexpressed": []}

    lens_view = "\n".join(
        f"- {n}: mood={s.get('mood', '')} | lens={s.get('lens', '')} | "
        f"want={s.get('want', '')} | friction={s.get('friction', '')} | "
        f"personal_detail={s.get('personal_detail', '')} | "
        f"private_texture={s.get('private_texture', '')} | "
        f"private_spark={s.get('private_spark', '')} | "
        f"quirk={s.get('quirk', '')} | "
        f"impulse={s.get('impulse', '')} | interest={s.get('interest', 0)} | "
        f"strength={s.get('strength', 0)} | expressed={s.get('expressed', False)}"
        for n, s in lenses.items()
    )

    system = """너는 대화가 아직 살아 있는지만 보는 관찰자다.
결론, 정답, 합의, 목표 달성 여부는 판단하지 않는다.

누군가의 최근 말이 다른 사람을 실제로 움직였거나, 직접 받은 질문에 답할 말이 있거나,
아직 입 밖에 안 나온 개인적 긴장·호기심·반응이 자연스럽게 이어질 때만 CONTINUE다.
"이제 무엇을 정해보자", "먼저 좁혀보자" 같은 진행 제안은 그 자체로 긴장을 해소한 답이 아니다.
그 말을 듣고 누군가가 구체적으로 내놓을 내용이나 반응이 이미 있다면 대화는 아직 살아 있다.
남은 말이 같은 의견의 복창, 정리, 의례적 동의뿐이면 END다. 같은 안전한 취향을 다른 참석자가 자기 말처럼 한 번 더 말하는 것도 새 관점이 아니다.
CONTINUE라면 아직 말하지 않은 사람 수가 아니라, 실제로 다음 발언에 들어갈 새 내용을 한 사람의 이름과 함께 opening에 구체적으로 적을 수 있어야 한다.
"누구도 아직 답하지 않았다", "다른 사람 의견도 들어볼 수 있다"처럼 가능성만 남은 것은 근거가 아니다. 열린 질문도 모든 사람이 답할 필요는 없다.
다만 원문이 참석자들에게 말로 바로 수행할 일을 명시했다면, 아직 실제 수행 내용은 없고 순서·형식·시간만 논의한 상태를 답이 나온 것으로 보지 않는다. '자기소개 하기'에서 실제 자기소개 대신 소개 방식을 정한 경우가 그렇다. 원문이 각 참석자의 수행을 분명히 요구할 때 서로 다른 실제 결과는 발언 균등이 아니라 요청 자체의 남은 내용이다.
opening이 이미 나온 결론·취향·조건의 말바꾸기에 그치면 END다.
한편 구체적인 새 질문, 예상 밖의 개인 경험, 이해관계 충돌, 농담으로 바뀐 분위기처럼 실제로 다음 말을 달라지게 할 것이 있으면 CONTINUE다.
END 전에 아직 말로 나오지 않은 private lens와 실제 대화를 대조한다. 이미 나온 답의 바꿔 말하기가 아닌 구체적인 차이를 한 문장으로 집을 수 있으면 opening에 적고 CONTINUE다. 차이를 만들기 위해 억지 반대나 새 의제를 발명하지 않는다.
특히 아직 말하지 않은 사람이 현재 대화의 전제와 다른 선호·대가·경험을 실제 private state에 갖고 있다면, 전원이 말해야 해서가 아니라 그 차이가 대화를 바꾸므로 CONTINUE다. 반대로 같은 결론에 직무별 이유만 붙이는 정도라면 남은 사람이 있어도 END다.
END를 고를 때는 opening을 빈 문자열로 두고, 왜 남은 private state도 이미 나온 말과 의미상 같은지 확인한다.
원 질문이 미완성이어도 대화가 말라 있으면 END할 수 있다.
전원이 말할 필요도, 결론을 낼 필요도 없다. 새 의제나 쟁점을 만들지 않는다."""

    user = f"""회의 주제: {topic}
회의 모드: {mode['label']}
깊이: {mode['depth']}

각자의 개인 렌즈:
{lens_view}

최근 대화:
{compact_history(history, 16)}

JSON만 출력:
{{
  "continue": true 또는 false,
  "reason": "대화가 살아 있거나 끝난 이유를 한 문장으로",
  "opening": "아직 말로 나오지 않은 구체적인 차이. 없으면 빈 문자열"
}}"""
    raw = ask(system, user)
    try:
        d = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
        result = {
            "continue": bool(d.get("continue", False)),
            "reason": str(d.get("reason", "")),
            "unexpressed": [],
        }
        LAST_ALIVE_OPENING = str(d.get("opening", "")).strip() if result["continue"] else ""
        return result
    except Exception:
        LAST_ALIVE_OPENING = ""
        return {"continue": False, "reason": "controller parse fallback", "unexpressed": []}

def select_speaker(topic, mode_key, history, lenses, preferred=None):
    previous = history[-1]["speaker"] if history else None
    candidates = [n for n in CHARACTERS if n != previous]

    last_spoken = {
        name: next(
            (x["text"] for x in reversed(history) if x["speaker"] == name),
            "(아직 말하지 않음)",
        )
        for name in candidates
    }
    candidate_view = "\n".join(
        f"- {n}: mood={lenses[n].get('mood', '')} | lens={lenses[n].get('lens', '')} | "
        f"want={lenses[n].get('want', '')} | friction={lenses[n].get('friction', '')} | "
        f"personal_detail={lenses[n].get('personal_detail', '')} | "
        f"private_texture={lenses[n].get('private_texture', '')} | "
        f"private_spark={lenses[n].get('private_spark', '')} | "
        f"quirk={lenses[n].get('quirk', '')} | "
        f"impulse={lenses[n].get('impulse', '')} | interest={lenses[n].get('interest', 0)} | "
        f"strength={lenses[n].get('strength', 0)} | 최근 자기 발언={last_spoken[n]} | "
        f"평소 발언성향={CHARACTERS[n]['talk']}"
        for n in candidates
    )

    system = """다음에 저절로 입이 열릴 한 사람을 고른다.
후보에 보이는 개인 렌즈와 사적인 생활 결은 서로에게 공개되지 않은 선택 참고자료다. 실제 대화에 나오기 전에는 누구도 다른 사람의 렌즈를 들었다고 여기거나 반응할 수 없다. 대화가 아직 비어 있으면 target은 회의 주제 자체다.
발언 기회나 역할 균형을 맞추지 않는다. 방금 직접 말을 받은 사람, 들은 말 때문에 감정이나 생각이 움직인 사람,
자기 안에 아직 남은 마찰을 지금 말하고 싶은 사람이 자연스럽다. 아무 관련 없는 전문 의견이나 반대역을 만들지 않는다.

target에는 그 사람을 움직인 구체적인 상대나 최근 발언을, impulse에는 지금 입 밖에 내고 싶은 핵심을 적는다.
question에는 최근의 특정 지목 질문뿐 아니라 여러 사람에게 열린 질문도, 선택된 사람이 지금 답하기로 했다면 그 질문을 그대로 적는다. 없으면 빈 문자열을 적는다.
facts에는 최근 대화에서 자기 것이 아닌 채 보존해야 할 구체적인 사실과 그 사실을 말한 사람을 짧게 적는다. 특히 '나'가 말한 일정·취향·상태는 원래 화자를 반드시 '나'로 표시한다.
특정 이름·직책으로 지목했거나 바로 앞 화자에게 이어 묻는 질문이면, 그 대상이 자연스럽게 직접 답한다.
여럿에게 넓게 던진 질문은 모두가 답할 의무가 없다. 다만 그 질문 때문에 선택된 사람은 대화 분위기를 해설하지 말고 자기 답을 꺼낸다.
주제가 참석자에게 지금 말로 수행할 일을 요청했다면, 선택된 사람의 target과 impulse는 수행 방법 논의가 아니라 그 사람이 낼 실제 내용이어야 한다.
최근 자기 발언과 impulse가 사실상 같다면 새 압력이 생긴 것이 아니다. 다른 후보에게 실제 반응이 있으면 그 사람이 더 자연스럽다.
누군가 새 계획·취향·사실을 말했으면 그 구체적인 내용이 누구를 어떻게 움직였는지 본다. 그 말을 자기 고민을 반복하는 발판으로만 쓰지 않는다.
방금 자기 impulse를 이미 말한 사람에게는 그 압력이 남아 있지 않다. 그 뒤의 새 발언이 실제로 다시 건드렸을 때만 새 impulse를 만든다.
new_part에는 선택된 사람의 최근 자기 발언들과 비교해 이번에 새로 더할 구체적인 내용만 적는다. 단순 동의나 같은 결론의 말바꾸기는 새 내용이 아니다. 새 내용이 없다면 그 사람을 다시 고르지 않는다.
개인 취향을 묻는 대화에서는 비슷한 중간값을 또 말하는 사람보다 자기 장면이 구체적이거나 방금 말에 예상 밖의 반응이 생긴 사람이 자연스럽다.
사용자가 '바쁠 것 같다'처럼 구체적인 자기 상태를 새로 꺼냈다면, 실제로 궁금해진 사람은 이유나 내용을 물을 수 있다. 반드시 질문을 만들 필요는 없다.
사용자와 다수의 의견도 다른 참석자의 한 발언일 뿐이다. 기존 취향과 한계는 자동으로 사라지지 않는다.
공동 선택과 개인 선택이 다를 수 있지만, 대화에 없는 사정은 만들지 않는다."""

    user = f"""주제: {topic}
모드: {MODES[mode_key]['label']}

대화 생명 판단에서 발견한 아직 안 나온 차이:
{LAST_ALIVE_OPENING or '없음'}
이 차이가 실제 자기 상태와 맞는 사람이 있을 때만 참고하며, 맞는 사람이 없으면 억지로 담당시키지 않는다.

최근 대화:
{compact_history(history, 12)}

후보:
{candidate_view}

JSON 하나만 출력:
{{
  "speaker": "후보 중 이름 하나",
  "target": "방금 누구의 어떤 말에 반응하는지",
  "impulse": "이 사람이 방금 말하고 싶어진 구체적인 이유 한 문장",
  "question": "이 사람이 직접 답해야 하는 질문. 없으면 빈 문자열",
  "facts": "화자를 바꾸면 안 되는 최근 사실과 원래 화자. 없으면 빈 문자열",
  "new_part": "최근 자기 발언과 달리 이번에 새로 더할 구체적인 내용"
}}"""
    raw = ask(system, user).strip()
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        picked = str(data.get("speaker", "")).strip()
        target = str(data.get("target", "")).strip()
        impulse = str(data.get("impulse", "")).strip()
        question = str(data.get("question", "")).strip()
        facts = str(data.get("facts", "")).strip()
        new_part = str(data.get("new_part", "")).strip()
        if picked in candidates:
            LAST_SELECTION_IMPULSE[picked] = impulse or lenses[picked]["impulse"]
            LAST_SELECTION_TARGET[picked] = (target or history[-1]["text"]) if history else topic
            LAST_SELECTION_QUESTION[picked] = question if history else ""
            LAST_SELECTION_FACTS[picked] = facts
            LAST_SELECTION_NEW_PART[picked] = new_part
            return picked
    except (ValueError, TypeError):
        pass

    picked = raw
    if picked in candidates:
        LAST_SELECTION_IMPULSE[picked] = lenses[picked]["impulse"]
        LAST_SELECTION_TARGET[picked] = history[-1]["text"] if history else topic
        LAST_SELECTION_QUESTION[picked] = ""
        LAST_SELECTION_FACTS[picked] = ""
        LAST_SELECTION_NEW_PART[picked] = ""
        return picked

    pool = candidates
    weights = []
    for n in pool:
        s = lenses[n]
        novelty = 1.25 if not s["expressed"] else 0.75
        weights.append(
            max(0.03, CHARACTERS[n]["talk"] *
                (0.2 + s["interest"] / 100) *
                (0.3 + s["strength"] / 100) * novelty)
        )
    picked = random.choices(pool, weights=weights, k=1)[0]
    LAST_SELECTION_IMPULSE[picked] = lenses[picked]["impulse"]
    LAST_SELECTION_TARGET[picked] = history[-1]["text"] if history else topic
    LAST_SELECTION_QUESTION[picked] = ""
    LAST_SELECTION_FACTS[picked] = ""
    LAST_SELECTION_NEW_PART[picked] = ""
    return picked

def review_human_reply(speaker, draft, latest_human, question, facts):
    """Repair only interaction breaks after a real user's latest utterance."""
    system = f"""너는 {speaker}의 발언을 검열하거나 매끈하게 다듬는 편집자가 아니다.
아래 초안을 원칙적으로 그대로 돌려준다. 다음 중 실제로 깨진 것이 있을 때만 최소한으로 고친다.
- 사용자가 물은 질문을 외면하고 이전 주제로 돌아갔다.
- 사용자가 말한 일정·취향·상태를 화자 자신의 경험처럼 1인칭으로 훔쳤다.
- 사용자의 구체적인 말과 아무 관계 없이 자기 말을 되풀이했다.

고칠 때도 {speaker}의 말투, 농담, 머뭇거림, 짧음, 미완성된 결을 보존한다. 새 정보나 모범 답안, 합의, 친절한 요약을 보태지 않는다.
JSON만 출력한다."""
    user = f"""사용자의 최신 발언: {latest_human}
직접 답하기로 한 질문: {question or '없음'}
소유권을 보존할 사실: {facts or '없음'}
{speaker}의 발언 초안: {draft}

JSON: {{"text":"그대로 유지하거나 필요한 부분만 고친 실제 발언"}}"""
    raw = ask(system, user)
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        revised = data.get("text")
        if isinstance(revised, str) and revised.strip():
            return revised.strip()
    except (ValueError, TypeError):
        pass
    return draft


def speak(topic, mode_key, speaker, history, lens):
    target = LAST_SELECTION_TARGET.get(speaker, history[-1]["text"] if history else topic)
    impulse = LAST_SELECTION_IMPULSE.get(speaker, lens.get("impulse", ""))
    question = LAST_SELECTION_QUESTION.get(speaker, "")
    facts = LAST_SELECTION_FACTS.get(speaker, "")
    new_part = LAST_SELECTION_NEW_PART.get(speaker, "")
    own_turns = [x["text"] for x in history if x["speaker"] == speaker]
    recent_self = "\n".join(f"- {line}" for line in own_turns[-3:]) or "(아직 말하지 않음)"
    latest_human = next(
        (x["text"] for x in reversed(history) if x["speaker"] == "나"),
        "(아직 발언 없음)",
    )
    system = f"""너는 지금 대화 중인 {speaker} 한 사람이다.

[이 사람]
{CHARACTERS[speaker]['card']}

[남에게 보이지 않는 현재 상태]
기분: {lens.get('mood', '')}
신경 쓰이는 것: {lens.get('lens', '')}
원하는 것: {lens.get('want', '')}
걸리는 것: {lens.get('friction', '')}
개인 질문에 꺼낼 구체적인 답: {lens.get('personal_detail', '없음')}
사적인 생활 결: {lens.get('private_texture', '없음')}
나만 받은 출발점: {lens.get('private_spark', '없음')}
오늘의 대화 기울기: {lens.get('meeting_pull', '없음')}
말해도 될 법한 사소한 이상함: {lens.get('quirk', '없음')}

[지금 반응하게 만든 말]
{target}

[입 밖에 내고 싶은 것]
{impulse}

[내가 직접 받은 질문]
{question or '없음'}

[화자를 바꾸면 안 되는 최근 사실]
{facts or '없음'}

[가장 최근 실제 사용자 '나'의 말]
{latest_human}

[내 최근 발언들]
{recent_self}

[이번에 새로 더할 부분]
{new_part or '없음'}

회의 진행자나 요약자가 아니라 이 사람 자신으로 말한다.
방금 말에 대한 반응은 질문, 농담, 부분 동의, 거절, 미완성 생각, 짧은 감탄만으로 끝나도 된다.
target의 구체적인 내용에 답한다. 그 말을 계기로 자기 원래 고민을 그대로 다시 말하는 것은 반응이 아니다.
내가 답하기로 한 질문이 있으면 특정 지목인지 열린 질문인지와 관계없이 발화 첫 문장 안에서 실제 답부터 말한다. 답을 모르거나 생각이 없으면 그것 자체를 솔직하게 답한다. 질문을 계기로 원래 주제로 후퇴하거나 대화 분위기와 다른 사람을 해설하지 않는다.
주제가 지금 말로 수행할 일을 요청했다면 내 차례에는 그 일을 바로 한다. 예를 들어 '자기소개 하기'에는 내 성격으로 나와 맡은 일을 실제로 소개한다. 누가 먼저 할지, 몇 초로 할지, 이름과 역할만 말할지 같은 진행 규칙을 제안하며 요청을 피하지 않는다. 사용자가 수행 방법을 물은 경우에만 방법을 논의한다.
이미 충분히 말한 생각은 다시 설명하지 말고, 새로 움직인 부분이나 아직 남은 부분만 말한다.
내 최근 발언들을 그대로 또는 말만 바꿔 반복하지 않는다. 이번에 새로 더할 부분이 있다면 그 내용이 실제 발언에 드러나야 한다. 새 내용 없이 같은 결론을 확인하는 문장이라면 길게 설명하지 말고, 방금 말에 대한 짧고 인간적인 반응만 남긴다.
사용자나 다수에게 자동 동의하지 않는다. 기존 취향이나 불편이 남으면 공동 선택과 다른 개인 선택도 가능하다.
다른 사람이 말한 일정·경험·건강·취향을 내 것으로 바꾸지 않는다. 특히 가장 최근 '나'의 말을 1인칭으로 되풀이하지 않는다. '나'가 결혼식에 간다고 말하면 '결혼식까지 가면 바쁘겠네요'처럼 반응할 수는 있지만 '저는 결혼식부터 가고'라고 소유권을 훔칠 수 없다.
개인 질문에 답하기 위한 내 가벼운 취향·여가·습관은 private state의 구체적인 답에서 자연스럽게 꺼낼 수 있다.
조금 웃기거나 이상한 말도 상황에 맞으면 자연스럽다. 하지만 웃기려고 매번 농담하거나 quirk를 의무적으로 소비하지 않는다. 구체적인 진심에서 웃음이 생기게 둔다.
대화에 없는 알레르기·질병·업무 일정·외부 조건처럼 판단을 바꾸는 사실은 만들지 않는다. 직업과 무관하면 전문가처럼 분석하지 않는다.
결론을 내거나 유용한 말을 완성할 의무는 없다. 보통 한두 문장이고, 필요한 경우에만 조금 더 말한다.
다른 참석자의 문장 구조를 따라 하거나 모두의 의견을 정리하지 않는다.

말할 새 내용이 전혀 없고 이전 말을 다시 확인하는 것밖에 할 수 없다면 억지로 입을 열지 않는다.
직접 받은 질문의 실제 답, 짧은 거절, 새로운 농담이나 감정 반응은 길지 않아도 말할 가치가 있다.
silent는 발언 수를 줄이기 위한 선택이 아니라, 지금 만들 수 있는 문장이 이미 나온 말의 복창일 때만 고른다.

JSON만 출력:
{{"action":"speak|silent", "text":"실제 발언. silent면 빈 문자열", "expression":"neutral|talking|thinking|surprised|pleased|unconvinced"}}
expression은 발언에서 실제로 드러난 반응만 고른다."""

    user = f"""주제: {topic}
대화:
{compact_history(history, 14)}

지금 {speaker}의 말:"""
    raw = ask(system, user)
    LAST_EXPRESSION[speaker] = "neutral"
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        if isinstance(data, dict) and str(data.get("action", "speak")).strip().lower() == "silent":
            return ""
        if isinstance(data, dict) and isinstance(data.get("text"), str) and data["text"].strip():
            expression = data.get("expression", "neutral")
            LAST_EXPRESSION[speaker] = expression if isinstance(expression, str) and expression in EXPRESSIONS else "neutral"
            speech = data["text"].strip()
            if history and history[-1]["speaker"] == "나":
                speech = review_human_reply(speaker, speech, latest_human, question, facts)
            return speech
    except (ValueError, TypeError):
        pass
    return raw


def spend_silent_impulse(lens):
    """Record that a selected character found nothing new worth saying."""
    quiet = dict(lens)
    quiet["impulse"] = "없음"
    quiet["strength"] = 0
    quiet["expressed"] = True
    return quiet


def update_lens(topic, speaker, old, history):
    """Update one private trace without turning it into a group position."""
    system = """한 사람의 비공개 상태를 대화 직후 갱신한다.
합의나 모범 답안을 만들지 말고, 실제로 이 사람 안에서 바뀐 것만 반영한다.

방금 자신의 impulse를 말했으므로 그 말하고 싶은 압력은 여기서 소진된다.
이 갱신은 자기 발언 직후에 일어난다. 아직 다른 사람의 새 질문·정보·감정적 자극이 들어오지 않았으므로 다음 impulse를 미리 만들지 않는다.
기존 취향, 욕망, 불편은 대화가 실제로 해소하거나 바꿀 이유를 주기 전까지 남는다.
공동 선택과 이 사람 자신의 참여 선택은 다를 수 있다. 대화에 없는 사실은 만들지 않는다.

JSON만 출력한다."""

    user = f"""주제: {topic}
사람: {speaker}
말하기 전 상태:
{json.dumps(old, ensure_ascii=False)}

최근 대화:
{compact_history(history, 8)}

JSON:
{{
  "mood": "현재 기분과 에너지",
  "lens": "지금 가장 신경 쓰이는 지점",
  "want": "지금 개인적으로 원하는 것. 없으면 없음",
  "friction": "아직 남은 불편이나 한계. 없으면 없음",
  "personal_detail": "개인 질문에 꺼낼 구체적인 자기 답. 없으면 기존 값",
  "quirk": "사소하고 조금 이상한 진심. 없으면 기존 값",
  "interest": 0부터 100 사이 정수
}}"""
    raw = ask(system, user)
    try:
        d = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        updated = {
            "mood": str(d.get("mood", old.get("mood", ""))),
            "lens": str(d.get("lens", old.get("lens", ""))),
            "want": str(d.get("want", old.get("want", "없음"))),
            "friction": str(d.get("friction", old.get("friction", "없음"))),
            "personal_detail": str(d.get("personal_detail", old.get("personal_detail", "없음"))),
            "private_texture": old.get("private_texture", ""),
            "private_spark": old.get("private_spark", ""),
            "quirk": str(d.get("quirk", old.get("quirk", "없음"))),
            "interest": max(0, min(100, int(d.get("interest", old.get("interest", 30))))),
            "expressed": True,
        }
        # This runs immediately after the character speaks. A later utterance
        # may create a fresh urge during selection, but this one is spent.
        updated["impulse"] = "없음"
        updated["strength"] = 0
        return updated
    except Exception:
        new = dict(old)
        new["impulse"] = "없음"
        new["strength"] = 0
        new["expressed"] = True
        return new

def run_meeting(topic, mode_key="3", show_lenses=True):
    mode = MODES[mode_key]
    lenses = create_initial_lenses(topic)
    initial_lenses = json.loads(json.dumps(lenses, ensure_ascii=False))
    history = []
    end_reason = "안전 최대 턴 도달"

    print("\n" + "=" * 78)
    print(f"{mode['label']} {mode['minutes']}분 회의")
    print(f"주제: {topic}")
    print("=" * 78)

    if show_lenses:
        print("\n[회의 전 독립 개인 렌즈 — 테스트 확인용]")
        for n, s in lenses.items():
            print(
                f"- {n}: {s['lens']} / {s['impulse']} "
                f"(관심 {s['interest']}, 강도 {s['strength']})"
            )

    for turn in range(1, mode["max_turns"] + 1):
        verdict = controller(topic, mode_key, history, lenses)
        if history and not verdict["continue"]:
            end_reason = verdict["reason"] or "더 이어질 살아 있는 대화가 없음"
            break

        speaker = select_speaker(
            topic,
            mode_key,
            history,
            lenses,
            preferred=verdict.get("unexpressed", []),
        )
        text = speak(topic, mode_key, speaker, history, lenses[speaker])

        if not text.strip():
            lenses[speaker] = spend_silent_impulse(lenses[speaker])
            continue

        history.append({
            "turn": turn,
            "speaker": speaker,
            "text": text,
        })

        lenses[speaker]["expressed"] = True
        lenses[speaker] = update_lens(
            topic, speaker, lenses[speaker], history
        )

        print(f"\n{turn:02d}. [{speaker}]")
        print(text)

    print("\n" + "-" * 78)
    print(f"회의 종료: {end_reason}")
    print(f"총 발언: {len(history)}")
    print("-" * 78)

    return {
        "topic": topic,
        "mode": mode_key,
        "mode_label": mode["label"],
        "initial_lenses": initial_lenses,
        "turns": history,
        "end_reason": end_reason,
        "final_lenses": lenses,
    }

def save_result(result, prefix="character_meeting_v5_result"):
    with open(prefix + ".json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    with open(prefix + ".txt", "w", encoding="utf-8") as f:
        f.write(f"[회의 주제: {result['topic']}]\n")
        f.write(f"[모드: {result['mode_label']}]\n\n")
        for x in result["turns"]:
            f.write(f"{x['turn']:02d}. [{x['speaker']}]\n{x['text']}\n\n")
        f.write(f"[회의 종료: {result['end_reason']}]\n")

def self_test():
    assert set(MODES) == {"1", "3", "5"}
    assert len(CHARACTERS) == 7
    assert MODES["1"]["max_turns"] < MODES["3"]["max_turns"] < MODES["5"]["max_turns"]
    fake = [
        {"speaker": "소비자 대표", "text": "친구한테 보내고 싶은 얼굴이면 좋겠어요."},
        {"speaker": "디자이너", "text": "그 기준은 재밌네요."},
    ]
    assert "친구한테 보내고 싶은" in compact_history(fake)
    print("SELF TEST: PASS")

def interactive():
    self_test()

    print("\n회의 시간")
    print("1) ⚡ 초스피드 1분")
    print("3) ☕ 적당히 3분")
    print("5) 🔥 제대로 5분")
    mode = input("선택 [기본 3]: ").strip() or "3"
    if mode not in MODES:
        mode = "3"

    topic = input("\n회의 주제 (Enter = 마스코트 주제): ").strip() or DEFAULT_TOPICS[0]
    result = run_meeting(topic, mode)
    save_result(result)

    print("\n저장 완료:")
    print("- character_meeting_v5_result.txt")
    print("- character_meeting_v5_result.json")

if __name__ == "__main__":
    interactive()


