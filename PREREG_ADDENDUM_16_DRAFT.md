# PREREG addendum 16 — 술어 정렬을 포함한 표준화 SPARQL 오라클 (실행 전 동결본)

> 이 파일이 동결 대상 본문이다. 동결 커밋과 태그(`access2026-addendum16-freeze`)가 이 파일의 상태를 고정한다. `PREREG.md`에는 합치지 않았다(`PREREG.md`는 이 작업에서 고치지 않는다). 나중에 합칠 때는 글자 그대로 `## 16.`으로 덧붙인다. 표기는 §12와 같다: (확인함) = 이 작성에서 파일·코드·출력을 직접 읽거나 실행해 확인한 것, [추정] = 근거를 밝힌 추론, [UNVERIFIED] = 확인하지 못한 것. 이 문서와 구현 코드는 AI가 작성했다. 저자 검토와 테스트 전에는 원고나 다른 분석에 쓰지 않는다.

## 16. [2026-10-13 addendum] 술어 정렬을 포함한 표준화 SPARQL 오라클 — 매핑 적용 결과를 보기 전에 동결한다

### 16.0 시점

이 addendum은 2026-10-13에, §15(IOF)와 별개로, 다음을 모두 알고 난 뒤에 쓴다.

- 기존 ASK 오라클의 결과: 18 CQ × 6 변형 = 108회 중 true 7, false 63, not_evaluable 38(`harness/real_run/ask_alignment/ask_results.json`; 사후·탐색적 실행). §7(L894–937)의 사전등록 질의는 108/108 false였다.
- 그 결과의 원인 분해: B–F의 false 55개 중 30개는 변형 그래프에 triple이 0개인 술어를 요구하고, 25개는 `rdfs:subClassOf`에 의존했다(`ask_alignment/README.md`, 확인함).
- Brick 홀드아웃의 judge 점수, AH 라벨, 독립 평가자 라벨의 존재. 저자와 이 작업 세션은 G1 결과(4/33)를 안다. 이 등록의 규칙(임계값 포함)은 그 결과를 의식하고 정해졌다.

따라서 이 실험은 **등록 후 실행하지만 주 분석 외의 사후 보강**이다. 확증 분석도 게이트도 아니며 어떤 G도 이 결과로 바뀌지 않는다. 사전등록의 지위는 "결과를 몰랐다"가 아니라 아래 순서에서 나온다: 매핑표·질의·결정 규칙 동결 → 그 뒤에 변형 그래프에 재작성 질의를 처음 실행.

**동결 전에 열람한 것(전부).**
1. 변형 6개 그래프의 술어 목록과 술어별 triple 수(확인함: `rdflib`로 집계만; 질의를 실행하지 않았다). 이 목록이 16.2의 매핑 후보의 근거다.
2. `bank/ask_queries/CQB01–CQB36.rq`, `bank/cq_bank_brick_v1.csv`.
3. 라벨 시트 파일의 앞 2–3행(열 이름과 형식 확인용): `annotation/labeling_sheet_key_2026-10-13.csv`, `annotation/second_pass_2026-10-13/v3/labels_v3.csv`, `harness/real_run/cells.jsonl`. 라벨 값을 집계하거나 오라클과 결합하지 않았다.
4. `ask_alignment.py`, `ask_alignment/README.md`와 위 기존 결과(집계).

**동결 전 금지 사건.** 다음이 하나라도 일어나면 이 addendum은 사전등록이 아니다.
- 매핑표(`predicate_map.csv`)나 v2 질의(`bank/ask_queries_v2/`)를 변형 그래프 6개 중 어느 것에든 적용·실행해 outcome(true/false/not_evaluable)을 본다.
- 재작성 질의의 outcome과 J·S_AH·S_독립의 결합을 본다.
- 매핑 규칙(16.2)이나 결정 규칙(16.4)을 그런 열람 뒤에 바꾼다.
동결 전 v2 질의는 문법 검사(`prepareQuery`)만 했고 어떤 그래프에도 실행하지 않았다(확인함). 동결 뒤에 규칙을 바꾸려면 원문을 남기고 새 addendum으로 덧붙이며, 실행 시작 뒤의 변경은 "결과를 본 뒤의 개정"으로 표시한다.

