# PREREG addendum 25 — LLM-rater (luna) labels, subgraph view: 188개 주 셀 전체에 luna 라벨을 매기고, luna가 기존 사람 라벨과 맞는 정도가 사람끼리 맞는 정도와 비슷한지 본다 (탐색적, 사후)

> AI가 작성한 초안이다. 저자 검토 후 사용한다. 날짜: 2026-10-15. 이 파일만 단독 커밋으로 동결하고 annotated 태그 `access2026-addendum25-freeze`를 붙인다. luna 호출은 이 커밋 뒤에만 한다(동결 전 네트워크 호출 0회; 동결 전에는 토큰 추정과, luna 대신 독립 평가자 라벨을 넣은 가짜 입력으로 분석 코드의 오프라인 시험만 했다).

## 25.1 지위, 목적, 라벨원 이름

**탐색적(exploratory)이며 사후(post hoc)다.** 저자 결정(2026-10-15): luna 라벨을 쓰는 근거는 "luna가 기존 사람 라벨(AH, 독립 평가자)과 맞는 정도가 두 사람이 서로 맞는 정도와 비슷하다"는 것이며, 이 addendum은 정확히 그것을 188셀에서 검정한다. 확증 가설, 다중성 보정은 없다. 아래 25.5의 "비슷함(comparable)" 규칙은 결과를 보기 전에 정한 기술적 판정 규칙이다.

라벨원 이름: **"LLM-rater (luna) labels, subgraph view"**. 사람 라벨이 아니며 독립적인 인간 기준(reference)이 아니다. 분석기 입력에서는 `label_source = "LLM, not human"`으로 넣는다. 원고(main.tex, main_ko.tex, supplement.tex)는 이 addendum에서 수정하지 않는다.

이 세션과 요청자는 AH 라벨, 독립 평가자 라벨(v3), 그 결과(π̂, 게이트), 사람 다중 평가자 12개 라벨, 그리고 addendum 24의 전체 보기(full view) luna 파일럿 12셀 결과를 이미 안다. 부분그래프(subgraph) 보기의 luna 라벨만 "보기 전"이다.

## 25.2 평가자 지시문과 눈가림 — addendum 24와 같음

- 시스템 메시지: addendum 24.8의 `RATER_PROMPT` 그대로(UTF-8 sha256 `efb8a43fd89e6281777eb97047a91495c1aaba22ef96148735125c33db04f769`). 코드는 `harness/llm_rater_luna_2026-10-15/rater_luna.py`에서 가져오고 고치지 않는다. 실행 코드는 시작할 때 sha256을 대조해 다르면 멈춘다.
- 사용자 메시지 형식도 24와 같다(`rater_luna.user_message`): `자료:` + 자료 텍스트 + `범주:` + `질문:` + `참고 번역:`. 바뀌는 것은 **자료 텍스트**뿐이다(25.3).
- 주지 않는 것(24.2와 같음): judge 점수 J, judge 인용 구간, 변형 이름·파일 이름, AI 초안, AH 라벨, 독립 평가자 라벨, 사람 다중 평가자 라벨, 셀 id. 셀마다 독립 호출(대화 이력 없음).

## 25.3 자료(view) = 질문 관련 부분그래프

- 각 셀(변형 V × 질문 CQ)의 자료는 길이 실험(addendum 17·23)이 쓴 **바로 그 부분그래프 렌더링**이다: `harness/length_experiment/make_inputs.py`의 `build_subgraph_text`(`graph_view.ego_graph`, hop 2, 질문 텍스트의 토큰만으로 노드를 고름; 정답·grounding 열은 읽지 않음)가 만든 `harness/length_experiment/inputs/<V>/<CQ>/subgraph.txt`. 새로 만들지 않고 이미 있는 파일을 읽으며, 파일마다 sha256을 `harness/length_experiment/inputs/manifest.jsonl`(커밋됨)의 값과 대조한다(동결 전 확인: 210개 subgraph 파일 모두 일치).
- 사람 평가자 배포본(`views_for_raters.zip`)의 셀별 전체 보기가 manifest의 `full` sha256(즉 `harness/variants/<V>/rendered_view.txt`)과 같은지도 셀마다 확인한다(동결 전 확인: 188셀 모두 일치).
- **부분그래프가 없는 6셀**(길이 실험에서 `not_applicable`: 질문 토큰과 맞는 노드 0개 — A–CQB27, B–F의 CQB32): 이 셀은 부분그래프가 정의되지 않으므로 사람 평가자가 보는 **전체 보기**를 그대로 준다(`view_kind = full_view_fallback`). 이렇게 해서 188셀 모두에 라벨이 생긴다. 민감도 분석으로 부분그래프 182셀만의 일치도를 함께 보고한다(25.6).
- 각 기록에 `view_kind`(subgraph / full_view_fallback)와 자료 텍스트의 sha256을 남긴다.

