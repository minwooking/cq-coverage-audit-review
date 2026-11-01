# 실험 3 (렌더링 길이) 결과 보고 — judge gpt-5.6-luna (addendum 17, 이탈 D28)

원고(main.tex)는 수정하지 않았다. 이 보고서와 아래 초안은 사람이 검토하기 전에는 결과로 쓰지 않는다. 숫자는 `results_length.json`(확인함)에서 왔다.

## 실행
- judge `gpt-5.6-luna`(<internal-proxy> 로컬 프록시), temperature 0, max_tokens 1024, response_format text 덮어쓰기 + json.loads 파싱. 설계 reduced(393호출), workers 3, 시드 20260913.
- 호출 393, 무효 3(0.8%: 502 업스트림 1, 응답 파싱 불가 2 — `cells_length.jsonl`에 `judge_response_parsed=false`로 남김, 재시도하지 않음; 모두 subgraph 조건). 추정 입력 토큰 6,264,381(문자/4 추정, 상한 7,000,000), 소요 553초.
- astra 부분 결과(`cells_length_astra_partial.jsonl`, 유효 113셀)와 실패 기록은 보존했고 분석에 쓰지 않았다.

## 조건별 J 분포 (유효 셀)
| 조건 | n | J=0 | J=1 | J=2 | J=3 | 평균 |
|---|---|---|---|---|---|---|
| full (A만) | 23 | 0 | 4 | 0 | 19 | 2.65 |
| limited (A–F) | 188 | 81 | 88 | 8 | 11 | 0.73 |
| subgraph (A–F) | 179 | 10 | 72 | 17 | 80 | 1.93 |

variant별 평균 J: limited A 1.35, B 0.76, C 0.67, D 0.70, E 0.52, F 0.58; subgraph A 2.23, B 2.03, C 1.87, D 1.88, E 1.91, F 1.77. subgraph 적용불가 입력 6(제외).

## 조건 간 차이 (같은 (variant, CQ) 셀; 평균 차이, CQ-cluster BCa 95%)
| 대조 | 쌍 | 평균 차이 | 95% 구간 | 정확 일치 | QWK |
|---|---|---|---|---|---|
| full − limited (A) | 23 | +1.30 | [0.87, 1.74] | 0.35 | 0.21 |
| full − subgraph (A) | 22 | +0.41 | [0.14, 0.95] | 0.86 | 0.42 |
| limited − subgraph (A–F) | 179 | −1.21 | [−1.49, −0.83] | 0.31 | 0.03 |

## 판정 오류 대 정보 부족 (full J≥2 → reduced J≤1; 후보, 원인 확정 아님)
| reduced | full J≥2 쌍 | judge_error_candidate (근거가 입력에 있음) | information_deficit (입력에 근거 없음) | reduced_up |
|---|---|---|---|---|
| subgraph | 18 | 0 | 3 | 0 |
| limited | 19 | 8 | 4 | 0 |

## 해석 (기술 서술, 17.6 규칙)
- 이 judge에서 60,000자로 자른 limited 입력은 같은 그래프의 full(A)보다 평균 1.30 낮다. 구간은 0을 포함하지 않는다. 그러나 limited는 IRI 정렬 앞부분이라 질문과 무관한 prefix이므로, 이 하락 중 얼마가 "긴 입력의 judge 오류"이고 얼마가 "근거가 잘려 나간 정보 부족"인지는 이 표만으로 가를 수 없다. 분리 표에서 limited의 하락 12쌍 중 8쌍은 근거 문자열이 입력에 있었는데도 J≤1이었다(judge_error_candidate, 문자열 일치 휴리스틱).
- 반대로 질문 관련 subgraph는 full(A)보다 평균 0.41만 낮고(구간 [0.14, 0.95]), 정확 일치 0.86이다. 하락 3쌍은 모두 입력에 근거가 없는 정보 부족 후보다. 짧고 관련 있는 입력에서는 judge가 full(A)과 거의 같은 점수를 준다.
- limited와 subgraph의 차이(−1.21, [−1.49, −0.83])는 variant B–F에서도 같은 방향이다. B–F의 full 조건은 컨텍스트 문제로 판정하지 않았으므로 B–F에서 full과의 직접 비교는 없다.
- 이 결과는 "긴 입력에서 judge가 점수를 낮춘다"의 확증이 아니다. 같은 셀의 조건 간 이동의 크기와 구간이며, 원고 문장은 구간이 허락하는 범위로만 쓴다.

## 한계
- judge가 대체 모델(gpt-5.6-luna)이라 기존 holdout(등록 judge)의 J와 직접 비교할 수 없다. 조건 간 차이는 이 judge 안에서만 읽는다.
- full 조건은 variant A(29만 자)만 판정했다. A의 full 뷰는 B–F와 렌더러 출력 길이가 달라(약 29만 대 195만–241만 자) A의 결과를 B–F로 일반화할 수 없다.
- 무효 3셀은 subgraph 조건에서 빠졌다(분모 182 중 179). 무효 응답 중 2건은 evidence 문자열이 길어 1024토큰 안에서 JSON이 닫히지 않은 것으로 보이나(추정) 확인하지 않았다.
- grounding 일치는 문자열 휴리스틱이다.

## 원고 삽입용 초안 (영어, 원고에 넣지 말 것)

To separate judge error from missing evidence, we re-scored the same graphs under three input conditions with a substitute judge (gpt-5.6-luna; the registered judge was not reachable, see deviation D28), holding the question, rubric, and decoding fixed. On the 23 variant-A cells, truncating the rendered view to its first 60,000 characters lowered the mean score from 2.65 to 1.30 (mean paired difference 1.30, cluster-BCa 95% interval 0.87 to 1.74), whereas a question-relevant subgraph lowered it only to 2.23 (difference 0.41, interval 0.14 to 0.95; 86% exact agreement). Across all six variants, the truncated prefix scored 1.21 points below the subgraph (interval 0.83 to 1.49). Among full-view pairs scored J>=2 that fell to J<=1 under truncation, 8 of 12 contained the grounding terms in the input, which we report as judge-error candidates only, because the match is a string heuristic. Full views were scored for variant A only, and the judge differs from the registered one, so these differences are not comparable to the main holdout scores.

| Condition | n | J=0 | J=1 | J=2 | J=3 | Mean J |
|---|---|---|---|---|---|---|
| Full (A only) | 23 | 0 | 4 | 0 | 19 | 2.65 |
| Truncated (60k chars) | 188 | 81 | 88 | 8 | 11 | 0.73 |
| Subgraph | 179 | 10 | 72 | 17 | 80 | 1.93 |

(tab:lengthexp 초안.) 삽입 위치 제안: 한계/타당성 절에서 "judge가 긴 입력에서 점수를 낮추는가"를 다루는 문단 바로 뒤, 또는 부록의 judge 타당성 부분. 본문에는 문단만, 표는 부록을 권한다.