### 16.1 목적과 결정 DN16

**목적.** 질의 어휘(Brick: `rdfs:subClassOf`, `owl:inverseOf`, `skos:definition` 등)와 변형 어휘(파이프라인이 만든 `ex:` = `http://example.org/chunktograph#` 술어, `skos:broader` 등)의 불일치를 결정적 술어 매핑으로 해소한 뒤, SPARQL 오라클이 judge와 AH 라벨에서 독립한 기준으로 기능하는지 본다. 기능의 정의는 16.4다.

- **DN16-1 CQ 분류.** 결정적 18 = `ask_expressible == yes`(CQB07–18, 21–24, 32, 33). 전문가 필요 18 = `partial`(CQB01–06, 19, 20, 25–31, 34–36). 전문가 필요 18개는 outcome 분포만 보고하고 라벨·judge와 결합하지 않는다. 근거: `partial`은 질의가 CQ의 일부(존재 확인)만 검사하므로 일치도를 정의할 수 없다.
- **DN16-2 모호한 술어.** `ex:p_is`, `ex:p_is-a`, `ex:p_be`, `ex:p_is-an`, `ex:p_are`는 **보수적으로 제외**한다(규칙 X1–X5). 사유: 추출된 계사(copula) 동사는 하위분류, 유형 소속, 느슨한 서술을 모두 담을 수 있다. subClassOf로 매핑하면 본문 문장이 스키마 수준 질의를 충족시켜 오라클이 true로 기운다. 오라클의 false 쪽 오류(누락)가 true 쪽 오류(과대 인정)보다 이 연구의 질문에 덜 해롭다. "둘 다 허용" 민감도는 실행하지 않는다.
- **DN16-3 `skos:broader`.** `rdfs:subClassOf`의 후보로 포함한다(P2, 저자 지정). 한계: B–D에서 `skos:broader`의 많은 object가 `section_*` 노드이지만 질의의 object는 항상 고정된 Brick 용어이므로 영향은 없다 [추정, 실행으로 확인].
- **DN16-4 `owl:inverseOf` 대칭.** `ex:p_inverse`는 양방향을 허용한다. `owl:inverseOf` 자체에는 대칭 확장을 더하지 않는다(변형 A의 결과를 v1과 가능한 한 같게 둔다).
- **DN16-5 질의 표준화.** 36개 질의를 `bank/ask_queries_v2/`로 복사한다. 형식은 모두 ASK로 유지하고(rdflib가 36개 모두 처리하므로 SELECT-존재 확인으로 바꿀 필요가 없다), 변경은 (i) 출처·표준화 두 줄의 주석 머리, (ii) `PREFIX rdf:` 추가, (iii) 동사 `a`를 `rdf:type`으로 쓰기(CQB19–24)뿐이다. 본문은 그 밖에 바이트 단위로 같다(확인함: 스크립트 대조). `bank/ask_queries/`는 고치지 않았다.
- **DN16-6 outcome 정의와 비교 기준.** 16.3.
- **DN16-7 결정 규칙의 수치.** 16.4: not_evaluable ≤ 10%, κ ≥ 0.4(S_AH와 S_독립 각각), 최소 평가 가능 셀 20. 수치는 이 작업 세션이 제안했고 저자가 따로 승인하지 않았다. 임계값이 어느 방향으로 정해졌는지는 16.4 말미에 적는다.
- **DN16-8 구간.** κ는 cluster(CQ) BCa 95%(기존 `analyze_holdout.cluster_bootstrap_stat`, B = 10,000, 시드 20260913)로 보고하되 판정에 쓰지 않는다. 일치도는 cluster 단위 단측 97.5% Clopper–Pearson(`analyze_holdout.clopper_pearson_upper`)도 보고한다.
- **DN16-9 판정 모집단.** 결정적 18 CQ × 변형 B–F(90회). 변형 A는 구조가 달라(개체 0, 스키마형 그래프, Brick 어휘 그대로) 별도 행으로 보고하고 판정에 넣지 않는다. A를 포함한 108셀 pooled는 기술용이다.
- **DN16-10 지위.** 탐색적·사후 보강. 모든 출력에 "탐색적(exploratory), 사후" 표지를 붙인다. AH 라벨은 AI 초안·저자 수정 라벨이고 judge는 gemini-3.6-flash다. 독립 평가자 라벨은 `labels_v3.csv`의 `S_label`이다(저자가 독립 평가자 라벨로 지정, 외부에서 받은 자료이며 이 세션이 독립성을 검증하지 않았다 [UNVERIFIED]).
- **DN16-11 보조 민감도.** "술어 부재 제외": false이면서 `predicate_absent`로 표지된 셀(16.3)을 평가 가능 집합에서 뺀 κ·일치도를 병기한다. 판정에는 쓰지 않는다.
- **DN16-12 시드·결정성.** 16.6.

