# PREREG addendum 21 — 두 번째 도메인 B→B′ 복구 대비 (탐색적)

## 21.1 지위

**탐색적(exploratory)이며 확증이 아니다.** 결함은 B의 실패를 본 뒤에 확인·수정했다(개발 연구에서 coverage 붕괴 → 파이프라인 추적 → `iri.py` slug 결함 확인, 수정 커밋 1de0282, 2026-09-25). 따라서 이 대비는 사전 등록된 가설 검정이 아니라 사후 복구 점검이다. 동결 이전에 이 addendum의 judge 호출은 하나도 없었다(스크립트 작성과 B 재현 빌드만 수행, LLM 호출 0회). 날짜: 2026-10-14.

## 21.2 B′의 조작적 정의

- B′ = 변형 B와 **동일한 입력**(`output_mfg/triples.json`, 89개 트리플, sha256 78a92114…)에서 stage 4만 다시 실행한 결과. 변경은 **단 하나**: 커밋 1de0282의 `src/chunktograph/iri.py`(비-ASCII 라벨을 `x` 대신 `x-<sha256[:12]>`로 슬러그). 이 수정은 그것이 만든 `tests/test_iri.py`(8개 통과)와 함께 적용한다.
- stage 4 코드는 **B가 만들어진 시점의 코드(커밋 f0f754d)** 를 쓴다. 그 위에 1de0282만 cherry-pick한다. 이후의 stage 4 변경(eed791c: 타이핑 배치·untyped 거부)은 일부러 **제외**한다. "수정 하나"의 대비를 지키기 위해서다. 사전 확인: f0f754d 코드만으로 `triples.json`에서 B를 다시 만들면 `ontology_B.ttl`, `tbox_B.ttl`, `abox_B.ttl`과 바이트 단위로 같다(확인함, LLM 호출 0회). 즉 빌드는 결정적이고 B와 B′의 차이는 slug 수정뿐이다.
- **한국어 술어를 번역하지 않는다.** 술어 89개 중 대부분(보고서 기준 81/89)이 한국어 그대로이며, 이것은 두 번째 교란이다. B′는 그것을 고치지 않는다. 따라서 B′의 결과는 "dedup 수정만의 효과"이고, B′가 낮아도 한국어 술어 교란이 남아 있다는 뜻일 수 있다.
- 타이핑 캐시는 B의 기존 캐시 6개를 복사해 쓴다(원본 불변). 적중하지 않으면 <internal-proxy> judge 모델로 호출하고 호출 수를 보고한다.

## 21.3 Judge와 이유

원래 judge(Qwen3-Next-80B-A3B-Instruct-FP8 @ <ip-address>)는 서버가 내려가 있다. 대체로 **`local/qwen-next-flash`(<internal-proxy>, `http://<local-endpoint>/v1`)** 를 쓴다. 원래 judge와 다른 모델이므로 **원 결과(B 0.0%, C 5.6%, A 77.8%)와 절대 수치를 비교하지 않는다.** 공정성을 위해 A, B, C, B′ **네 변형 모두를 같은 judge로, 새 캐시 디렉터리에서 다시 채점한다**(캐시 키에 모델과 CQ 텍스트가 없으므로 기존 캐시는 쓰지 않는다). 온도 0, JSON 모드, 동일 rubric(`eval_ab`), NUM_JUDGES = 2, 동시 worker 3 이하, 토큰 예산 1.5M(초과 시 중단).

## 21.4 질문 은행, 변형, 지표

- 은행: 기존 12문항 은행 `eval/competency_questions_mfg_ko.json`(sha256 1b570a91…, 파이프라인 팀이 작성, 수정하지 않음). **주 은행은 한국어**(언어 일치). 영어 은행 `eval/competency_questions_mfg.json`(f84f1d92…)은 **기술적 보조**로만 보고한다.
- 변형: A(`ontology_A.ttl` d743bbf9…), B(9f5948b3…), C(bdb16f7f…), B′(새로 빌드). 입력 TTL은 변경하지 않는다.
- 지표: 변형별 Coverage = L1 점수 합 / (3 × 12). 질문별 점수는 judge 2회 평균의 반올림(0–3), `eval_ab.aggregate_cq`와 같다. L2 품질은 기술적으로만 보고한다.
- **주 대비(1개): B′ − B**, 한국어 은행, 질문 수준 쌍 부트스트랩(12개 질문 쌍 차이, 복원추출 10,000회, 시드 20261014, 백분위 95% 구간). 다중성 보정은 하지 않는다(대비 1개, 탐색적).
- 기술적 비교(추론 없음): A, B, C, B′ 각각의 Coverage; B′−A, B′−C, A−B, C−B의 같은 부트스트랩 구간; 영어 은행에서의 같은 표; B와 B′의 그래프 통계(노드 수, 최대 차수, 허브 `ct:x` 존재 여부, 분류 계층 간선 수). n = 12이므로 구간은 넓고, 어떤 방향의 결과도 "확인"이라 부르지 않는다.

## 21.5 실행·산출물 위치와 제약

- 스크립트: `harness/r34_bprime/{build_bprime.py, score_bprime.py, analyze_bprime.py}`(이 동결에 포함). B′ 산출물 `output_mfg/r34_bprime/`, 결과 `harness/r34_bprime/`. 기존 출력은 덮어쓰지 않는다.
- 이 addendum은 `main.tex`와 부록을 고치지 않는다. 숫자는 보고만 하고 통합은 조정자가 한다.
- 이탈이 생기면 `REPORT_ko.md`에 사유와 함께 적는다.
