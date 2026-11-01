# 전문가 품질 평가 패키지 — 외부 타당성 실험 (커버리지 vs 실무자 품질)

초안·도구 모음이다. 동결하지 않았고 원고·`PREREG.md`는 바뀌지 않았다(부록 초안: `../../PREREG_ADDENDUM_19_DRAFT.md`). 이 폴더의 코드와 출력은 사람이 검토·테스트한 뒤에만 쓴다.

질문: 커버리지(L1\*, J)가 전문가가 말하는 산출물 품질(답변 가능성과 분리된 5개 기준 + 전체 순위)을 따라가는가. claims 표의 "Coverage tracks what practitioners call artifact quality = not tested" 행에 해당한다.

## 파일
| 파일 | 역할 |
|---|---|
| `artifacts.json` | 평가 대상(holdout A–F, dev A–F)과 그래프 경로. 저자용, 배포 금지 |
| `build_expert_quality_packets.py` | 눈가림 패킷 생성(rdflib 필요). 재직렬화·run-id 치환·동일 내용 병합·평가자별 난수 ID·셔플·유출 검사 |
| `RATER_FORM_QUALITY.md` | 평가자 안내·기준 앵커·순위·진행 방법(패킷에 복사됨) |
| `rating_sheet_template.csv`, `exit_survey_template.csv` | 평가 시트·종료 설문 양식 |
| `coverage_reference.csv` | 저자 쪽 커버리지(J, L1\*). 평가자에게 주지 않음. 값은 main.tex tab:holdout-coverage와 supplement tab:s-scorecard에서 옮김 |
| `analyze_expert_quality.py` | 표준 라이브러리 전용. `analyze`(일치도·상관·부트스트랩·기준별), `power`(정확 임계 τ·모의 검정력) |
| `tests/` | 단위·종단 테스트 22개(`python3 -m unittest discover -s tests`) |
| `dry_run.py`, `dry_run_log.txt` | 합성 평가자 3명 전체 실행(임시 폴더에만 씀) |

## 사용 순서
1. 부록 19의 `[[TBD]]`를 채우고 동결(19.10 순서). 평가 의도문(`artifacts.json`의 `task_statement`)은 질문·점수 정보 없이 저자가 쓴다.
2. 패킷 생성: `python3 build_expert_quality_packets.py --raters R1 R2 R3 --master-seed <저자 문자열>` (세트 제한 `--sets holdout`, E/F 분리 `--keep-duplicates`). `packets/<ID>/`만 해당 평가자에게 준다. **`keys/`는 배포 금지**(저자 보관, 가능하면 저장소 밖). 패킷 안 파일 이름은 난수이고 시트에 `variant`, 커버리지, 판정 열이 없다.
3. 수거: 채운 `rating_sheet_<ID>.csv`와 종료 설문. 수거 해시를 기록한다.
4. 분석: `python3 analyze_expert_quality.py analyze --keys-dir keys --filled R1=filled/R1.csv R2=... --coverage coverage_reference.csv --json-out results.json`. 형식 오류(범위, 동순위)는 분석 전에 보고하고 멈춘다(`--force`로 무시 가능, 권장하지 않음).
5. 해석 전에 `python3 analyze_expert_quality.py power --coverage coverage_reference.csv` 출력과 부록 19.8의 규칙을 먼저 읽는다.

## 알아둘 점 (한계)
- **L1 변형 은폐는 불완전하다.** 변형마다 모델링 방식(레이블 형태, 정의 유무, 계층 깊이)이 달라 내용만으로 짐작할 수 있다. 이름·파일·run-id·접두어 단서만 제거한다. 짐작 여부는 종료 설문으로 묻는다.
- **L2 E와 F는 내용이 같다.** 그래프가 `buildrun_E`/`buildrun_F` 식별자 줄만 다르고 렌더링 해시가 같다(확인함: holdout 렌더링 sha256 `cb451ed3…` 동일, dev tbox 동일). 치환 후 동일하므로 기본은 한 산출물(E+F)로 제시한다. 따라서 독립 산출물은 세트당 5개다.
- **L3 표본.** 검토 자료는 산출물당 같은 크기의 무작위 표본(개념 30, 관계 25, 진술 30, 계층 6 브랜치)이며 모든 평가자가 같은 표본을 본다. 표본 잡음은 평가자 일치도에 공통으로 들어간다. 선택적 전체 TTL 부록으로 보완한다.
- **L4 n이 매우 작다.** 부록 19.8의 검정력 표를 본다. 이 실험은 확증이 아니라 방향 확인이다.
- **L5 변형은 독립 시스템이 아니다.** B–F는 A에서 단계적으로 수정한 계열이다.
- **L6 Q5(과업 적합성)는 답변 가능성과 개념상 가깝다.** 그래서 합성 점수는 Q1–Q4만 쓰는 민감도 분석을 함께 낸다.
- 시간: 산출물당 20–30분, 세트당 약 2–2.5시간(5개), 두 세트면 약 4–5시간. 한 번에 몰아서 하지 않게 한다.
- 개인정보: 평가자 이름·연락처는 이 폴더에 두지 않는다(ID만).