### 16.2 동결 대상 (a): 술어 매핑표

`harness/real_run/ask_alignment_v2/predicate_map.csv`(동결 대상, 18행)가 규칙의 정본이다. 요약:

| 규칙 | 상태 | 질의 술어 ← 변형 술어 | 방향 | 근거(한 줄) |
|---|---|---|---|---|
| P1 | 적용 | `rdfs:subClassOf` ← `ex:p_subclass` | 정방향 | 파이프라인의 "하위분류" 관계, subject가 하위 |
| P2 | 적용 | `rdfs:subClassOf` ← `skos:broader` | 정방향 | SKOS 계층 간선, subject가 하위; B–F의 계층 간선 |
| P3 | 적용 | `owl:inverseOf` ← `ex:p_inverse` | 대칭 | 역관계 술어; owl:inverseOf가 대칭이라 양방향 허용 |
| P4 | 적용 | `skos:definition` ← `ex:p_define` | 정방향 | 정의를 담는 관계 술어 |
| P5 | 적용 | `rdfs:label` ← `ex:p_label` | 정방향 | 레이블 문자열을 담는 술어 |
| P6 | 적용 | `rdfs:label` ← `skos:prefLabel` | 정방향 | B–F의 레이블 술어 |
| P7 | 적용 | `rdf:type` ← `ex:p_class-schema` | 정방향 | 저자 지정 type 대응 |
| P0 | 항등 | `skos:definition` ← `skos:definition` | — | E·F는 그대로 사용, 재작성 없음 |
| X1–X5 | 제외 | `rdfs:subClassOf` ← `p_is-a`, `p_is`, `p_be`, `p_is-an`, `p_are` | — | DN16-2 |
| N1–N5 | 대응 없음 | `rdfs:comment`, `owl:disjointWith`, `sh:path`, `sh:class`, `rdfs:subPropertyOf` | — | 대응 술어를 등록하지 않음 |

**적용 규칙 수 7**(P1–P7), 항등 1, 제외 5, 대응 없음 5. P5·P6은 36개 질의가 `rdfs:label`을 쓰지 않으므로 발동하지 않고 P7은 `rdf:type`의 object가 `owl:ObjectProperty`·`owl:Class`·`brick:EntityProperty`뿐이라 변형의 `ex:p_class-schema` triple(object는 `ex:schema`)과 만날 일이 없다 [추정, 실행 로그의 `predicate_map_applied`로 확인]. 이 규칙들을 목록에서 빼지 않는 이유는 지정된 후보를 그대로 동결하기 위해서다.

**재작성 방식(그래프 불변).** 질의 본문에서 술어 위치의 규칙 대상 IRI를 SPARQL 속성 경로 대안으로 바꾼다. 예: `?c rdfs:subClassOf brick:Point` → `?c (rdfs:subClassOf|ex:p_subclass|skos:broader) ct:brick-point`; `A owl:inverseOf B` → `A (owl:inverseOf|ex:p_inverse|^ex:p_inverse) B`; `X skos:definition ?d` → `X (skos:definition|ex:p_define) ?d`; `X rdf:type C` → `X (rdf:type|ex:p_class-schema) C`. 변형 A에도 같은 재작성을 쓰되 A에는 `ex:` 술어가 없어 결과가 달라지지 않는다(확인은 실행에서; 달라지면 보고한다). 대응 없는 술어(N1–N5)는 그대로 둔다.

### 16.2.1 적용 순서

