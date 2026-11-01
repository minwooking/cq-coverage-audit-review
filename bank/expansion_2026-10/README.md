# 질문 은행 확장 초안 (2026-10) — AI 생성, 미동결

이 디렉터리는 AI가 만든 **초안**이다. 저자가 검토·수정·동결하기 전에는 judge 호출에 쓰지 않는다. 판정 호출은 한 번도 하지 않았다. 원고와 기존 은행(`../cq_bank_brick_v1.csv`, `v2.csv`)은 건드리지 않았다. 도구와 데이터는 사람이 검토·테스트하기 전에 적용하지 않는다.

## 파일
| 파일 | 내용 |
|---|---|
| `cq_bank_brick_expansion_draft_v1.csv` | 84문항(6범주 x 14). 첫 줄은 `#` 주석 헤더(동결 시 삭제). 기존 열 10개 + `author_review`(전 행 `pending`) + 스크린 열 |
| `ask_queries/CQX01.rq` .. `CQX84.rq` | 행별 SPARQL ASK (기존 `ask_queries/` 와 같은 PREFIX 머리말) |
| `build_and_screen.py` | 초안 생성과 3채널 스크린. 스냅샷에서 정의·자식·교체 정보를 읽어 `expected_answer`와 ASK를 만든다 |
| `screen_results.json` | 스크린 요약 |

## 작성 방식 (artifact-blind)
읽은 것은 `data/brick-v1.4.4.ttl`(sha256 `b65720b7...`, 실행 때 일치 확인)과 기존 은행의 질문·grounding 텍스트(중복 검사용)뿐이다. `variants/`, 그래프, rendered view, 판정 셀, 라벨, 길이 실험 입력은 열지 않았다.

## 스크린 열
`screen_format`, `screen_grounding`, `screen_ask`: 3채널(형식 / grounding 항이 스냅샷에 존재하고 정의 주장에 비어 있지 않은 리터럴이 있음 / ASK true). `anchor_rule_check`: `run_holdout._grounding_anchors`가 grounding 문자열에서 뽑는 앵커가 모두 스냅샷의 이름인지(규칙 수준 확인, 산출물 비열람). `eligibility_anchors`: 그 앵커 목록. `screen_dup`: 의미 중복 점검(REVIEW는 저자가 볼 것). `screen_fail`: FAIL / REVIEW / ok.

## 저자 검토 체크리스트
1. 질문이 자연스럽고 모호하지 않은가. 기대 답이 스냅샷 문구와 일치하는가(스크린은 존재와 ASK만 본다).
2. `screen_dup=REVIEW` 4행(CQX19 rec:Zone 자식, CQX23 rec:Level 상위, CQX28 Parameter/Status 비교, CQX43 area): 기계 휴리스틱이 지역명 토큰("zone", "level", "parameter", "area")으로 올린 것이며 기존 문항과 사실이 다르다고 판단했다. 최종 판단은 저자.
3. 변형 패턴 반복: 방법론 6행(CQX71-76)은 폐기·교체 기록을 묻는 같은 틀이고(기존 CQB59와 같은 틀, 다른 항), 관계 6행은 SHACL 속성 형상(rec: Agent 계열)이다. 한 틀이 너무 많다고 보면 줄인다.
4. 동결 목표는 78문항(범주당 13). 초안 84는 삭제 여유 6이다. 삭제는 범주 균형을 지키며 한다.
5. 동결 후: `#` 헤더 줄 삭제 → 해시 기록 → annotated tag → 이후 수정 금지. `cq_id`는 `CQX`로 시작해 기존 `CQB01-60`과 겹치지 않는다.

## 알려진 한계
- 3채널은 "존재"와 "ASK true"만 본다. 질문의 질, 난이도, 정답의 단일성은 기계가 보증하지 않는다.
- ASK 채널의 `partial` 49행은 정의 문구를 ASK로 완전히 검증하지 못한다(예시 구절 포함 여부까지만).
- 변형 A 적격성은 산출물에 의존하므로 이 초안은 판정하지 않는다(부록 20.5).
