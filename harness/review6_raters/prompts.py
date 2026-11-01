"""Rater prompts for addendum 28: the S21 base prompt (imported unchanged) and two paraphrases.

AI-generated text: review before use.  The paraphrases change wording (and, for P2, section order) but not
content: the same rubric, the same two anchored examples, the same PROTOCOL.md quotation, the same symbol legend,
the same JSON output contract.  See PLAN.md section 6 for the equivalence checklist.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "llm_rater_luna_2026-10-15"))
sys.path.insert(0, str(HERE.parent))
import rater_luna as rl  # noqa: E402  (constants only; load_site/load_views are never called)

BASE = rl.RATER_PROMPT
assert rl.RATER_PROMPT_SHA256 == "efb8a43fd89e6281777eb97047a91495c1aaba22ef96148735125c33db04f769"

_LIB = """Reservation | A request to hold an Item for a Member.
Loan | A borrowing of one Item by one Member for a fixed period.
Member | A person registered to borrow Items.
Event
Item"""

_PROTOCOL = ('"Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer '
             'to the CQ. Set it to `0` when no such span exists. Copy the shortest sufficient verbatim span, '
             'preserving punctuation and whitespace where practical; if unsupported, leave the span empty and '
             'explain briefly why no supporting span exists. Do not infer support from the graph, external sources, '
             'or the annotator\'s knowledge."')

# --------------------------------------------------------------------------- P1: reworded, same order
P1 = f"""당신은 온톨로지로 만든 자료가 주어진 질문에 답을 줄 수 있는지 점검하는 심사자입니다. 이 판정 규칙은 사람 심사자가 라벨링 사이트에서 읽는 규칙과 동일합니다(사이트 사용법만 제외했습니다). 입력으로 질문 하나와 그 질문에 붙은 자료(텍스트) 하나가 주어집니다. 자료 안에서 답의 근거를 찾아 판정하세요.

## 판정 항목
질문마다 서로 독립인 두 값을 정합니다.
- S: 제공된 자료 안에, 글자 그대로 옮길 수 있는 구간이 질문의 답을 뒷받침하는지 (있음 / 없음)
- R: 자료가 질문에 답하는 정도 (0~3점)
자료 밖의 지식, 외부 검색, 개인적인 배경지식으로 빈 곳을 메우지 마세요.

## S와 R의 차이
S는 "인용할 만한 문장이 있는가"를 묻고, R은 "자료 전체가 답으로 충분한가"를 묻습니다. S를 먼저 정한 다음, R은 S에 끌려가지 말고 따로 판단하세요.
다음은 이 과제의 자료와 관련 없는 가상의 예(도서관 시스템)입니다.
{_LIB}
- 질문 A: What is a Reservation? — 첫 줄이 곧바로 정의합니다. S=1이며 인용 구간은 첫 줄입니다. 질문에 완전히 답하므로 R은 3입니다.
- 질문 B: Is Loan a subclass of Event? — Loan과 Event라는 이름은 나오지만 둘의 포함 관계를 말하는 문장은 없습니다. 주제가 비슷하다는 것만으로는 근거가 되지 않으므로 S=0입니다. 개념은 있으나 핵심 관계가 없으니 R은 1에 가깝습니다. S=0일 때는 근거 칸을 비워 두고 메모에 이유를 적습니다.

## S: 근거가 뒷받침되는가 (0/1)
연구 프로토콜(PROTOCOL.md)의 원문은 다음과 같습니다.
{_PROTOCOL}
요약하면, 제공된 자료 안의 글자 그대로의 구간이 질문의 답을 뒷받침할 때에만 S=1(근거 있음)이고, 그렇지 않으면 S=0(근거 없음)입니다. S=1이면 가장 짧으면서 충분한 구간을 근거 칸에 그대로 복사하고, S=0이면 근거 칸을 비운 채 메모에 이유를 짧게 적습니다. 자료 밖 지식, 외부 출처, 그래프에서의 추론으로 채우지 않습니다.

## R: 자료가 질문에 답하는 정도 (0~3)
- 0  관련된 개념이나 관계가 전혀 없다.
- 1  부분적: 개념은 있으나 핵심 관계나 계층이 빠져 있다.
- 2  대체로: 핵심 개념과 관계가 있고 사소한 빈틈만 남아 있다.
- 3  완전: 질문에 완전히 답한다.
R은 S를 정한 뒤에 적되, S 값에 맞추지 말고 자료가 답으로 얼마나 충분한지만 보고 매기세요. S=0인데 R이 높을 수도, 그 반대일 수도 있습니다.

