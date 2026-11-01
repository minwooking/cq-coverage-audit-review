# PREREG addendum 17 — 동결본 (2026-10-13)

> **이 addendum은 2026-10-13에 동결한다**(동결 커밋·태그는 17.7). `PREREG.md`에는 합치지 않고 별도 파일로 둔다. 판정 모델·표본 설계·예산은 17.0에 확정했다. 이 addendum의 코드와 계산은 사람이 검토하고 테스트하기 전에는 결과로 쓰지 않는다. 원고는 수정하지 않았다. 표기는 §12와 같다: (확인함) = 이 작성에서 파일·코드·출력을 직접 읽거나 실행해 확인한 것, [추정] = 근거를 밝힌 추론.
>
> 구현: `harness/length_experiment/{make_inputs,run_length_judge,analyze_length,test_length_experiment}.py`. 입력은 이미 생성했고(`inputs/manifest.jsonl` sha256 `46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32`, 두 번 생성해 같은 값, 확인함) **길이 실험 입력에 대한 판정 호출은 동결 전에 한 번도 하지 않았다**(`cells_length.jsonl` 없음, 확인함. 동결 전 호출은 17.0의 연결 확인용 소형·합성 호출뿐이며 길이 실험 입력을 쓰지 않았다).

## 17. [2026-10-13 addendum] 렌더링 길이 실험(실험 3) — 같은 그래프를 다른 입력 조건으로 판정해 judge 오류와 그래프 정보 부족을 분리한다

### 17.0 동결 결정 (2026-10-13)

- **judge 결정과 근거.** 등록 judge `gemini-3.6-flash`용 Google API 키가 이 머신에 있는지 점검했다: 환경변수 `HOLDOUT_JUDGE_API_KEY`·`GOOGLE_API_KEY`·`GEMINI_API_KEY`, 저장소와 `paper/access2026` 아래 `.env*`, `real_run/MANIFEST.json`, `<user-config-dir>`, `<agent-config-file>`의 env 블록. 사용할 키는 없었다(확인함; 값은 열람·기록하지 않았다). 따라서 **DN17-1은 (2) 대체 judge**로 확정한다.
- **대체 judge.** 모델 ID `gpt-6-astra`, <internal-proxy> 로컬 프록시(`http://<local-endpoint>/v1`, OpenAI 호환 chat/completions, 외부 API 키 없음), temperature 0.0, `max_tokens` 1024, 기존 `call_judge`·`RUBRIC` 그대로. 컨텍스트 창은 `/v1/models`가 872,000 토큰으로 보고했고(확인함), 사전 점검에서 A의 full 뷰(292,845자)가 통과했다(확인함, 소형·합성 질문, 길이 실험 입력 아님). 프록시 경로는 `response_format={"type":"json_object"}`일 때 입력 메시지에 소문자 "json"이 없다며 400을 반환했다(system 메시지의 "Return JSON:"은 인정하지 않음, 확인함). 그래서 **디코딩 편차**로 `response_format`을 `{"type":"text"}`로 덮어쓴다(`HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS`, 기존 `call_judge`의 `extra_top_level` 경로). 응답은 같은 `json.loads`로 파싱하며 RUBRIC은 JSON 출력을 요구한다. 파싱 실패는 무효 응답으로 센다. **이 judge는 등록 judge(`gemini-3.6-flash`)나 기존 holdout judge와 다르므로 기존 holdout과 직접 비교할 수 없다.** 결과는 "이 judge에서의 길이 효과"이며 등록 judge의 오류율에 대한 증거가 아니다.
- **표본 설계(DN17-2).** 축소안(B): full은 variant A만, limited와 subgraph는 전 variant. `--design reduced`. 호출 393(full 23, limited 188, subgraph 182; subgraph 적용불가 6 제외). 선택지 C(기존 full 재사용)는 judge가 다르므로 쓸 수 없다. B–F의 full 조건은 이 실험에서 판정하지 않는다. 컨텍스트 창은 B–F full(호출당 49만–60만 토큰 추정)을 받을 수 있지만 7M 토큰 상한 때문에 제외했다.
- **제외(DN17-3).** holdout의 documented exclusion 28쌍은 보내지 않는다(`--include-excluded` 없음).
- **보고 규칙(DN17-4).** 17.6 그대로: 기술 통계 + CQ-cluster BCa 95% 구간. 가설 검정·동등성 마진 없음.
- **예산(DN17-5).** 누적 추정 입력 토큰 상한 7,000,000(문자/4 올림 추정). 사전 추정 합계 6,294,174. 실행 중 초과하면 새 호출을 멈추고 보고한다. `--workers 3`. 호출 100건마다 `progress.log`에 누적 추정 토큰과 실패 수를 남긴다. 단가는 쓰지 않는다.
- **재현성(DN17-6).** judge 변경으로 기존 `cells.jsonl`의 J를 재사용하지 않는다. A의 full 23셀은 이번 judge로 새로 판정하며, 기존 holdout J(다른 judge)와의 일치율은 참고로만 보고한다.
- **manifest.** `harness/length_experiment/inputs/manifest.jsonl` sha256 `46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32`(동결 시점에 재계산해 일치함, 확인함). 입력 본문(`inputs/*/*/*.txt`, 약 22MB)은 커밋하지 않고 manifest의 항목별 sha256으로만 고정한다.

