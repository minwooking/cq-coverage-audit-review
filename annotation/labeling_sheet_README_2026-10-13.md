# 라벨링 시트 사용법 (2026-10-13)

대상: Brick 홀드아웃 주 셀 188개 (변형 A 23 + B~F 각 33; 적격성 제외 28셀은 PREREG §6-2, main.tex VI-A). 행 순서는 seed 20260913으로 섞었고, `cell_id`로 복원된다.

## 파일
- `labeling_sheet_blind_2026-10-13.csv` — **평가자용.** 이것만 연다.
- `labeling_sheet_key_2026-10-13.csv` — **키 파일. 평가자는 열지 말 것.** J(판정 점수), 기존 AH 라벨(S_AH), L1*, AI 초안(draft_S), LLM 보조 라벨(aux_S)이 들어 있다.

## 채울 열
- `S_label`: 1 = 인용 span이 CQ의 답을 뒷받침, 0 = 뒷받침 없음. 기준(PROTOCOL.md 원문): "Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer to the CQ. Set it to `0` when no such span exists." 그래프, 외부 자료, 본인 지식으로 추론하지 않는다.
- `R_score`: 0–3 (0 관련 개념 없음 / 1 부분 / 2 대체로 / 3 완전).
- `evidence_span`: 렌더링 파일(`rendered_view_path`)에서 복사한 가장 짧은 충분 구간. S=0이면 비우고 `rater_note`에 이유를 적는다.
- `rater_note`, `dwell_seconds`(셀당 소요 초).
- `in_crossfamily_48`은 채우지 않는다(48셀 표식, 정보용).

## 시간·눈가림
- 셀당 약 90초가 PREREG 계획값이다(PREREG 1차 패스 계 "셀당 ~90초"). 단 LABELER_GUIDE는 이를 "guidance only"로 적고, 등록된 하한은 G7의 "20초 미만 셀 < 3%"다. 서두르지 말 것.
- 판정 모델의 J와 근거 설명(rationale)은 보지 않는다. 시트의 `judge_quoted_span`은 검증 대상 span일 뿐 증거가 아니다. 기대 답(expected_answer)은 판정 모델도 받지 않은 자료이고 프로토콜의 제공 자료 목록에 없어 뺐다.
- 변형 식별은 내용으로 드러날 수 있다(프로토콜도 변형 눈가림을 주장하지 않는다).

## 완료 후 분석
`harness/analyze_holdout.py`는 열 `cell_id`, `A`(0/1), `rater_L1`("0".."3"), `evidence_span_verbatim`을 가진 CSV를 `--labels`로 받는다. 이 시트의 열을 `S_label→A`, `R_score→rater_L1`, `evidence_span→evidence_span_verbatim`으로 바꿔 저장한 뒤 실행한다.

```
cd paper/access2026
uv run python harness/analyze_holdout.py harness/real_run/cells.jsonl --labels <renamed.csv> --label-source human
```
(`results_human_pass/README.md`의 명령 참조. 나머지 옵션은 거기 따른다.) 실행 전 사람이 검토하고 테스트할 것. 이 시트는 정식 1차 패스 도구(label_assist.py)와 별개의 보조 시트이며, 결과는 탐색적으로만 보고한다.