기존 6단계(`local_exact` → `local_normalized` → `local_joined` → `label` → `label_to_local` → `ns_prefixed_local`, `ask_alignment.py`)를 용어에 그대로 적용한 **뒤에** 7단계 `predicate_map`을 적용한다. 6단계까지의 용어 매핑·모호성 처리·not_evaluable 규칙은 바꾸지 않는다. 용어 매핑을 다시 하지 않으므로 7개 미매핑 용어(B–F)는 여전히 not_evaluable의 원인이다.

### 16.3 결과 지표 (c)

**outcome(질의·변형 쌍마다).** `true` / `false` / `not_evaluable`.
- `not_evaluable`: 질의의 Brick 용어 중 하나가 6단계까지 `unmapped` 또는 `ambiguous`일 때(v1과 같다). 술어 매핑 때문에 not_evaluable이 되는 일은 없다.
- `false`: 평가 가능하고 재작성 질의가 ASK false. 이때 질의가 쓰는 술어 중 변형 그래프에서 (원래 술어 + 매핑된 대안 술어)의 triple 합이 0인 것이 있으면 `predicate_absent`로 표지하고 술어 이름을 기록한다.
- `before` = 6단계까지만 적용한 v2 질의의 outcome(결정적 18개는 v1 `ask_results.json`과 일치해야 한다; 불일치하면 구현 오류로 보고한다). `after` = 7단계까지 적용한 outcome. 정렬 전후 비교는 이 두 열이다.

**보고 항목.**
1. 변형별 outcome 분포(true/false/not_evaluable), before와 after, 결정적 18과 전문가 필요 18 각각(전문가 필요 18은 여기까지).
2. 정렬 전후로 outcome이 바뀐 (CQ, 변형) 쌍의 목록과 전이 표.
3. 결정적 18 CQ × 변형의 primary 셀 중 after가 평가 가능한 셀에서: 오라클(true=1) 대 (a) 판정 J ≥ 2, (b) S_AH(`labeling_sheet_key_2026-10-13.csv`), (c) S_독립(`v3/labels_v3.csv`의 `S_label`)의 2×2 표, 단순 일치율, Cohen κ(+BCa), cluster 단위 일치 단측 CP 구간. 기준선으로 같은 셀에서 κ(S_AH, S_독립), κ(J ≥ 2, S_AH)를 낸다. 변형별(A는 별도 행, B–F pooled, 108셀 pooled).
4. 정렬 후에도 남는 미매핑 용어와 `predicate_absent` 술어의 목록·개수.
5. DN16-11의 민감도.
J는 `harness/real_run/cells.jsonl`에서 읽고 `labeling_sheet_key`의 J 열과 대조한다. 두 값이 다르면 중단한다.

### 16.4 결정 규칙 — "오라클이 독립 기준으로 기능한다"의 사전 정의

판정 모집단은 결정적 18 CQ × 변형 B–F(DN16-9). 다음 네 조건을 **모두** 만족하면 "기능"이다.

- **C0 비상수.** 평가 가능한 B–F primary 셀에서 오라클 outcome이 true와 false를 모두 가진다. 상수면 κ가 0이거나 정의되지 않아 일치도로 쓸 수 없다. 평가 가능한 B–F primary 셀이 20개 미만이면 "판정 불가"다(DN16-7).
- **C1 평가 가능성.** 결정적 18 × B–F 90회 중 `not_evaluable`의 비율 ≤ 10%(after 기준).
- **C2 AH 라벨과의 일치.** κ(오라클, S_AH) ≥ 0.40.
- **C3 독립 평가자와의 일치.** κ(오라클, S_독립) ≥ 0.40.

**판정 범주.** 기능 = C0∧C1∧C2∧C3. **부분 기능** = C0∧C2∧C3이지만 C1 불충족(평가 가능한 곳에서는 일치하나 적용 범위가 부족). **불기능** = 그 밖. 판정 불가는 C0의 20개 하한 미달 때만이다. κ가 정의되지 않으면 해당 조건은 불충족이다.

