# 다중 평가자(H1/H2/H3) 내보내기 분석 보고 — 2026-10-24

> **AI-generated analysis.** 이 보고와 동봉 스크립트·CSV는 AI(Claude)가 생성했다. 사람이 검토하기 전까지 논문·등록 절차에 인용하지 않는다. 기존 레포 파일은 하나도 수정하지 않았고(신규 산출물만 이 폴더), git 작업·모델 호출은 하지 않았다. 참고: 브리핑의 HEAD는 `273bd39`였으나 작업 트리 HEAD는 그 직후 커밋 `d30925e`였다(읽기 전용 확인만).

## 0. 결론 먼저

**이 데이터(12건)를 그대로 다음 등록의 G4/G5 consensus-버전으로 쓸 수 없다.** 세 가지 독립 사유:

1. **평가자 간 겹침 0셀.** 12개 셀 전부가 정확히 1명씩 라벨(H1 10, H2 1, H3 1). 다수결 consensus가 정의되지 않는다 — 만들어진 `consensus_labels.csv`는 사실상 단일 평가자 라벨(H1이 10/12)이다. rater 쌍별 κ/QWK/MAE 전부 n=0.
2. **커버리지 6.4% (12/188).** G4·G5 등록 추정량은 primary 188셀 전체에 대한 것이다(피닝 분석기는 rater_L1을 전 primary 셀에서 요구한다). 12셀로 돌리면 등록 추정량이 아니라 탐색치가 된다.
3. **나온 수치 자체가 게이트를 통과 못 함.** consensus vs 판정 J: **G5 MAE = 1.000 [BCa 0.500, 1.667] → fail**(기준 ≤0.50, AH 전체 0.793, 사람-사람 0.287). **G4 QWK = 0.473 [0.088, 0.818]** → 반증 전용 게이트라 상한 0.818 ≥ 0.60이라 형식상 not_falsified지만, 구간 폭 0.73에 n=12라 판정 근거가 못 된다. 또한 H그룹과 AH/IND 라벨러 집단의 R 눈금이 크게 달라(consensus vs AH 새 L1: QWK 0.125, MAE 1.417; 사람-사람 기준 0.728/0.287) 기존 기준선과 같은 자리에 놓을 수 없다.

가능했던 것: 라벨링 사이트 파이프라인이 실제 한국어 노트·실측 dwell로 라벨을 수집함(§5 인간성 근거). 가능하려면: 같은 셀에 2~3명 중복 라벨(사이트 작업 나누기 목표인원 조정) + washout 재평가 수집 + registered design(188셀) 충족.

## 1. 현황 확정 (README/ADJUDICATION/GUIDE/스크립트 읽고)

- 준비물(패킷 빌더, 평가자 가이드, 조정 절차, 단위테스트, dry-run 로그)은 갖춰져 있고 dry-run까지 완료된 상태. 실라벨은 라벨링 사이트(claude.ai 아티팩트, IndexedDB 저장)로 수집되어 `human_labels_export_2026-10-15.csv` 12건만 존재.
- **기존 `compute_multirater_agreement.py`는 충분히 충분하지 않다**: (a) 입력이 packet 흐름용(`keys/key_<RID>.csv` 불투명키 + `S_label/R_score` 시트)이고 사이트 내보내기 스키마와 다름 → `analysis_2026-10-24/keys/`, `filled/`에 변환본(신규 파일)을 만들어 수정 없이 실행함. (b) 쓰기 경로는 `--json-out`(선택)과 stdout뿐 — 기존 파일을 덮어쓰지 않음을 코드 확인으로 검증하고 실행. (c) 결과(`agreement_compute_script.json`): `n_cells_common=0`, Fleiss/α/쌍별 κ 전부 null/NaN — 겹침 0이라 스크립트 정의상 산출 불가 확인. (d) 이 스크립트는 R의 QWK·MAE, %-agreement, dwell/note 검사를 계산하지 않아 과제 요구 통계를 위해 신규 스크립트(`analyze_multirater.py`)에 재구현하되, 그 스크립트의 Cohen κ 함수는 import로 재사용(수정 없음).
- `README.md`의 일치도 계산 전제("켜면 셀당 평가자가 한 명이라 평가자 간 일치도는 계산할 수 없다")가 실제 수집 상태에서 입증됨.

## 2. 입력·프로버넌스