## 25.4 호출 설정, 토큰 예산, 중단 규칙

- 모델 `gpt-5.6-luna`, <internal-proxy> 로컬 프록시 `http://<local-endpoint>/v1`(모델 공급은 <internal-proxy>만), temperature 0.0, `seed` 20260913(요청에 넣지만 업스트림이 지키는지는 보장되지 않음), `max_tokens` 2048, `response_format` `{"type":"text"}`. 파싱·유효성·재시도 규칙은 24.3과 같다(`rater_luna.call_rater`, `parse_content`).
- 동시 작업자 ≤ 3. 402·403이 한 번이라도 나오거나 Retry-After가 300초를 넘는 429가 나오면 새 호출을 멈추고 끝난 셀만 보존해 보고한다.
- 결과는 `harness/llm_rater_luna_2026-10-15/subgraph_r25/luna_rater_subgraph_raw.jsonl`에 셀별로 덧붙인다(재개 시 유효 셀은 건너뜀). 셀 id(`primary:<변형>:<CQ>`)로 중복을 제거하며 첫 유효 기록을 쓴다. 사이트 불투명 id는 저장하지 않는다.
- **추정 입력 토큰(문자/4, 지시문 포함): 4,853,188** = 부분그래프 182셀 1,900,605(셀당 1,687–18,063, 중앙값 10,724) + 전체 보기 6셀 2,952,583. 브리지(25.7)의 12셀은 이 188셀에 들어 있어 추가 호출이 없다(그 12셀의 부분그래프 추정 86,423).
- **토큰 예산 6,000,000 입력 토큰.** 코드는 (이미 쓴 토큰 + 남은 셀의 추정 토큰) > 6,000,000이면 호출하지 않는다. 실제 사용량은 응답의 `usage`로 기록해 보고한다.
- 무효 응답 셀은 같은 설정으로 재시도한다(재실행 시 자동). 188셀이 모두 유효하지 않으면 25.5–25.6은 계산하지 않고 완료 수를 보고한다.

## 25.5 주 분석 — "비슷함(comparable)" 규칙 (결과 보기 전에 정함)

188셀 전체에서 세 쌍의 일치도를 같은 방식으로 계산한다.
- **기준선:** AH 대 독립 평가자(v3). 이미 계산된 값: R 이차 가중 κ(QWK) 0.728 [0.567, 0.859], R 정확 일치율 0.718 [0.565, 0.841], S 일치율 0.830 [0.690, 0.925], S Cohen κ 0.595 [0.268, 0.833] (`results_llm_rater_luna.json`의 `baseline_188_AH_vs_IND`; 이번 분석에서 같은 코드로 다시 계산해 일치를 확인한다).
- **luna 쌍:** luna 대 AH, luna 대 독립 평가자.
- **지표(주 지표 4개):** R QWK(`analyze_holdout._qwk_from_values`), R 정확 일치율, S 일치율, S Cohen κ. R 1점 이내 일치율은 기술적으로만 함께 보고한다.
- **구간:** 질문(CQ) 군집 BCa 95% 구간, `analyze_holdout.cluster_bootstrap_stat`, B = 10,000, 시드 20260913 (`rater_luna.agreement_ci`; 군집 = CQ, 33개).
- **판정 규칙:** luna 쌍(luna–AH, luna–독립 평가자 각각)의 점추정값이 기준선(AH–독립 평가자)의 BCa 95% 구간 안에 있으면 그 지표에서 luna는 **"비슷함(comparable)"**, 밖에 있으면 **"비슷하지 않음"**이다. 지표별·쌍별로 따로 판정하며 종합 판정은 만들지 않는다. 구간보다 높아도 "비슷하지 않음"으로 기록하되 방향(높음/낮음)을 함께 적는다.
- **짝지은 차이:** 각 지표에서 (luna 쌍 값 − 기준선 쌍 값)을 같은 군집 재표본 위에서 계산한 BCa 95% 구간(B = 10,000, 시드 20260913)과 함께 보고한다. 이 구간은 기술적이며 판정 규칙을 바꾸지 않는다.

