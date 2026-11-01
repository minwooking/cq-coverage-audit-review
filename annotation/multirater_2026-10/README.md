# 다중 평가자(눈가림) 패키지 — 실험 1 준비

초안·도구 모음이다. 동결하지 않았고 원고는 바뀌지 않았다. 이 폴더의 코드는 사람이 검토하고 테스트한 뒤 쓴다.

## 파일
| 파일 | 역할 |
|---|---|
| `build_multirater_packets.py` | 평가자별 다른 시드로 제약 셔플(같은 CQ 간격 ≥20)한 눈가림 시트 N개(2~3) 생성. 불투명 ID, 키는 `keys/`에 |
| `compute_multirater_agreement.py` | S: Fleiss κ, Krippendorff α(이진), 쌍별 Cohen κ / R: Krippendorff α(순서형) / 평가자·다수결·조정 결과 vs J≥2의 κ와 단측 Clopper–Pearson |
| `tests/test_multirater.py` | 단위 테스트(Fleiss κ 알려진 값 0.210 등) |
| `dry_run.py`, `dry_run_log.txt` | 합성 평가자 3명 전체 파이프라인 시험(임시 디렉터리에만 씀) |
| `ADJUDICATION_MULTIRATER.md`, `RATER_GUIDE_ko.md` | 조정 절차, 평가자 안내 |
| `../../PREREG_ADDENDUM_18_DRAFT.md` | 사전 등록 부록 18 초안 |

## 사용 순서
1. **평가자 확정**: 요건은 부록 18.2. ID(R1~R3)만 쓰고 이름은 키·동의서 쪽에만 둔다. 동의서는 `../CONSENT_TEMPLATE.md`.
2. **부록 동결**: 저자가 `[[TBD]]`를 채우고 `PREREG.md`에 덧붙여 커밋·태그(부록 18.9 순서).
3. **패킷 생성**:
   `python3 build_multirater_packets.py --input ../labeling_sheet_blind_2026-10-13.csv --raters R1 R2 R3 --master-seed <저자가 정한 문자열> --anonymize-views`
   `packets/<ID>/sheet_<ID>.csv`와 `views/`만 해당 평가자에게 준다. **`keys/`는 배포 금지**(저자 보관, 가능하면 저장소 밖).
4. **배포**: 평가자별 폴더 + `RATER_GUIDE_ko.md`. 평가자끼리 파일을 공유하지 않게 한다.
5. **수거**: 채운 시트를 `filled/`에 받는다. 수거 해시를 기록.
6. **일치도**:
   `python3 compute_multirater_agreement.py --keys-dir keys --filled R1=filled/R1.csv R2=filled/R2.csv R3=filled/R3.csv --judge-key <cell_id,J CSV> --json-out agreement.json`
   judge-key는 저자 쪽 파일(예: `../labeling_sheet_key_2026-10-13.csv`, 열 `cell_id,J`)이며 조정 전에는 일치도 단계에서만 쓴다. 일치도(α)를 먼저 확인하고 부록 18.6의 규칙을 적용한다.
7. **조정**: `ADJUDICATION_MULTIRATER.md`. 조정 결과 CSV를 `--adjudicated`로 넣어 6단계를 다시 실행.
8. **분석**: 부록 18.6의 지표·결정 규칙대로 보고. 규칙 밖 분석은 탐색적이라고 표시한다.

## 알아둘 점
- 시트에는 `cell_id`(불투명), `question_text`, `category`, `rendered_view_path`와 입력 열만 있다. J, 판정 인용 구간, AI 초안, AH 라벨, 독립 평가자 라벨, `variant` 열은 코드가 읽지도 쓰지도 않는다.
- 렌더링 파일은 변형마다 내용이 다르므로 변형 은폐는 완전하지 않다. `--anonymize-views`는 파일명만 무작위화한다. 자료 내용에서 변형을 추측할 가능성은 부록 18.4에 한계로 적었다.
- 현재 188셀은 CQ 33개에 걸쳐 있다(은행 36문항 중 3문항 셀이 이 시트에 없음). 36 클러스터 기준은 부록 18.5.
- 동의서·개인정보: 이름, 연락처, 키는 이 폴더에 두지 않는다.
