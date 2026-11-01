# 평가자 안내 (1쪽)

평가자 ID: [[TBD]] · 시트: `sheet_<ID>.csv` · 대상: 질문(CQ)별 제공 자료(`rendered_view_path`의 텍스트)

## 하는 일
각 행에서 질문(`question_text`)과 제공 자료를 읽고 아래 두 가지를 **서로 독립적으로** 입력한다.

**1. S_label (0/1) — 근거 지지 여부.** PROTOCOL.md 원문 기준:

> Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer to the CQ. Set it to `0` when no such span exists. Copy the shortest sufficient verbatim span, preserving punctuation and whitespace where practical; if unsupported, leave the span empty and explain briefly why no supporting span exists. Do not infer support from the graph, external sources, or the annotator's knowledge.

즉 제공 자료 안의 글자 그대로의 구간이 답을 뒷받침할 때만 S_label=1. 아니면 0. 1이면 가장 짧은 충분 구간을 `evidence_span`에 복사하고, 0이면 비우고 `rater_note`에 이유를 짧게 쓴다. 자료 밖 지식, 외부 출처, 그래프 추론으로 채우지 않는다.

**2. R_score (0–3) — 자료가 질문에 답하는 정도.** [[TBD: 척도 정의는 rubric/ 의 Layer-1 척도 원문을 이 칸에 붙인다]]. R_score는 S_label을 정한 뒤 그 값에 맞추지 말고, S와 무관하게 자료의 답변 충분성만 보고 매긴다. (S=0인데 R이 높거나 그 반대도 가능하다.)

## 기록
- `start_time`, `end_time`: 각 행을 열 때와 입력을 끝낼 때 시각을 `HH:MM:SS`로 적는다(시계나 타이머 앱 사용). 행 사이 휴식은 이전 행의 `end_time`을 그대로 두고 다음 행의 `start_time`을 휴식 뒤에 적는다. 이 값은 체류 시간 점검용이며 평가 결과에 영향을 주지 않는다.
- 행 순서대로 진행한다. 이전 행을 고치지 않는다. 고쳤다면 `rater_note`에 "수정함"과 이유를 적는다.
- 한 번에 작업하는 분량과 휴식 계획: [[TBD]]

## 해서는 안 되는 것
- 다른 평가자·저자와 라벨을 상의하지 않는다. 같은 질문이 다시 나와도 앞의 답을 찾아 맞추지 않는다(행 순서는 섞여 있다).
- 파이프라인·모델 출력, 점수, 정답 후보를 알아내려 하지 않는다. 제공 파일 이름에서 어떤 변형인지 추측하지 않는다.
- **AI 도구 금지**(번역기, 검색 요약, 챗봇, 코드 보조 포함). 아래에 확인하고 서명한다.

- [ ] 이 평가 전 과정에서 AI 도구를 사용하지 않았다(행 단위 사용 없음, 시트 단위 사용 없음).
- [ ] 저자·다른 평가자와 라벨을 논의하지 않았다.
- [ ] 위 기준을 읽고 이해했다.

확인일: [[TBD]] · 평가자 ID: [[TBD]] (이름 대신 ID만 쓴다)

## 질문이 생기면
**저자가 아닌 조정자**([[TBD: 조정자 연락처]])에게 보낸다. 조정자는 판정 점수를 모른다. 저자에게 직접 묻지 않는다. 기준 해석 질문은 답을 모든 평가자에게 같은 문장으로 전달하며 기록한다.