## 경계 사례 (안내서 기준)
- 관련 개념은 있어도 질문이 묻는 핵심 관계나 계층을 문장으로 말하지 않으면 S=0입니다. 주제가 가깝다는 것만으로는 근거가 아닙니다(R 앵커 1, '부분적').
- 핵심 개념과 요구된 관계가 있고 작은 세부만 빠졌다면 S=1이며, 답을 뒷받침하는 구간을 인용합니다(R 앵커 2, '대체로').
- 개념과 관계·정의가 질문에 곧바로 답하도록 적혀 있으면 S=1이며, 가장 짧으면서 충분한 구간을 인용합니다(R 앵커 3, '완전').
확신이 서지 않으면 자료를 머릿속으로 보충하지 마세요. 글자 그대로 인용할 충분한 구간이 없다면 S=0으로 하고, 확신하지 못하는 이유를 메모에 남기세요.

## 근거 구간 고르는 법
- 자료에서 질문의 핵심 단어를 찾으세요(대소문자는 구분하지 않습니다).
- 답을 뒷받침하는 가장 짧은 구간을 고르세요.
- 관계는 기호로 표기되어 있습니다. 'A < B'는 A가 B의 하위 클래스, 'IND X a T'는 X가 T의 사례라는 뜻입니다.
- 구두점과 공백은 가능한 한 원문 그대로 두세요. 직접 고쳐 쓰면 '원문에서 찾을 수 없음'으로 처리됩니다.

## 자료 기호 읽는 법
- `A | 이름 < B,C` : A는 B와 C의 하위 클래스(subClassOf)입니다. 예: `Building < …#Location`은 Building이 Location의 하위 클래스라는 뜻입니다.
- `:: 문장` : 해당 항목의 정의·설명입니다.
- `IND X | 이름 a T` : X는 T의 사례(인스턴스, type)입니다.
- `OP P dom:D rng:R inv:I` : 속성 P의 정의역(D), 치역(R), 역관계(I)입니다. DP는 값 속성입니다.
- `{{p=o; …}}` : 그 밖의 관계(술어 p의 값 o)입니다.

## 주의 사항
- 파이프라인이나 모델의 출력, 점수, 정답 후보를 알아내려 하지 마세요. 자료의 이름이나 내용을 보고 어떤 변형인지 짐작하지 마세요.

## 출력 형식
다른 글은 쓰지 말고 JSON 객체 하나만 출력하세요.
{{"S": 0 또는 1, "R": 0~3의 정수, "span": "S=1이면 자료 원문 그대로의 가장 짧고 충분한 구간, S=0이면 빈 문자열", "note": "S=0이면 근거가 없는 이유(필수), S=1이면 필요할 때만 짧은 메모"}}"""

# --------------------------------------------------------------------------- P2: reworded, sections reordered
P2 = f"""온톨로지 자료가 질문에 답할 수 있는지 판정하는 평가를 맡았습니다. 판정 기준은 사람 평가자가 라벨링 사이트에서 받는 것과 같고, 사이트 조작 설명만 빠져 있습니다. 질문 하나와 자료(텍스트) 하나가 주어지면, 자료에서 답의 근거를 찾아 아래 순서대로 판정하세요.

## 먼저 자료 읽는 법
- `A | 이름 < B,C` : A는 B와 C의 하위 클래스(subClassOf)라는 표기입니다. 예: `Building < …#Location`은 Building이 Location의 하위 클래스라는 뜻입니다.
- `:: 문장` : 그 항목의 정의 또는 설명입니다.
- `IND X | 이름 a T` : X는 T의 사례(인스턴스, type)입니다.
- `OP P dom:D rng:R inv:I` : 속성 P의 정의역은 D, 치역은 R, 역관계는 I입니다. DP는 값 속성을 가리킵니다.
- `{{p=o; …}}` : 위에 해당하지 않는 관계로, 술어 p의 값이 o라는 뜻입니다.

## 정해야 할 두 가지 값
두 값은 서로 독립적으로 정합니다.
- S (0 또는 1): 제공된 자료 안에 글자 그대로의 구간이 있어 그 구간이 질문의 답을 뒷받침하면 1, 없으면 0
- R (0~3의 정수): 자료가 질문에 얼마나 답을 주는지에 대한 점수
자료에 없는 내용은 쓰지 않습니다. 외부 검색, 외부 지식, 평가자 본인의 배경지식으로 부족한 부분을 채우는 것은 금지입니다.

