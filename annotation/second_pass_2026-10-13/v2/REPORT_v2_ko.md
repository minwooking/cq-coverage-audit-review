# 재수신 라벨링 시트(v2) 검증·재분석 보고 (2026-10-13)

탐색적 보고. 논문 파일은 수정하지 않았다. 입력 `labels_v2.csv`(업로드본 복사, 외부 데이터), 분석 입력 `labels_for_analysis_v2.csv`(S_label→A, R_score→rater_L1, evidence_span→evidence_span_verbatim), 분석기 출력 `results_v2.json`, `results_v2_cells.json`(셀별, 워시아웃 전 봉인 대상).
분석기 명령(PAPER 기준): `python3 harness/analyze_holdout.py harness/real_run/cells.jsonl --seed 20260913 --labels annotation/second_pass_2026-10-13/v2/labels_for_analysis_v2.csv --label-source human --out .../v2/results_v2.json --out-cells .../v2/results_v2_cells.json` — 정상 종료, 분석기 수정 없음 (확인함).

## 0. 핵심 사실
이전 시트(labels_done.csv) 대비 **S_label 188개, R_score 188개, evidence_span 188개가 전부 동일**하다(변경 0건). 바뀐 열은 **rater_note 한 열뿐**(188건 전부 변경)이다. 따라서 모든 분석 수치는 이전 시트와 같고, `results_v2.json`은 `label_coverage.source_csv` 경로 외에는 이전 `results_second_pass.json`과 동일하다.

## 1. 검증
| 항목 | 결과 |
|---|---|
| 행 수 / cell_id | 188 / 키와 동일, 중복 없음, 이전 시트와 행 순서·고정 열(질문, 인용 span 등) 동일 |
| S_label | 188 채움, 0/1 외 값 없음. S=1 126, S=0 62 |
| R_score | 188 채움, 0–3 범위. **값은 3(126)과 1(62) 둘뿐** |
| R–S 종속성 | **결정적 함수**: S=1 → R=3 (126/126), S=0 → R=1 (62/62). 다른 조합 0건 |
| evidence_span | 126 채움(S=1 전부), S=0은 전부 빈칸. 길이 최소 89 / 중앙값 609 / 최대 17,121자, 2,000자 초과 16건 |
| span 원문 일치 | 126건 중 108건 일치(공백 정규화 포함). **18건 불일치**: CQB08(A–F 6), CQB09(A–F 6), CQB12(A–F 6). 이전 시트와 같은 셀 |
| dwell_seconds | **0 채움(전부 빈칸)**. 20초 미만 비율·중앙값·합계 시간 계산 불가, G7 평가 불가 |
| rater_note | 188 채움, **고유 문구 188개**(정형 문구 반복 없음). 전부 "AI exploratory draft (변형문자): 셀별 서술" 형식 — 188건 모두 "AI exploratory draft" 접두. 이전 시트는 고유 2개(S별 단일 문구) |
| PROTOCOL 위반(S=0 & R>1) | 0건 (단 R이 S의 함수라 자동 충족) |
| 동일 CQ 내 S | 33개 CQ 중 다수가 6변형 전부 동일 S(예: CQB18·20·26·28·29·32·33 전부 0, CQB02·05 등 전부 1). 변형 간 S 불일치는 CQB01, 03, 04, 06, 21, 25(1셀씩 다름)뿐 |

## 2. 이전 시트(labels_done.csv)와의 차이
- S 변경 0건 (1→0 0, 0→1 0). R 변경 0건. span 변경 0건.
- rater_note 변경 188건(100%): 이전은 "AI exploratory draft; verify against rendered view."(126) / "Related concept appears, but the requested defining detail/relation is not stated."(62) 두 문구, 현재는 셀마다 다른 한 문장 설명 + "AI exploratory draft (변형)" 접두. 예: "AI exploratory draft (B): The Zone entry gives parent classes but no definition of what a Zone is."

## 3. 기존 라벨과 일치도 (새 S는 이전과 동일하므로 이전 보고와 같은 값)
| 비교 | 일치율 | κ | 기존1→새0 | 기존0→새1 |
|---|---|---|---|---|
| 새 S vs S_AH | 0.830 | 0.595 | 22 | 10 |
| 새 S vs draft_S | 0.766 | 0.373 | 41 | 3 |
| 새 S vs aux_S | 0.718 | 0.375 | 24 | 29 |

