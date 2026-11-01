"""Persona preambles of addendum 30 (review10_llm_labels).

AI-generated text: review before use.  Each persona is a short role preamble put IN FRONT of the identical criteria text
(the S21 rater prompt of review6_raters, imported unchanged).  The criteria wording is not altered for any persona:
system prompt = PREAMBLE[persona] + "\\n\\n" + BASE.  The preambles are quoted verbatim in PLAN.md; test_ensemble.py
checks that the strings here occur in PLAN.md.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS / "review6_raters"))
import prompts as P6  # noqa: E402  (asserts the S21 prompt sha256)

BASE = P6.BASE
BASE_SHA256 = hashlib.sha256(BASE.encode("utf-8")).hexdigest()

_TAIL = "판정 기준과 출력 형식은 아래 지침이 전부이며 모든 역할에 똑같이 적용됩니다. 역할 때문에 기준을 바꾸지 마세요."

PREAMBLE = {
    "domain": ("[역할] 당신은 Brick 스키마와 건물 시스템(공조, 센서, 계량, 공간 구조 등)을 잘 아는 도메인 엔지니어입니다. "
               "이 역할의 눈으로 자료를 읽고 아래 평가를 수행합니다. " + _TAIL),
    "ontology": ("[역할] 당신은 OWL/RDFS 온톨로지를 설계하고 검증하는 온톨로지 엔지니어입니다. "
                 "클래스, 속성, 정의, 계층이 자료에 어떻게 적혀 있는지 살펴보며 아래 평가를 수행합니다. " + _TAIL),
    "auditor": ("[역할] 당신은 엄격한 근거 감사자입니다. 자료에 명시적으로 적힌 구간만 근거로 인정하고, "
                "암시되거나 짐작되는 내용은 인정하지 않는 태도로 아래 평가를 수행합니다. " + _TAIL),
    "kgqa": ("[역할] 당신은 지식 그래프 기반 질의응답(QA) 시스템의 테스터입니다. 질문을 사용자가 실제로 던진 질의로 보고, "
             "이 자료만으로 답을 낼 수 있는지 확인하는 태도로 아래 평가를 수행합니다. " + _TAIL),
    "generalist": ("[역할] 당신은 도메인 전문 지식 없이 지침을 꼼꼼히 따르는 신중한 일반 어노테이터입니다. "
                   "지침에 적힌 대로만 읽고 판단하는 태도로 아래 평가를 수행합니다. " + _TAIL),
}
PERSONAS = list(PREAMBLE)            # fixed order: domain, ontology, auditor, kgqa, generalist
assert PERSONAS == ["domain", "ontology", "auditor", "kgqa", "generalist"]

SYSTEM = {p: PREAMBLE[p] + "\n\n" + BASE for p in PERSONAS}
PREAMBLE_SHA256 = {p: hashlib.sha256(PREAMBLE[p].encode("utf-8")).hexdigest() for p in PERSONAS}
SYSTEM_SHA256 = {p: hashlib.sha256(SYSTEM[p].encode("utf-8")).hexdigest() for p in PERSONAS}

if __name__ == "__main__":
    print("BASE", len(BASE), BASE_SHA256)
    for p in PERSONAS:
        print(p, len(PREAMBLE[p]), PREAMBLE_SHA256[p])
