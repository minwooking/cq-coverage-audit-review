# PREREG addendum 23 — 렌더링 길이 실험의 full 뷰(B–F)를 luna로 채점해 한 judge 안에서 완결 (탐색적, 사후)

> AI가 작성한 초안이다. 저자 검토 후 사용한다. 날짜: 2026-10-14. 이 파일과 코드를 한 커밋으로 동결하고 annotated 태그 `access2026-addendum23-freeze`를 붙인다. 판정 호출은 태그 뒤에만 한다.

## 23.1 지위

**탐색적(exploratory)이며 사후(post hoc)다.** addendum 17(D28)의 luna 길이 실험은 limited·subgraph를 A–F 전체에, full을 변형 A에만 채점했다(`cells_length.jsonl`, `results_length.json`). addendum 22가 등록한 gemini-3.6-flash 재채점은 결제 한도 소진(HTTP 402)으로 실패했고 그 실행은 `registered_r34/invalid_402_20261014/`에 격리돼 있다(건드리지 않는다). 저자가 **한 judge(luna) 안에서 실험을 완결**하도록 B–F의 full 뷰 채점을 요청했다. 이 addendum의 judge 호출은 동결 이전에 하나도 없었다(코드·테스트·dry-run만 수행, 네트워크 호출 0회). 확증 가설은 없다.

## 23.2 judge와 호출

기존 luna 실행과 같다: 모델 `gpt-5.6-luna`, <internal-proxy> 로컬 프록시 `http://<local-endpoint>/v1`(외부 키 없음), temperature 0.0, `max_tokens` 1024, 같은 `RUBRIC`·`call_judge`, `response_format`을 `{"type":"text"}`로 덮어쓰고(`HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS`) 응답을 `json.loads`로 파싱(실패는 무효 응답). 기존 `MANIFEST_length.json`과 같은 값이다(확인함). 모델 공급은 <internal-proxy>만 쓴다. `/v1/models`의 `gpt-5.6-luna` 컨텍스트 창은 922,000토큰이다(확인함).

컨텍스트 점검: 가장 긴 full 뷰는 변형 C의 입력 2,414,780자로 문자/4 추정 약 604k토큰이다(추정). 실제 토크나이저 값은 다를 수 있다. 창을 넘는 입력은 업스트림이 400(context)으로 거절하며, 이 경우 **그 셀만 건너뛰고**(무효 기록으로 남김, 재시도 없음) 나머지를 계속한다. 건너뛴 셀과 변형은 보고에 모두 적는다.

## 23.3 표본과 순서

- 조건 `full`, 변형 B–F, documented exclusion 제외(addendum 17과 같은 규칙). 셀: B·C·D·E·F 각 33, 합계 **165호출**. 입력은 addendum 17 manifest 그대로(sha256 `46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32`, dry-run에서 일치, 확인함).
- dry-run 추정 입력 토큰(문자/4 올림, RUBRIC+질문 포함): B 16,098,722 / C 19,925,006 / D 19,826,783 / E 19,517,517 / F 19,517,517, 합계 94,885,545(추정).
- **순서:** 변형 B의 모든 셀 → C → D → E → F. 한 변형 안에서는 시드 20260913으로 섞는다. 변형 하나가 끝날 때마다 `luna_full_r35/PROGRESS.md`에 한 줄(셀 수, 누적 추정 토큰, 경과)을 남긴다. `--workers` ≤ 3.
- **중단 규칙:** (1) 누적 추정 입력 토큰이 상한 **100,000,000**을 넘으면, (2) 429가 재시도(최대 5회) 뒤에도 남거나 402·403이 한 번이라도 나오면, 새 호출을 멈추고 **끝난 변형은 보존**한 채 정상 종료하고 보고한다. 그 밖의 오류(502, 파싱 불가, 컨텍스트 400)는 셀 단위로 기록하고 계속한다. 재개 가능: 유효 셀은 건너뛰고 실패 셀만 다시 보낸다(예산은 이미 쓴 유효 셀 토큰부터 센다).
- 출력은 `harness/length_experiment/luna_full_r35/`에만 쓴다. `cells_length.jsonl`은 덮어쓰지 않는다(코드가 거부한다).

## 23.4 분석 (addendum 17.6과 같은 대비·통계)

기존 luna 셀(`cells_length.jsonl`: limited 188, subgraph 179 유효, A의 full 23)에 새 full 셀(B–F)을 합쳐 full을 A–F 전체로 만든다. 보고:

1. 조건별 J 분포(0–3 개수, 평균)와 **커버리지**(= J≥2 셀의 비율; 이 addendum에서 정의), variant별과 A–F 풀링.
2. 같은 (variant, CQ) 셀의 대비 full−limited, full−subgraph, limited−subgraph: 평균 차이와 **질문(CQ) 군집 BCa 95% 구간**(`analyze_holdout.cluster_bootstrap_delta`, B=10,000, 시드 20260913; 90% 병기). variant별과 A–F 풀링(군집 = 질문). 쌍 수, 정확 일치, QWK 병기.
3. 판정 오류 대 정보 부족 분리(17.6-4)는 풀링에 대해 보고한다.
4. 기술 통계와 구간만 등록한다. pass/fail 임계, 동등성 마진, 다중성 보정은 없다. 해석은 17.6-5와 같다: 구간이 허락하는 범위로만 쓴다.

## 23.5 이탈과 한계

- 이 judge는 등록 judge(gemini-3.6-flash)가 아니므로 기존 holdout J와 직접 비교할 수 없다. 조건 간 차이는 이 judge 안에서만 읽는다.
- full B–F와 limited·subgraph 셀은 채점 시점이 다르다(limited·subgraph는 2026-10-13, full B–F는 이번). 서빙 변화(drift)가 대비에 섞일 수 있다. A의 full은 2026-10-13 실행이다.
- 입력 토큰은 추정치다. A의 subgraph는 `schema_view`를 쓰며 A의 full 뷰와 렌더러가 정확히 같지 않다(17.2). B의 full 뷰는 `schema_view(graph_B)`와 바이트가 같다.
- 탐색적 사후 분석이다. 원고(main.tex)와 supplement는 이 addendum에서 수정하지 않는다.

## 23.6 코드

`run_length_judge.py --design luna-full-BF`(`--confirm-addendum23-frozen`, 모델·로컬 호스트·manifest sha256 고정 확인, `--token-budget` 기본 100M), `analyze_length.py --extra-full-cells --per-variant`, 테스트 `test_length_experiment.py`(27개 통과; 합성 데이터·네트워크 없음).

## 23.7 [2026-10-14, 실행 후 기록] 중단

동결 뒤 실행해 B·C·D를 완료하고 E를 21/33에서, F를 0/33에서 멈췄다. 사유: 업스트림 한도 소진(진행 중 3호출이 HTTP 429 + `Retry-After` 약 2,497,900초). 23.3의 "429가 남으면 중단" 규칙을 적용해 프로세스를 수동 종료했고 완료 변형을 보존했다. 동결 이후 변경은 분석 코드의 민감도 풀링 옵션과 보고 제목뿐이다(채점 규칙 불변). 결과: `harness/length_experiment/luna_full_r35/`.
