# Layer-1 Scoring Rubric

## Score anchors

**Provenance:** `main.tex`, lines 479–482.

Given an artifact $G$ and a question $q$, the Layer-1 judge assigns an
answerability score $L_1(G,q)\in\{0,1,2,3\}$: $0$, no related concept or
relation; $1$, partial---concepts present, key relation or hierarchy missing;
$2$, mostly---core concept and relation present, minor gaps; $3$, complete.

## Evidence-anchored adjudication

**Provenance:** `PREREG.md`, lines 55–60.

> **L₁\*(v,q) = J(v,q)           if A(v,q) = 1**
> **L₁\*(v,q) = min{ J(v,q), 1 } if A(v,q) = 0**

**단측(one-sided) by construction**: 근거 span이 없는 점수를 **낮출 수는 있어도 올릴 수는 없다.**

## Notation mapping

`J(v,q)` is the raw judge Layer-1 score in `PREREG.md`; `L₁*(v,q)` is the post-adjudication demoted score. The manuscript writes the raw score as `L₁(G,q)`.