**방향 선언.** C1은 용어 매핑을 바꾸지 않기 때문에 v1의 B–F not_evaluable(18개 중 7개 = 39%)이 거의 그대로 남는다 [추정, v1 결과를 안 상태에서 정함]. 따라서 "기능"은 도달하기 어려운 범주이고 "부분 기능" 여부가 실질적 질문이다. 0.4는 "보통(moderate)" 일치의 관례적 하한을 따랐고 10%는 이 세션이 제안한 수치다. 두 수치 모두 결과를 본 뒤에 조정하지 않는다.

**이 실험의 한계를 해석에 미리 묶는다.** 결정적 18 중 B–F primary 셀은 변형당 15개 안팎이고 v1에서 오라클이 true인 셀은 변형 A에만 있었다. 평가 가능한 셀이 적으면 κ 구간이 넓다. 판정은 점추정으로 하되 구간을 같이 보고한다.

### 16.5 구현과 테스트 (실행 전 약속)

- 구현: `harness/real_run/ask_alignment_v2/run_oracle_v2.py`가 `ask_alignment.py`를 import해 6단계를 그대로 쓰고, 7단계 `predicate_map`을 질의 재작성으로 추가한다. 그래프는 바꾸지 않는다. 입력: `bank/ask_queries_v2/`, `predicate_map.csv`, 변형 그래프 `harness/variants/{A..F}/graph_*.ttl`.
- 출력: `ask_results_v2.json`(`ask_results.json`의 스키마 + `predicate_map_applied` + `per_cq_variant`의 `before_outcome`·`after_outcome`), `mapping_v2.csv`, 비교표.
- 테스트: `harness/test_ask_alignment_v2.py` — 매핑 규칙 단위 테스트(합성 그래프), `before`가 v1과 일치하는지, 두 번 실행한 결과의 바이트 동일성.
- 동결 뒤 코드의 버그 수정은 규칙(16.2–16.4)을 바꾸지 않는 한 허용하며, 수정 diff를 보고서에 적는다. 규칙을 바꾸는 수정은 새 addendum이다.
- 이 코드는 사람이 검토하고 테스트하기 전에는 다른 분석에 쓰지 않는다.

### 16.6 시드·결정성 (e)

난수는 BCa 부트스트랩에서만 쓰며 B = 10,000, 시드 20260913(기존 등록값)을 `analyze_holdout`과 같이 쓴다. 다른 단계는 결정적이다. 출력 JSON은 시각을 담지 않고 키를 정렬한다. 같은 입력에서 두 번 실행한 바이트 동일성을 테스트로 확인한다. 실행 환경(Python, rdflib, scipy 버전)과 입력 파일의 sha256을 출력에 기록한다.

### 16.7 변경되지 않는 것

- §1–§14의 모든 등록된 정의, 임계값, 게이트(G1–G8)와 그 결과.
- 사전등록 ASK 질의(`bank/ask_queries/`)와 §7의 108/108 false 기록.
- 기존 사후 정렬(`ask_alignment/`)의 파일과 결과. v2는 별도 디렉터리에 쓴다.
- 잠긴 라벨, 변형 그래프, `cells.jsonl`.
- 이 실험의 결과는 확증 분석의 어떤 결정에도 들어가지 않는다.

### 16.8 결정 체크리스트

- [x] DN16-1 결정적 18 / 전문가 필요 18 분류(`ask_expressible`).
- [x] DN16-2 `p_is`·`p_is-a`·`p_be`(+`p_is-an`, `p_are`) 보수적 제외.
- [x] DN16-3 `skos:broader` 포함.
- [x] DN16-4 `ex:p_inverse`만 양방향.
- [x] DN16-5 ASK 유지, `a`→`rdf:type`, `bank/ask_queries_v2/`.
- [x] DN16-6 outcome 정의, before/after.
- [x] DN16-7 C0–C3, 수치(10%, 0.4, 0.4, n ≥ 20).
- [x] DN16-8 BCa·CP 구간은 보고만.
- [x] DN16-9 판정 B–F, A 별도 행.
- [x] DN16-10 탐색적·사후 보강.
- [x] DN16-11 술어 부재 제외 민감도(판정 외).
- [x] DN16-12 시드 20260913, 결정성 테스트.
- [ ] 저자 검토: 위 모든 수치와 DN16-2 (이 세션이 정했고 저자는 개별 승인하지 않았다).