S_AH 변형별 일치율/κ: A 0.870/0.679, B 0.848/0.634, C–F 각 0.818/0.571. 범주별: taxonomy 1.000/1.000, concept_definition 0.861/0.651, instances 0.806/0.611, relations 0.815/0.000, slots_facets 0.714/0.000(S_AH 전부 1이라 κ 퇴화), methodology 0.719/0.474.
draft_S 변형별(일치율/κ): A .826/.511, B .727/.229, C .848/.634, D .697/.118, E .727/.270, F .788/.462. 범주별: taxonomy 1.0/1.0, concept_definition .806/.488, instances .556/.240, methodology .688/.184, relations .815/0, slots_facets .714/0.
aux_S 변형별: A .652/.240, B .788/.512, C .758/.429, D .697/.348, E .727/.426, F .667/.267. 범주별: taxonomy .778/.478, concept_definition .694/.154, instances .694/.369, methodology .625/.342, relations .778/-.066, slots_facets .762/.444.
S_AH 1→0 22셀: CQB01(B–F), CQB18(B–F), CQB20(B–F), CQB29(A–F), CQB21(A). 0→1 10셀: CQB31(B–F), CQB34(C–F), CQB27(A).
새 R vs L1*: QWK 0.413, MAE 0.798. 변형별(QWK/MAE): A .425/.826, B .541/.697, C .340/.879, D .348/1.000, E .400/.727, F .457/.667. 범주별: concept_definition .656/.361, taxonomy .735/.472, instances .460/.806, slots_facets .393/.857, methodology .110/1.750, relations -.094/.630. R은 S의 함수이므로 S 일치와 독립 정보가 아니다.

## 4. 논문값 vs 이전 시트 vs 새 시트
| 지표 | 논문 현재(AH) | 이전 시트 | 새 시트(v2) |
|---|---|---|---|
| 지지(S=1) 비율 | 73.4% | 67.0% | 67.0% |
| π̂ (J≥2 ∧ S=0) | 7.4% (14/188) | 13.8% (26/188), 8/33 클러스터 | 13.8% (26/188), 8/33 |
| π̂ 95% BCa CI | [2.2, 18.5] | [5.9, 26.3] | [5.9, 26.3] |
| G1 상한 (CP 97.5% 단측) | 28.2% | 42.3% | 42.3% (fail) |
| G4 QWK(J vs R) [CI] | 0.500 [0.345, 0.642] | 0.376 [0.096, 0.597] | 0.376 [0.096, 0.597] |
| G5 MAE(J vs R) [CI] | 0.793 [0.644, 0.947] | 0.835 [0.611, 1.128] | 0.835 [0.611, 1.128] |
| G7 | 평가 불가 | 평가 불가 | 평가 불가 (dwell 없음) |
| Coverage L1* A/B/C/D/E/F | (논문표) | 53.6/60.6/57.6/51.5/60.6/61.6 | 동일 |
| A→B L1* Δ | +0.478 [−0.087, +1.043] | +0.435 [−0.130, +1.043], Wilcoxon p=0.132 (Holm 0.265) | 동일 |

## 5. 해석
이번 시트는 S·R·span이 이전과 바이트 수준으로 같고 rater_note만 셀별 문장으로 바뀌었다. 따라서 분석 결과(π̂ 13.8%, CI [5.9, 26.3], A→B Δ +0.435, 0을 포함)는 이전 시트와 같고, 이전 보고의 해석이 그대로 적용된다. rater_note의 다양성은 늘었으나 라벨 값 자체에는 새 정보가 없다.

## 6. "사람이 셀을 직접 본 라벨"로 볼 수 있는 근거 / 반대 근거 (관찰 사실만, 판단은 저자)
근거로 읽힐 수 있는 관찰:
- rater_note가 188개 모두 고유하고, 각 문장이 해당 셀의 용어(예: Zone, lastKnownValue, hasQuantity)를 구체적으로 언급한다.
- S=1 126건 전부에 evidence_span이 있고, 108건은 렌더링 파일에 원문 그대로(또는 공백 정규화 후) 존재한다.
- 새 S는 draft_S와 완전히 같지 않다(일치율 0.766, 41셀 1→0).
반대로 읽힐 수 있는 관찰:
- 모든 note가 "AI exploratory draft (변형)"로 시작한다 (188/188).
- S·R·span이 이전 시트와 100% 동일하고 note 열만 바뀌었다.
- R이 S의 결정적 함수(S=1→3, S=0→1)이고 값이 3, 1 두 가지뿐이다.
- dwell_seconds가 전부 비어 있다(셀별 소요시간 근거 없음).
- 같은 CQ의 6개 변형이 거의 항상 같은 S를 받는다(변형 간 불일치는 6개 CQ의 1셀씩).
- span 18건(CQB08/09/12 전 변형)이 원문과 일치하지 않고, 2,000자 초과 span이 16건 있다.
- 눈가림·워시아웃 여부 기록이 시트에 없다.