### 17.1 목적

holdout의 judge 입력(`rendered_view`)은 variant B–F에서 약 195만–241만 자(추정 49만–60만 토큰)이고 A는 약 29만 자다(`wc -c`, 확인함). 이 길이에서 낮은 점수가 (i) 그래프에 근거가 없어서인지 (ii) 긴 입력에서 judge가 근거를 놓쳐서인지 지금의 데이터로는 가를 수 없다. 이 addendum은 **같은 그래프, 같은 질문, 같은 rubric과 디코딩**으로 입력 길이·범위만 바꿔 판정해 두 설명을 가르는 탐색적 실험을 등록한다. 확증 가설은 없다. 결과는 기술 통계와 구간으로 보고한다(17.6). 이 addendum은 §1–§16의 어떤 항목도 고치지 않으며 primary 결과의 지위를 바꾸지 않는다.

### 17.2 조건 정의 (코드와 같은 규칙, 그대로 등록)

세 조건 모두 같은 질문 텍스트와 같은 `RUBRIC`(`run_holdout.RUBRIC`), 같은 `call_judge`(temperature 0, `max_tokens` 1024, `response_format=json_object`)를 쓴다. 판정 입력의 형식은 `ARTIFACT:\n{입력}\n\nQUESTION: {질문}`으로 holdout과 같다.

- **(a) full.** `harness/variants/<V>/rendered_view.txt`를 그대로 쓴다. 복사하지 않고 경로와 sha256으로만 참조한다(variant별 sha256은 `variants/MANIFEST.json`의 `rendered_view_sha256`).
- **(b) limited.** 뷰의 앞 60,000자. 절단 규칙: `head = view[:60000]`. 뷰가 60,000자 이하면 그대로 둔다. 초과하면, `view[60000]`이 개행이 아닌 경우 `head`를 마지막 개행 앞까지 줄이고(`head`에 개행이 없으면 그대로 둔다), 끝에 `"\n[truncated]"`를 붙인다. 문자는 Python `str`의 코드포인트로 센다. 이 규칙은 judge 호출 전에 고정한다. 규칙을 만든 뒤 어떤 항이 잘리는지 확인해 고치지 않는다(`RENDERING_SPEC.md` L102–108이 요구한 "사전 등록" 조건. 확인함). 이 초안 작성자는 절단 입력에 grounding 항이 남았는지 확인하지 않았다(확인함: 그런 코드를 돌리지 않았다).
  - 알려진 한계: 뷰는 IRI 순으로 정렬돼 있어 앞 60,000자는 알파벳 앞쪽 항만 담는다. limited 조건은 "잘린 항이 질문과 무관하게 정해진다"는 점에서 무작위 prefix이며, 이것이 RENDERING_SPEC L102–108이 경고한 "렌더러를 재는" 효과를 의도적으로 만든 조건이다.