## 25.6 부가 분석 (기술적)

1. **민감도:** 부분그래프를 받은 182셀만으로 25.5의 세 쌍 일치도와 구간을 다시 계산한다(판정 규칙은 적용하지 않음).
2. **과대 크레딧과 게이트:** luna 라벨을 기준으로 π̂(J≥2 ∧ S=0)와 게이트 기록 G1–G8을 기존 분석기로 계산한다: `python3 harness/analyze_holdout.py harness/real_run/cells.jsonl --seed 20260913 --labels <luna 라벨 CSV>`(CSV의 `label_source` 열 = "LLM, not human", A = S, rater_L1 = R; 분석기 수정 없음, 같은 정의·코드). AH(`harness/real_run/results_human_pass/holdout_results_human.rater_safe.json`, π̂ 7.4%)와 독립 평가자(`annotation/second_pass_2026-10-13/v3/results_v3.json`, π̂ 13.8%)의 값과 나란히 보고한다. AH의 G4·G5는 washout까지 봉인 상태로 두고 열지 않는다.
3. 라벨 분포(S=1 개수, R 0–3 개수)를 세 라벨원에 대해 보고한다. S=1 셀의 근거 구간이 받은 자료 텍스트에 공백 정규화 후 그대로 있는 비율을 보고한다.

## 25.7 브리지와 새 사람 라벨 (기술적, n = 12)

- **브리지:** addendum 24 파일럿 12셀(전체 보기 luna 라벨, `luna_rater_raw.jsonl`)과 이번 부분그래프 luna 라벨을 같은 셀에서 비교한다: R 정확·1점 이내 일치율, R QWK, S 일치율, S κ, (S,R) 전이 횟수. 구간은 계산하지 않는다.
- **새 사람 라벨 12개:** 부분그래프 luna, 전체 보기 luna, AH, 독립 평가자 각각을 사람 라벨(H1–H3 합산, 셀당 1개)과 비교한다. 같은 지표, 구간 없음.
- 셀별 표(사람·AH 셀 라벨 포함)는 봉인 대상이므로 저장소 밖에만 쓴다.

## 25.8 산출물과 커밋

`harness/llm_rater_luna_2026-10-15/subgraph_r25/`에 `rater_luna_subgraph.py`(실행·분석), `luna_rater_subgraph_raw.jsonl`, `results_llm_rater_luna_subgraph.json`, `labels_for_analysis_luna_subgraph.csv`, `holdout_results_luna_subgraph.json`(분석기 요약 출력), `REPORT_ko.md`를 둔다. `views_for_raters.zip`, `site_key*.csv`, `labeling_sheet_key*.csv`, 사람 라벨 export, 봉인된 셀별 표(AH·사람 셀 라벨, 분석기 `--out-cells`)는 커밋하지 않는다.

## 25.9 한계

- luna 라벨은 독립적인 인간 기준이 아니다. 기준선 비교는 "사람 둘이 맞는 정도"와 나란히 놓는 기술적 비교일 뿐, luna가 사람을 대신할 수 있다는 확증이 아니다.
- holdout의 등록 judge는 gemini-3.6-flash이지만, luna는 길이 실험(addendum 17·23)의 대체 judge이기도 하다. judge 계열과 공유하는 편향이 있을 수 있다.
- 작업 조건이 다르다: luna는 질문 관련 부분그래프(6셀은 전체 보기)를 받았고, 사람 평가자는 전체 보기를 검색·그래프 탭과 함께 보았다. 부분그래프 밖에 있는 근거는 luna가 볼 수 없다.
- 판정 규칙(점추정이 기준선 구간 안)은 동등성 검정이 아니다. 기준선 구간이 넓어(특히 S κ) "비슷함"의 문턱이 느슨하다.
- 브리지·새 사람 라벨 비교는 n = 12로 작고, 파일럿 셀은 무작위 표본이 아니다.