| 입력 | 내용 |
|---|---|
| `../human_labels_export_2026-10-15.csv` | 12행(H1 10, H2 1, H3 1), sha256 `1f9e67129afbfb47…` |
| `../site_key_2026-10-13.csv` | opaque→`primary:<variant>:<CQ>` 키. cell 188행 전부 primary(제어셀 없음 → G3 재료 없음), 12/12 불투명 ID 전부 매핑 |
| `annotation/labeling_sheet_key_2026-10-13.csv` | 저장소 내 AH 라벨 위치(cell_id,J,S_AH,L1_star). 브리핑이 준 `annotation/packet/labels_primary_pass.csv`는 저장소에 없음(blank만 존재). 키의 S_AH 12셀 = 봉인 사본(`locked_labels/primary_working.csv`, 읽기 전용)의 A와 전원 전치 일치 확인 |
| `harness/real_run/cells.jsonl` | 등록 판정 J(primary 188 + control 36 = 224), 12셀 전부 존재 |

시드 20260913, 클러스터는 cell→cq(site_key `cq_id`, cells.jsonl `cluster_id`와 일치)로 복원. B=10,000.

## 3. rater 쌍별 매트릭스 (n, %-agreement(S), Cohen κ(S), QWK(R), MAE(R))

| 쌍 | n | %-agr(S) | κ(S) | QWK(R) | MAE(R) |
|---|---|---|---|---|---|
| H1–H2 | **0** | — | — | — | — |
| H1–H3 | **0** | — | — | — | — |
| H2–H3 | **0** | — | — | — | — |
| (참고) 인간-인간 기준 AH vs IND(188셀, 봉인) | 188 | 0.830 | 0.595 | 0.728 [0.567, 0.859] | 0.287 [0.161, 0.447] |

기존 인간-인간 기준: `CLAIMS-LEDGER-2026-10-13.md` 547행(`harness/review6_reanalysis/results.json /R5/ordinal_0_3`), `PREREG_ADDENDUM_25.md` 38행(`results_llm_rater_luna.json baseline_188_AH_vs_IND`).

| rater | n | S=1 | R 분포(0/1/2/3) | dwell 중앙값 | <20s 비율 |
|---|---|---|---|---|---|
| H1 | 10 | 3 | 4/3/0/3 | 108.0 s | 0% |
| H2 | 1 | 1 | 0/0/1/0 | 234.2 s | 0% |
| H3 | 1 | 1 | 0/1/0/0 | 126.8 s | 0% |

## 4. consensus gold와 대조

`consensus_labels.csv`(신규): 등록 분석기 호환 열(`cell_id,A,rater_L1,evidence_span_verbatim`) + 근거 열(`n_raters,raters,S_votes,R_values,J,S_AH,L1_star_AH`). 규칙: S = 엄다수결, 동률 시 unsupported 우선(ADJUDICATION_MULTIRATER §2), R = 중앙값(반올림). **n_raters=1이 12/12 — 다수결이 아니라 단일 라벨 그대로** (gold 정의 미달, deviation 명시).

**consensus vs AH** (n=12, 겹침 12/12 = AH 188커버리지 6.4%, 전 셀 cells.jsonl 존재):

| 기준 | S(A) 일치 | κ(S) | R QWK | R MAE | R exact |
|---|---|---|---|---|---|
| AH 키(S_AH, L1_star) | 0.500 | 0.122 | 0.473 | 1.000 | — |
| AH 새 rater_L1(봉인 사본; **기준선과 동일 지표**) | 0.500 | 0.122 | **0.125** | **1.417** | 0.167 |
| IND v3(second_pass 두 번째 인간) | 0.500 | 0.122 | −0.011 | 1.667 | — |
| (기준선 AH vs IND 188) | 0.830 | 0.595 | 0.728 | 0.287 | 0.718 |

S 불일치 6셀(전부 consensus 0 / AH 1): `A:CQB03, A:CQB30, B:CQB21, B:CQB29, D:CQB27, F:CQB07` — 이 6셀 중 J≥2가 5개(판정은 지지, H그룹은 무지지). R까지 포함한 불일치 전체는 `results_multirater.json vs_ah(_fresh).mismatches`(10행).

**consensus vs registered judge(J)** — 피닝 `harness/analyze_holdout.py`를 **수정 없이** `--labels consensus_labels.csv --label-source human --allow-partial`로 실행(rc=0; in-process dry 검증 후 실행, 쓰기 대상은 이 폴더 신규 파일 2개뿐):

| 게이트 | 결과(consensus, 12셀/11 CQ) | 등록 전체 참고치 |
|---|---|---|
| G4 human-judge QWK | not_falsified: QWK 0.473, BCa CI [0.088, 0.818] (반증 전용 — pass 불가 구조) | AH: 0.500 [0.345, 0.642] |
| G5 MAE(J,H) | **fail**: MAE 1.000, BCa CI [0.500, 1.667] (≤0.50) | AH: 0.793 [0.644, 0.947]; 사람-사람 0.287 |
| G1 π̂ (부분표본) | fail: events 4/12, CP 단측 상한 0.692 | AH 188: 0.074, 상한 0.185 |
| G2 / G3 / G6 / G7 / G8 | not_computable (§6) | same |