- **(c) subgraph.** `graph_view.ego_graph`(깊이 2 BFS, 질문 토큰 `cq_tokens(question)`과 노드 이름·레이블 매칭, 노드 상한 120, 뿌리 상한 25)로 뽑은 서브그래프를 **같은 렌더러**(`run_simulated.schema_view`)로 텍스트화한다. 구성: 선택된 노드 집합 S에 대해, 주어가 S인 트리플 중 (객체가 리터럴) 또는 (술어가 `rdf:type`) 또는 (객체가 S)인 것만 임시 Turtle에 담고, 그 파일에 `schema_view`를 적용한다. 그래서 줄 형식·정렬·접두어가 full 뷰와 같다(테스트가 서브그래프의 모든 줄이 전체 그래프 렌더링의 줄 집합에 속함을 확인함).
  - **정답 누수 차단.** 서브그래프 추출은 질문 문장만 받는다. 은행은 `load_questions`로 `cq_id/question/cluster_id/category` 네 열만 읽고 `grounding`·`expected_answer` 열은 버린다. `ego_graph`의 judge 증거 인자는 항상 빈 값이다. 테스트 3개가 이를 고정한다: 열 이름이 추출 코드에 나오지 않음, 두 은행이 `grounding`·`expected_answer`만 다를 때 모든 입력의 sha256이 같음, 열이 제거됨(확인함, `test_length_experiment.py`).
  - **not_applicable.** 질문 토큰과 맞는 노드(뿌리)가 0개이거나 렌더 결과가 비면 이 셀은 subgraph 조건에 적용 불가이며 입력 파일을 쓰지 않고 판정하지 않는다. 실측: 6셀(A–CQB27, B–F의 CQB32). holdout의 28개 documented exclusion과 겹치지 않는다(확인함).
  - 주의: `rdf:type` 객체(예: `owl:Class`)가 허브이므로 깊이 2 이웃이 노드 상한 120까지 차는 경우가 많다(뿌리 25개가 169/216셀, 확인함). subgraph 입력은 "근거만 추린 입력"이 아니라 "질문 어휘 주변의 상한 있는 이웃"이다.
- 기록: `inputs/manifest.jsonl`에 변형×CQ×조건별 문자 수, 추정 토큰 수(= ⌈문자/4⌉, 추정이며 실제 토크나이저 값과 다르다. URL이 많은 텍스트는 더 많게 나올 수 있다), 매칭 노드 수, sha256, 원본 뷰 sha256, 절단 여부, documented exclusion 여부.
- 참고(확인함): `schema_view(graph_B.ttl)`은 `variants/B/rendered_view.txt`와 바이트 단위로 같다. A는 다르다(`schema_view(graph_A.ttl) != rendered_view.txt`; `test_domain_regression.py`가 A를 제외하는 이유와 같다). 따라서 A의 subgraph 조건은 A의 full 뷰와 정확히 같은 렌더러가 아니라 현재 `schema_view`를 쓴다. 이 차이는 A의 조건 간 대조 해석 시 보고한다.

### 17.3 판정 모델 선택지 (⚖ DN17-1, 저자 결정 대기)

| | (1) 등록 judge 유지 | (2) <internal-proxy> 대체 judge |
|---|---|---|
| 모델 | `gemini-3.6-flash`, `generativelanguage.googleapis.com`, `thinking_level=minimal`(`real_run/MANIFEST.json`, 확인함) | <internal-proxy>(:PORT) 경유 모델 `gpt-6-astra` |
| 장점 | holdout과 같은 judge이므로 full 조건 점수를 기존 `cells.jsonl`에서 가져올 수 있다(17.4 선택지 C). 조건 효과만 분리된다. | 외부 API 비용과 한도가 없다. |
| 함의 | 같은 judge의 입력 길이 효과만 잰다. 외부 API 키·비용·한도는 예산 상한은 17.0. | **기존 holdout과 직접 비교할 수 없다.** judge와 입력 조건이 동시에 바뀌므로 기존 `cells.jsonl`의 full 점수를 쓸 수 없고 full 조건도 같은 대체 judge로 다시 돌려야 한다. 결과는 "그 judge에서의 길이 효과"이며 등록 judge의 오류율에 대한 증거가 아니다. |
| 제약 | 없음. full B–F 입력이 호출당 약 49만–60만 토큰이어도 holdout에서 이미 처리했다. | 컨텍스트 창이 문제다. full B–F는 호출당 약 49만–60만 토큰(아래 17.5)이라 창 262k 급 모델은 받을 수 없다. [추정: 메모리 기록상 로컬 qwen 계열 창 262k, 이 세션에서 모델 창 값을 직접 확인하지 않았다] 그 경우 full은 A(호출당 약 7.3만 토큰)만 가능하며 표본 설계는 축소안(17.4 B)으로 강제된다. |

