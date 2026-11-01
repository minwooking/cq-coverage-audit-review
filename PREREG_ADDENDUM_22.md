# PREREG addendum 22 — 렌더링 길이 실험을 등록 judge(gemini-3.6-flash)로 재채점 (탐색적, 사후)

> AI가 작성한 초안이다. 저자 검토 후 사용한다. 날짜: 2026-10-14.

## 22.1 지위

**탐색적(exploratory)이며 사후(post hoc)다.** addendum 17의 길이 실험은 이미 대체 judge gpt-5.6-luna(D28, 17.12)로 실행되어 결과(`cells_length.jsonl`, `results_length.json`)가 있다. 이 addendum은 그 결과를 본 뒤에 추가하는 재채점이며 확증 검정이 아니다. 이 addendum 동결 이전에 이 addendum의 judge 호출은 하나도 없었다(코드·테스트·dry-run만 수행, 네트워크 호출 0회).

## 22.2 judge

등록 holdout judge **gemini-3.6-flash**를 복원한다(addendum 17 / D28이 luna로 바꾼 것을 되돌려 같은 판정자로 재채점). 설정은 `harness/real_run/MANIFEST.json`과 같다: endpoint `https://generativelanguage.googleapis.com/v1beta/openai`, temperature 0, max_tokens 1024, `response_format=json_object`, `extra_body={"google":{"thinking_config":{"thinking_level":"minimal"}}}`, 루브릭·호출 코드는 `run_holdout.call_judge` 그대로. 키는 환경변수 `HOLDOUT_JUDGE_API_KEY`로만 받는다(플래그·파일 금지, 로그에 남기지 않음). `--workers 3` 이하, 429는 `call_judge`의 재시도(최대 5회, Retry-After 존중)와 1초 최소 간격을 따른다.

## 22.3 조건·변형·표본

- 조건: `limited`(60,000자 절단)와 `subgraph`(질문 관련 서브그래프). 변형 A–F 전부. documented exclusion 28쌍은 제외(addendum 17과 같은 규칙).
- 호출 수: limited 188 + subgraph 182 = **370**(subgraph not_applicable 6셀은 보내지 않음). dry-run 추정 입력 토큰 합계 4,608,188(= ⌈문자/4⌉ 기준 추정, 토크나이저 값 아님), 예산 상한 7,000,000 유지.
- **full 조건은 재실행하지 않는다.** holdout 실행(`harness/real_run/cells.jsonl`)에서 이 judge가 이미 채점한 primary 188셀을 `condition=full`로 재사용한다. 입력 일치 확인(dry-run, 확인함): holdout 유효 primary 188셀 중 188셀의 `artifact_digest`가 manifest의 full 입력 sha256과 같다.
- 입력은 addendum 17의 `harness/length_experiment/inputs/manifest.jsonl` 그대로(sha256 `46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32`, 이 동결 시점에 재계산해 일치, 확인함). 입력·은행·뷰는 바꾸지 않는다.
- 출력은 새 폴더 `harness/length_experiment/registered_r34/`(`cells_registered_r34.jsonl`)에만 쓴다. `cells_length.jsonl`(luna)은 덮어쓰지 않는다(코드가 거부한다). 재개 가능: 유효 셀은 건너뛰고 실패 셀만 다시 보낸다.

## 22.4 분석

addendum 17.6과 같은 대비와 지표: full−limited, full−subgraph, limited−subgraph(짝지은 (variant, CQ) 셀)의 평균 차이와 **질문(CQ) 군집 BCa 95% 구간**(`analyze_holdout.cluster_bootstrap_delta`, B=10,000, 시드 20260913; 90% 구간 병기), QWK, 정확 일치, 판정 오류 대 정보 부족 분리(17.6-4). 추가: 같은 셀에서 luna 결과(`cells_length.jsonl`)와의 일치(조건별 정확 일치, QWK, 평균 비교). 차이: luna 분석의 full은 변형 A뿐이었으나(23셀), 여기서는 6개 변형 전부(188셀)다. pass/fail 임계는 등록하지 않는다. 해석은 17.6-5와 같고, 결과는 두 judge 나란히 보고하며 원고 문장은 구간이 허락하는 범위로만 쓴다.

## 22.5 이탈과 한계

- addendum 17.0/17.12의 judge(luna)에서의 이탈이다. 사유: 등록 judge로 같은 대비를 확인하기 위함. 두 judge 결과는 대체하지 않고 병기한다.
- holdout full 셀(2026-09-21)과 이번 limited/subgraph 셀의 채점 시점이 다르다. 모델 버전·서빙 변화(drift)가 대비에 섞일 수 있다.
- 입력 토큰은 추정치다. 변형 A의 subgraph는 `schema_view`를 쓰므로 A의 full 뷰와 렌더러가 정확히 같지 않다(17.2 참고).
- 탐색적 사후 분석이므로 다중성 보정을 하지 않는다.

## 22.6 코드와 동결

코드: `run_length_judge.py --design registered-all`(`--confirm-addendum22-frozen` 필요, 모델·호스트·manifest sha256 고정 확인, 키는 환경변수만), `analyze_length.py --holdout-cells/--compare-cells/--report-ko`, 발사기 `launch_registered_r34.sh`, 테스트 `test_length_experiment.py`(20개 통과, 합성 데이터·네트워크 없음). 이 파일과 위 코드를 한 커밋으로 동결하고 annotated 태그 `access2026-addendum22-freeze`를 붙인다. 판정 호출은 태그 뒤에만 한다.