내 자체 군집 percentile bootstrap(seed 20260913, B=10,000, 탐색용)은 MAE 1.000 [0.462, 1.636], QWK 0.473 [0.000, 0.804]로 분석기 점추정과 일치. `registered_design.conforms=false`(12셀이라)가 결과 JSON에 봉인됨 — 등록 게이트로 읽을 수 없는 이유의 기계적 증거.

## 5. dwell·note 인간성 검사 (기계 판정 가능 서명만)

- **dwell**: 중앙값 126.5 s (IQR 67.0–216.0 s, min 49.0, max 340.8, mean 149.4), 전건 ≥20 s → AH primary pass(중앙값 9.3 s, 91% <20 s)와 정반대 프로파일. G7 관점 "20s 미만 0%"라 이 데이터 자체로는 fast-lane 위반 없음.
- **note 서명**: 비어있지 않은 노트 10건 전부 서로 다름(distinct 10/10), 전건 공통 접두 0자, v2 시트 단일 문구 템플릿("AI exploratory draft; verify against rendered view." / "Related concept appears…") 일치 **0건**, 전건 한글 포함, 평가자 간 동일 문장 0건, "수정함" 자기수정 마커 1건(RATER_GUIDE §기록 규칙 준수 흔적). S=0 7건 전부 노트 있음, S=1 5건 전부 span 복사 있음(GUIDE 규칙과 정합). 특이점 1건: `A:CQB10`(S=1)은 span 칸에 해명 문장을 입력하고 `span_verbatim=False`로 표시(원문 불일치 자기신고).
- **한계**: 이건 "v2식 기계 복제 서명의 부재"를 확인할 뿐, 노트가 사람 작성임을 증명하지는 않는다. 노트 10건으로 표본이 너무 작다.

## 6. cell_id 겹침·G2 재료

| 항목 | 값 |
|---|---|
| rater 쌍별 공유 셀 | 0/0/0 (겹침 비율 0%) |
| 2명 이상 라벨한 셀 | 0/12 |
| AH 188 대비 커버리지 | 12/188 = 6.4% (전 셀 primary, 전 셀 cells.jsonl·AH 키에 존재) |
| G2 washout | `annotation/g2_washout_2026-10/` 수집물 없음(INSTRUCTIONS "No label has been collected"), `washout_pass_72_ready_to_fill.csv` A열 비어있음 0/72, 내보내기에 동일 rater 재평가 0건 → **G2 불가 계속** |
| G3 | 사이트 키가 primary 188뿐 — ablated 24셀 라벨 생성 불가 → **G3 불가 계속** |

## 7. 산출물

```
analysis_2026-10-24/
├─ analyze_multirater.py                 # 신규 분석 스크립트(재실행 가능, 입력 읽기 전용)
├─ consensus_labels.csv                  # 다수결 gold(단일 라벨로 퇴화 — §4 주의)
├─ results_multirater.json               # 위 통계 전부 + 입력 sha256
├─ agreement_compute_script.json         # 기존 compute 스크립트 수정 없이 실행한 결과(전부 null — 겹침 0)
├─ keys/key_H{1,2,3}.csv, filled/H{1,2,3}.csv  # 위 실행용 형식 변환본(신규)
├─ results_consensus_holdout.json        # 피닝 analyze_holdout 실행 (--allow-partial, rc=0)
├─ results_consensus_holdout_cells.json  # 셀별 J/판정 대조 — 워시아웃 전 봉인 대상(분석기가 봉인 주의 출력)
└─ REPORT_ko.md                          # 본 문서
```

기존 파일 수정·git 작업·모델 호출 없음. `results_consensus_holdout_cells.json`은 셀별 판정값 포함 → washout 전 봉인 규율 준수 필요.

## 8. 권장(읽는 사람 판단용)

1. 사이트를 셀당 2~3명 중복으로 재수집해 겹침 셀을 확보한다(쌍별 κ가 의미를 가지려면 최소 30셀 이상; 등록 용도는 188 전셀×2~3명). 그 전에는 어떤 consensus gold도 무의미.
2. H그룹과 AH/IND의 R 눈금 차이(QWK 0.125 vs 기준 0.728)가 rater 집단 특성인지 rubric 해석 차이인지 RATER_GUIDE §2의 `[[TBD: rubric 원문 붙이기]]`를 메운 뒤 재검토 — 현재 가이드는 척도 정의가 빈칸이다.
3. 다음 등록에서 consensus R(다수결·중앙값)을 rater_L1 대체로 쓰려면 사전등록 부록에 consensus 정의를 먼저 고정할 것(현 ADJUDICATION_MULTIRATER는 R 조정을 금지하므로 "조정"이 아니라 "합성 규칙"으로 명시).