어느 쪽이든 판정은 `run_length_judge.py`로 하고, 엔드포인트와 모델은 CLI·환경변수로 지정한다. 동결 시 선택한 모델 ID·엔드포인트·디코딩·`extra_body`를 §15.2와 같은 freeze 표에 적는다.

### 17.4 표본 설계 선택지 (⚖ DN17-2)

대상 셀은 6 variant × 36 CQ = 216 (variant, CQ) 쌍이다. holdout과 같이 documented exclusion 28쌍은 보내지 않는 것을 기본으로 한다(⚖ DN17-3, 기본값: 제외; `--include-excluded`로 바꿀 수 있다). 그러면 primary 쌍은 188이다.

- **A. 전체안.** 6×36×3. 호출 558(제외 28쌍, subgraph 6 적용불가 제외; 제외를 포함하면 642).
- **B. 축소안.** full은 A variant만, limited와 subgraph는 전 variant. 호출 393(제외 28쌍 기준).
- **C. 기존 full 재사용(선택지 (1)에서만 가능).** full 조건은 판정하지 않고 `real_run/cells.jsonl`의 primary J를 쓰고, limited와 subgraph만 새로 판정한다. 호출 370. 한계: holdout 점수는 2026-09-21 실행이고 이번 실행은 다른 날짜이며, 같은 temperature 0이어도 API 쪽 비결정성이 있을 수 있다. 이 차이는 full−limited, full−subgraph 대조에서 혼입된다.

호출 순서는 시드 `20260913`으로 섞는다(`run_length_judge.py`, 확인함). 동시 호출은 3개 이하로 제한한다(코드가 거부함).

### 17.5 비용 추정 (dry-run 수치, 추정 토큰 = 문자/4)

`run_length_judge.py --dry-run`의 출력(확인함; 판정 입력 전체 = RUBRIC + 입력 + 질문, 문자/4 올림, 모든 수치는 추정):

| 조건 | 전체안 호출 | 평균 입력 문자 | 입력 토큰 합계 | 축소안 호출 | 축소안 토큰 합계 |
|---|---|---|---|---|---|
| full | 188 | 2,054,341 | 96,571,531 | 23 (A만) | 1,685,986 |
| limited | 188 | 59,788 | 2,827,560 | 188 | 2,827,560 |
| subgraph | 182 (+6 적용불가) | 38,762 | 1,780,628 | 182 | 1,780,628 |
| 합계 | 558 | | 101,179,719 | 393 | 6,294,174 |

- 제외 28쌍을 포함하면(`--include-excluded`) 전체안은 642호출·111,395,040토큰이다.
- 선택지 C(full 재사용)는 limited+subgraph만 새로 판정하므로 370호출·약 4.6M토큰이다(2,827,560 + 1,780,628 = 4,608,188).
- full 조건 한 variant당 입력(호출당): A 약 7.3만, B 약 49만, C 약 60만, D 약 60만, E·F 약 59만 토큰.
- 금액은 단가를 이 세션에서 확인하지 않았으므로 쓰지 않는다 예산 상한은 17.0(입력 토큰 합계 7,000,000, 추정 토큰 기준). 출력 토큰은 호출당 `max_tokens` 1024 이하다.
- 요점: 전체안 비용의 약 95%가 full 조건 한 곳에서 나온다. limited와 subgraph는 합쳐 약 4.6M토큰이다.

### 17.6 지표와 결정 규칙

