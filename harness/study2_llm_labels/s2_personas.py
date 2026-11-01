"""Personas and the new labeling instruction text (NEW_BASE) of addendum 32 (Study 2).

AI-generated text: review before use.  The five persona preambles are those of addendum 30 (imported byte for byte from
review10_llm_labels/personas.py by path, so that no module name collides).  NEW_BASE = BASE (the S21 criteria text of
addenda 28/30, sha256 asserted) with exactly two insertions (PLAN.md 32.5); nothing else changes.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent

_spec = importlib.util.spec_from_file_location("r10_personas", HARNESS / "review10_llm_labels" / "personas.py")
R10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R10)

BASE = R10.BASE
assert hashlib.sha256(BASE.encode("utf-8")).hexdigest() == "efb8a43fd89e6281777eb97047a91495c1aaba22ef96148735125c33db04f769"
PERSONAS = list(R10.PERSONAS)
PREAMBLE = dict(R10.PREAMBLE)

ANCHOR_1 = "질문 하나와 그 질문에 딸린 자료(텍스트) 하나를 받습니다."
INSERT_1 = (" 이 자료는 전체 자료에서 질문과 관련된 부분만 발췌한 것입니다. 발췌와 발췌 사이는 `[…]` 한 줄로 구분하고, "
            "아주 긴 줄은 중간이 잘려 있을 수 있습니다. 발췌에 없는 부분은 읽을 수 없으므로 판정에 쓰지 마세요.")
ANCHOR_2 = "S=0인데 R이 높거나 그 반대도 가능합니다."
INSERT_2 = (" R에는 하한이 없습니다. 발췌 안에 질문과 관련된 개념이나 관계가 전혀 없으면 R=0으로 적고, "
            "S 값 때문에 R을 1 이상으로 올리지 마세요.")

assert BASE.count(ANCHOR_1) == 1 and BASE.count(ANCHOR_2) == 1
NEW_BASE = BASE.replace(ANCHOR_1, ANCHOR_1 + INSERT_1).replace(ANCHOR_2, ANCHOR_2 + INSERT_2)
assert len(NEW_BASE) == len(BASE) + len(INSERT_1) + len(INSERT_2)
NEW_BASE_SHA256 = hashlib.sha256(NEW_BASE.encode("utf-8")).hexdigest()
SYSTEM = {p: PREAMBLE[p] + "\n\n" + NEW_BASE for p in PERSONAS}
SYSTEM_SHA256 = {p: hashlib.sha256(SYSTEM[p].encode("utf-8")).hexdigest() for p in PERSONAS}

if __name__ == "__main__":
    print("NEW_BASE", len(NEW_BASE), NEW_BASE_SHA256)