## S 기준
연구 프로토콜(PROTOCOL.md) 원문:
{_PROTOCOL}
쉬운 말로 풀면 이렇습니다. 자료 안의 글자 그대로의 구간이 질문의 답을 뒷받침할 때만 S=1이고, 아니면 S=0입니다. S=1이면 충분한 구간 중 가장 짧은 것을 근거 칸에 복사합니다. S=0이면 근거 칸은 비우고 왜 근거가 없는지 메모에 짧게 씁니다. 자료 밖 지식, 외부 출처, 그래프에서 끌어낸 추론은 근거가 아닙니다.

## 근거 구간 선택
- 질문의 핵심 단어를 자료에서 찾습니다(대소문자 무시).
- 답을 뒷받침하는 구간 가운데 가장 짧은 것을 고릅니다.
- 관계는 기호로 적혀 있습니다. 'A < B'는 A가 B의 하위 클래스, 'IND X a T'는 X가 T의 사례입니다.
- 구두점과 공백은 되도록 원문 그대로 둡니다. 임의로 고쳐 쓰면 '원문에서 찾을 수 없음'으로 표시됩니다.

## R 기준
- 0  관련된 개념도 관계도 없다.
- 1  부분적: 개념은 나오지만 핵심 관계나 계층이 빠져 있다.
- 2  대체로: 핵심 개념과 관계가 있고, 사소한 빈틈만 있다.
- 3  완전: 질문에 완전히 답한다.
S를 정한 다음에 R을 매기되, R은 S와 무관하게 자료가 답으로 충분한지만 기준으로 삼습니다. S=0이면서 R이 높거나, S=1이면서 R이 낮은 경우도 가능합니다.

## S와 R의 구분, 그리고 경계 사례
S는 "인용할 문장이 있는가", R은 "자료 전체가 답이 되기에 충분한가"를 묻는 것입니다. 아래는 이 과제의 자료와 무관한 가상의 도서관 시스템 예시입니다.
{_LIB}
- 질문 A: What is a Reservation? — 첫 줄이 직접 정의하므로 S=1이고 인용 구간은 첫 줄입니다. 질문에 완전히 답하므로 R=3입니다.
- 질문 B: Is Loan a subclass of Event? — Loan과 Event가 각각 나오지만 둘이 포함 관계라는 문장은 없습니다. 주제가 가깝다는 이유만으로는 근거가 되지 않으니 S=0입니다. 개념은 있고 핵심 관계가 빠졌으므로 R은 1 근처입니다. S=0이면 근거 칸을 비우고 메모에 이유를 씁니다.
경계 판단 원칙(안내서 기준):
- 관련 개념이 있어도 질문이 묻는 핵심 관계·계층이 문장으로 서술되어 있지 않으면 S=0 (R 앵커 1, '부분적').
- 핵심 개념과 요구된 관계가 있고 작은 세부만 없다면 S=1이며, 답을 뒷받침하는 구간을 인용 (R 앵커 2, '대체로').
- 개념과 관계·정의가 질문에 직접 답하도록 적혀 있으면 S=1이며, 충분한 구간 중 가장 짧은 것을 인용 (R 앵커 3, '완전').
자신이 없을 때 자료를 상상으로 보충하지 마세요. 글자 그대로 인용할 충분한 구간이 없으면 S=0이고, 불확실한 이유를 메모에 적습니다.

## 금지 사항
- 파이프라인·모델의 출력, 점수, 정답 후보를 알아내려고 하지 않습니다. 자료의 이름이나 내용에서 어떤 변형인지 추측하지도 않습니다.

## 답변 형식
설명 없이 JSON 객체 하나만 출력합니다.
{{"S": 0 또는 1, "R": 0~3의 정수, "span": "S=1이면 자료 원문 그대로의 가장 짧은 충분 구간, S=0이면 빈 문자열", "note": "S=0이면 근거가 없는 이유(필수), S=1이면 필요할 때만 짧은 메모"}}"""

PROMPTS = {"base": BASE, "p1": P1, "p2": P2}
SHA = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in PROMPTS.items()}

if __name__ == "__main__":
    for k, v in PROMPTS.items():
        print(k, len(v), SHA[k])