**기술 통계와 구간만 등록한다. 가설 검정과 pass/fail 임계는 등록하지 않는다.** 예를 들어 "limited−full 차이 구간이 ±0.30 안이면 길이 효과는 무시할 수 있다"는 동등성 규칙은 이 표본에서 도달하기 어려울 수 있다. 정규 근사로 95% 반폭 0.30에 이르려면 CQ-cluster 평균 차이의 표준편차가 약 0.88 이하(33 cluster)나 0.73 이하(A, 23 cluster)여야 하며, 0–3 척도에서 조건을 바꾸면 한 단계 이상 움직이는 셀이 흔한 점을 생각하면 충족을 기대하기 어렵다 [추정, 정규 근사, 이 세션 계산]. 그래서 동등성이나 "무시 가능" 결론은 이 실험의 종점이 아니다. 보고할 것(`analyze_length.py`, 합성 데이터 테스트 통과, 확인함):

1. 조건별 J 분포(0–3 개수, 평균; 전체와 variant별), 무효 응답 수, not_applicable 수.
2. 같은 (variant, CQ) 셀의 조건 간 차이 full−limited, full−subgraph, limited−subgraph: 평균 차이와 CQ-cluster BCa 95% 구간(`analyze_holdout.cluster_bootstrap_delta`, 10,000 resamples, 시드 20260913; 90% 구간 병기).
3. 조건 간 QWK(`analyze_holdout._qwk_from_values`)와 정확 일치 비율.
4. **판정 오류 대 정보 부족 분리.** 사후 분석 단계에서만 은행의 `grounding` 열로 각 입력에 grounding 항이 들어 있는지 확인한다(`run_holdout._grounding_match_info(...)["can_ablate"]`; 입력 생성에는 쓰지 않음). subgraph(및 limited)에 대해 full에서 J≥2인 쌍 중 reduced 조건에서 J≤1인 쌍을 센다.
   - grounding이 reduced 입력에 있음 → `judge_error_candidate`(보여준 근거를 judge가 놓친 후보)
   - grounding이 reduced 입력에 없음 → `information_deficit`(입력이 근거를 담지 않아 낮아진 후보)
   - 반대 방향(reduced J≥2, full J≤1)은 `reduced_up`으로 따로 센다.
   이 분리는 문자열 일치(`can_ablate`) 휴리스틱에 의존한다. 일치가 없다는 사실은 "의미상 근거가 없다"를 뜻하지 않는다. 그래서 개수는 후보로 보고하고 원인 확정으로 쓰지 않는다.
5. 해석 규칙(기술 서술, 판정 아님): 이 결과는 등록 judge가 긴 입력에서 점수를 낮추는 경향의 증거나 반증이 아니다. 같은 셀의 조건 간 점수 이동의 크기와 구간을 보고하며, 원고 문장은 구간이 허락하는 범위로만 쓴다.

### 17.7 동결 전에 일어나면 안 되는 사건

동결(이 addendum의 커밋·태그 `access2026-addendum17-freeze`; 커밋 해시는 이 파일의 17.11에 두 번째 커밋으로 덧붙인다) 이전에는 다음이 없어야 한다.

1. 길이 실험 입력(`inputs/*/*/limited.txt`, `subgraph.txt`)에 대한 **판정 호출 1회 이상**. `cells_length.jsonl`의 생성. `run_length_judge.py`는 `--confirm-addendum17-frozen` 없이는 실제 호출을 거부한다(코드가 거부함, 확인함).
2. 그 judge 점수의 열람, `analyze_length.py`를 실제 셀에 돌리는 것.
3. 절단 규칙·서브그래프 규칙(17.2)을 judge 점수나 grounding 일치 결과를 본 뒤에 바꾸는 것.

동결 전에 이미 있어도 되는 것(사건 아님): 입력 생성(`make_inputs.py`)과 manifest(위 sha256), dry-run 토큰 합계, 합성 데이터 테스트. 입력 manifest의 sha256은 동결 때 다시 계산해 17.0에 적는다(동결 시점 값 `46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32`, 재계산해 일치 확인함)(코드나 은행·뷰가 바뀌면 값이 달라진다). 동결 뒤 이 addendum의 항목을 바꾸려면 원문을 남기고 새 addendum으로 덧붙인다.

### 17.8 변경되지 않는 것

§1–§16의 모든 등록 항목, holdout의 primary·control 셀 설계와 결과, 은행(`993c5e11…`), rubric(`d0c39758…`), 렌더링 사양(`eb0399af…`), 시드 20260913. 이 실험은 새 확증 대조를 만들지 않으며 Holm 가족에 들어가지 않는다.

### 17.9 결정 체크리스트

- [x] DN17-1 판정 모델: (1) 등록 judge `gemini-3.6-flash` 유지 / (2) <internal-proxy> 대체 judge `gpt-6-astra` — **선택: (2)**
- [x] DN17-2 표본 설계: **축소안(B)**
- [x] DN17-3 documented exclusion 28쌍: **제외**
- [x] DN17-4 보고 규칙: 기술 통계 + 구간(기본값). 동등성 마진은 등록하지 않는다
- [x] DN17-5 예산 상한 입력 토큰 7,000,000(추정). 단가는 쓰지 않는다
- [x] DN17-6 해당 없음(선택지 C 미채택). 대신 full 조건은 A만 새로 판정하고, 기존 holdout J와의 일치는 보고만 한다(17.0)

### 17.10 미정 항목 목록

없음. 모든 항목을 17.0과 17.11에서 확정했다.

### 17.11 동결 커밋

동결 커밋 `5dc054c8149c5e39a975185666cf1e4a5fe2204a`, annotated 태그 `access2026-addendum17-freeze`(이 해시를 가리킴). 이 줄은 동결 뒤 두 번째 커밋으로 덧붙였고, 17.0–17.10은 동결 커밋과 같다.

### 17.12 [2026-10-13] Judge change after freeze (이탈 D28)

**D28 — [동결 후 변경] 길이 실험의 judge를 `gpt-6-astra`에서 `gpt-5.6-luna`로 바꾼다(17.0 "대체 judge"로부터의 이탈).** 저자 지시(2026-10-13).

- **사유.** 동결 후 실행에서 업스트림 한도 때문에 `gpt-6-astra` 호출이 400/429로 계속 실패했다. 393호출 계획 중 유효 셀은 113개에 그쳤고(`cells_length_astra_partial.jsonl`), 나머지는 실패로 기록했다(`cells_length_failed_run1.jsonl`, `cells_length_failed_run2.jsonl`; 대표 오류: 400 "model not supported ... ChatGPT account"). 실행은 완주하지 못했다.
- **새 judge.** 모델 ID `gpt-5.6-luna`, <internal-proxy> 로컬 프록시(`http://<local-endpoint>/v1`, 외부 API 키 없음). 디코딩은 같다: temperature 0.0, `max_tokens` 1024. `response_format`은 프록시가 `json_object`를 거부할 때를 대비해 `{"response_format":{"type":"text"}}`로 덮어쓰고(`HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS`), 응답은 `json.loads`로 파싱한다. 파싱 실패는 무효 응답으로 센다.
- **astra 부분 결과 폐기, 전량 재판정.** astra의 유효 113셀은 분석에 쓰지 않고 새 judge 결과와 섞지 않는다. 파일은 증거로 보존하되 분석 입력에서 제외한다. 393셀 전부를 새 judge로 판정한다. 113셀의 astra 점수는 저장돼 있으나 분석하지 않았다(`analyze_length.py`를 실제 셀에 돌린 적 없음).
- **불변.** 설계(축소안 B, 393호출), 입력(manifest sha256 `46277713…ceaa32`), 조건 규칙(17.2), 지표와 보고 규칙(17.6), 예산 상한 7,000,000 토큰, 시드, `--workers 3`. 코드는 바꾸지 않는다.
- **한계.** 대체 judge(astra 이어 luna)라 등록 judge `gemini-3.6-flash`의 기존 holdout J와 직접 비교할 수 없다. 이 실험의 조건 간 차이는 같은 judge 안에서의 비교로만 읽는다.
