# PREREG — 동결 분석계획 (IEEE Access) [공개용 redacted 사본 — release/REDACTION_LOG.md 참조]

> **이 문서는 데이터 수집 전에 동결되는 분석계획이다.**
> 원고 §V가 아래 freeze 블록의 해시로 이 문서를 인용한다.
> 결과를 본 뒤에 이 문서를 고치는 것은 사전등록이 아니다 — 변경이 필요하면
> **원문을 남긴 채 개정 이력으로 덧붙이고, 개정이 결과를 본 이후였음을 명시**한다.

## Freeze block — 동결 시점에 채울 것

| 필드 | 값 |
|---|---|
| CQ bank SHA256 | `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507` (`cq_bank_brick_v1.csv`, 36행, 채점 대상) — **[2026-09-12 채움]** |
| Rubric SHA256 | `d0c397584bd62ca2ba62cf3833b1ad70862d6be22be52a4c3ffa111529756ebf` — `rubric/RUBRIC_L1.md`, extracted 2026-09-13; provenance and notation mapping are recorded in the artifact. |
| Randomization seed | `20260913` — constrained annotator cell-presentation order, bootstrap resampling, and any stratified draw; it does not govern frozen CQ-bank membership, labels, or human adjudication decisions. The frozen CQ bank itself remains the original 36 rows; no replacement draw is made. |
| Rendering spec SHA256 | `eb0399af5152ac001074f1a0c27b23652a42a2f9ceeebf95a669abf703ec0a3e` (`rubric/RENDERING_SPEC.md`, v2, instance-inclusive) — **[2026-09-13 채움, 2026-09-20 재동결]** 렌더링은 제시 방식이 아니라 프로토콜의 일부다(§6-1 참고). 2026-09-20: v1(스키마 전용)은 인스턴스 중심 아티팩트(chunktograph 파이프라인 산출 그래프)에서 콘텐츠 대부분을 렌더링에서 누락시키는 결함이 확인되어(`harness/variants/RENDERING_MISMATCH.md`), 원문 기록을 남긴 채 v2(인스턴스 포함)로 재동결했다. 동결 Brick v1.4.4 스냅샷 자체의 렌더링 뷰는 인스턴스가 0개라 v1/v2 바이트 동일 — 아래 "Rendered view SHA256" 값은 변경되지 않았다. |
| Rendered view SHA256 (Brick v1.4.4) | `2c3f6f50e0a147321fa4039c196a3c59908fd017565723a4b90bb0a128463b7c` (1,985행 / 259,186자) — **[2026-09-13 채움]** |
| Freeze timestamp (UTC) | `2026-09-12T12:22:32Z` — **[2026-09-12 채움]** |
| Git tag | `access2026-cqbank-brick-v1-freeze` — **[2026-09-12 채움]** |
| DOI of the deposit | `TBD (fill at freeze)` |
| Confirmatory judge (모델·엔드포인트·디코딩) | `qwen-next-flash` (`<internal-endpoint>`, OpenAI-호환 vLLM 서버, `temperature=0.0`, `response_format={"type":"json_object"}`, `max_tokens=1024`, `extra_body` 없음) — **[2026-09-12 최초 채움: `gpt-5.4` → 2026-09-20 재결정: `gemini-3.6-flash` → 2026-09-21 세 번째 재결정: `qwen-next-flash`, 사용자 명시 지시]** 아래 "Confirmatory judge 세 번째 재결정" 절 참고. **§threats에 self-enhancement 리스크 반영됨 (같은 Qwen 계열이 extraction과 judge를 겸함).** |

⚠️ **DOI 창작 금지.** 아카이브가 실제로 발급하기 전까지 `TBD`로 남긴다.
⚠️ answer key(judge 점수) 파일의 SHA256도 여기에 기록하되, **파일 자체는 평가자가 읽는
디렉터리 밖**에 둔다. 자가채점 저자에게 answer key 동거는 이론적 누출이 아니다.

**[2026-09-12] Confirmatory judge, 사전 고정.** 후보는 두 갈래였다: (a) `output_gpt/`가
쓴 경로 — `gpt-5.4`, `base_url=https://api.openai.com/v1`, `temperature=0.0`,
`response_format=json_object`, `max_tokens=1024`(harness 기본값), 표준 API 키 인증(디코딩
파라미터·엔드포인트 모두 리뷰어가 그대로 재현 가능). (b) `output_claude/`가 쓴 경로 —
`claude-sonnet-4-6`을 빈 `base_url`로 호출한 것으로 보아, 공개 가능한 표준 API 엔드포인트가
아니라 **내부/OAuth 전용 프록시 경로**로 라우팅된 것으로 판단된다. Access는 judge 모델을
"실명·디코딩 파라미터까지" 공개하도록 요구하며(제출 체크리스트 (12)), 내부 엔드포인트는 별도로
공개 전 스크럽 대상이다(체크리스트 (16)) — 즉 (b)는 애초에 논문에 실명으로 인용할 수 있는
경로가 아니다. **(a)를 채택한다: 새 Brick holdout의 confirmatory judge는 `gpt-5.4`
(`https://api.openai.com/v1`, `temperature=0.0`, JSON-mode, `max_tokens=1024`)로 사전
고정한다.** 이 판단은 extraction loop(Qwen3-Next-80B-A3B-Instruct-FP8) 및 continuity/sensitivity
전용 judge와 별개다.

⚠️ **아직 실행되지 않음 — 이름만 고정.** `output_gpt/`에 이미 있는 결과는 legacy pilot(A–F,
16-CQ) 채점 결과이며, 새 Brick holdout 채점에 대해서는 human annotator 확보 후 이 모델로
**fresh run**을 수행해야 한다(§2.4 참고). 이 문서는 "어느 모델을 쓸지"만 지금 확정하고,
"그 모델이 무엇이라 답했는지"는 아직 관측되지 않았다 — 사전등록의 취지가 그것이다.

**[2026-09-20] Confirmatory judge 재결정 — `gpt-5.4`를 `gemini-3.6-flash`로 대체한다.**
위 [2026-09-12] 절은 지우지 않는다 — 그 (a)/(b) 논증 구조(공개 재현 가능한 표준 API
엔드포인트만 인용 가능, 내부/OAuth 프록시 경로는 실명 인용 불가)는 그대로 유효하며, 오늘
바뀐 것은 (a) 갈래 안에서 고른 **구체적 provider**뿐이다. 사용자가 오늘 이 결정을
직접 뒤집었다: OpenAI API 키를 확보하지 못해 `gpt-5.4`로 confirmatory judge를 실행할
방법이 없다는 것이 이번에 확인되었고, 대안으로 **Gemini 3.6-flash**를 명시적으로
지시했다.

*새 judge 스펙 (확인함 — 웹 검색, Google 공식 문서 `ai.google.dev/gemini-api/docs/openai`
및 `ai.google.dev/gemini-api/docs/latest-model`, 2026-09-20 조회 기준):*
- **모델 ID**: `gemini-3.6-flash` — Google이 2026-07-21 공개한 GA(generally available)
  Flash-tier 모델.
- **엔드포인트**: Google은 표준 OpenAI-호환 레이어를 공식 제공한다 —
  `base_url=https://generativelanguage.googleapis.com/v1beta/openai/`, 실제 요청 경로는
  `{base_url}/chat/completions`이며 request/response shape이 OpenAI Chat Completions와
  동일하다. 이는 `harness/run_holdout.py`가 이미 보내는 요청 형태
  (`endpoint.rstrip('/') + '/chat/completions'`, `Authorization: Bearer <key>` 헤더,
  `messages`/`temperature`/`max_tokens`/`response_format` 바디)와 그대로 맞아떨어진다 —
  네이티브 REST 스키마(`x-goog-api-key` 헤더, `:generateContent` 경로)로 전환할 필요가
  없다.
- **`temperature=0.0`**: OpenAI-호환 레이어가 `temperature`를 direct pass-through한다 —
  변경 없이 유지 가능(확인함).
- **JSON-mode**: gpt-5.4와 동일하게 `response_format={"type":"json_object"}`로 유지
  가능하다. Google 공식 마이그레이션 문서(Gemini Enterprise Agent Platform, OpenAI 라이브러리
  호환 절)는 이 레이어에서 `response_format`의 `json_object` 값이 "Gemini API에
  `application/json`을 전달하는 것으로 해석된다"고 명시한다(확인함) — Gemini 쪽 네이티브
  파라미터인 `response_mime_type`으로 바꿀 필요가 없다. (개발자 포럼 게시글 하나는 이
  레이어의 *batch(비실시간)* 모드가 `json_schema`류 스키마를 거부한다고 보고하지만,
  harness는 realtime 호출만 사용하므로 무관하다 — 다만 이 세부는 2차 출처이므로 실제
  연결 테스트로 재확인이 필요하다.)
- **`max_tokens=1024`**: Google 공식 문서는 OpenAI의 `max_tokens`(및 별칭
  `max_completion_tokens`)를 Gemini 네이티브 `generationConfig.maxOutputTokens`로 직접
  매핑한다고 명시한다(확인함) — 파라미터 이름과 의미 모두 gpt-5.4와 동일하게 유지된다.

*gpt-5.4에는 없던 축 — thinking budget (item 5, 코드에도 반영함):* Gemini 3 계열
모델은 기본적으로 내부 "thinking"이 켜져 있고(`gemini-3.6-flash`의 기본
`thinking_level`은 `MEDIUM`), **thinking에 쓴 token이 같은 `max_tokens`/
`maxOutputTokens` 예산을 공유한다**(확인함 — Google 자체 thinking 문서 및, 독립적으로,
서로 다른 두 커뮤니티 프로젝트의 버그 리포트가 "thinking이 `max_tokens` 예산을 조용히
잠식해 출력이 중간에 잘린다"는 동일한 failure mode를 별개로 재현·보고). gpt-5.4에는
이런 축 자체가 없었다. 그대로 두면 "`max_tokens=1024`로 고정한 동일 디코딩 예산"이라는
전제가 judge family에 따라 실질적으로 달라지므로(고정된 1,024 중 얼마가 visible output에
쓰이는지가 모델마다 다름), confirmatory judge를 gpt-5.4에서 Gemini로 바꾸는 것 자체가
암묵적으로 디코딩 프로토콜을 바꾸는 효과를 낳는다. 이를 막기 위해 `gemini-3.6-flash`가
지원하는 가장 낮은 `thinking_level`인 `MINIMAL`(Flash-tier 모델 전용값; 독립 벤치마크
측정치는 `MINIMAL`에서 reasoning-token 소비가 사실상 0으로 떨어진다고 보고한다 — 확인함,
단 3차 벤치마크 블로그 출처이므로 1차 보증은 아니다)로 thinking을 최소화하도록 지정한다.
Google 문서가 규정하는 raw-JSON 확장 필드 형태는
`"extra_body": {"google": {"thinking_config": {"thinking_level": "minimal"}}}`이다
(확인함, 공식 문서의 curl 예시로 그대로 확인).

이 필드는 `harness/run_holdout.py`에 **judge-불특정** 환경변수
`HOLDOUT_JUDGE_EXTRA_BODY`로 노출했다(2026-09-20 코드 변경, §"harness 변경" 참고) —
설정하지 않으면 요청 바이트가 이전과 완전히 동일하고(gpt-5.4 실행 및 기존 테스트에
영향 없음), 설정하면 그 JSON 객체가 요청 바디의 `extra_body` 키로 그대로 병합된다.
Gemini 3.6-flash로 confirmatory holdout을 실행할 때는 다음을 함께 export한다:

```
export HOLDOUT_JUDGE_ENDPOINT='https://generativelanguage.googleapis.com/v1beta/openai'
export HOLDOUT_JUDGE_MODEL='gemini-3.6-flash'
export HOLDOUT_JUDGE_EXTRA_BODY='{"google":{"thinking_config":{"thinking_level":"minimal"}}}'
export HOLDOUT_JUDGE_API_KEY='<Gemini API 키; 파일에 리터럴로 쓰지 않는다>'
```

⚠️ **아직 실행되지 않음 — 이름만 재고정, API 미호출.** 위 [2026-09-12] 절과 같은 이유로
이 절도 "어느 모델을 쓸지"만 재확정한다. **이 세션은 Gemini API 키를 갖고 있지 않으며,
실제로 API를 호출해 검증하지 않았다.** 위에 적은 스펙은 Google 공개 문서 조사로 확인한
것이고, 실제 연결 테스트(엔드포인트 도달성, 인증, 응답 스키마 파싱, JSON-mode 출력이
`RUBRIC`이 요구하는 `{"score", "evidence"}` 스키마를 실제로 만족하는지)는 사용자가
Gemini API 키를 확보한 뒤 별도로 수행해야 한다. `output_gpt/`의 legacy 결과와 마찬가지로,
Gemini judge로 채점된 결과는 이 시점까지 존재하지 않는다.

**[2026-09-21] Confirmatory judge 세 번째 재결정 — `gemini-3.6-flash`를 `qwen-next-flash`(로컬 자가호스팅)로 대체한다.**

위 두 절([2026-09-12], [2026-09-20])은 지우지 않는다. 이번 재결정은 그 논증 구조를 뒤집는
것이 아니라, 실행 단계에서 실패한 뒤 사용자가 명시적으로 내린 운영상 판단이다.

**실행 결과가 이 재결정의 직접 계기다.** `gemini-3.6-flash`로 실제 224셀 confirmatory run을
시도했으나(`harness/real_run/`, 지금은 `harness/real_run_gemini_partial_DISCARDED/`로 이관),
**224개 중 158개가 HTTP 429(Too Many Requests)로 실패했고 65개만 유효하게 파싱됐으며 1개는
잘림(truncation)으로 추정된다**(확인함 — `harness/real_run_gemini_partial_DISCARDED/cells.jsonl`의
`judge_response_parsed` 필드를 세어 재확인: `judge_response_parsed=true` 65건,
`_error` 필드에 `HTTPError 429`를 담은 레코드 다수). 이는 [2026-09-20] 절이 이미 "실제로
API를 호출해 검증하지 않았다"고 명시했던 바로 그 리스크가 현실화된 것이다. 사용자는 이 결과를
본 뒤 **오늘(2026-09-21) 명시적으로 지시했다**: OpenAI 키에 이어 Gemini 경로도 처리량 한계로
막혔으니, rate limit이 없는 **로컬 자가호스팅 `qwen-next-flash`**로 전환한다.

**핵심 위협 공개 — self-enhancement / family-overlap을 의도적으로 포기함.** 이 논문의
extraction loop은 `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8`로 사전등록되어 있다(위 [2026-09-12]
절 및 §2.4, 변이 A–F 전체가 이 모델로 생성됨 — 확인함, 커밋 87d3c7e·3163f9a). 오늘 확정한
`qwen-next-flash`는 Qwen3.8-Flash-Next 계열 체크포인트다(아래 체크포인트 신원 항목 참고).
즉 **extraction과 confirmatory judge가 같은 모델 패밀리(Qwen)를 공유하게 된다.**
[2026-09-12] 절이 `gpt-5.4`를, [2026-09-20] 절이 `gemini-3.6-flash`를 고른 **명시적으로 기록된
이유는 공개 재현 가능한 표준 API 엔드포인트 여부**였지(제출 체크리스트 (12)/(16), 내부/OAuth
프록시 경로 배제) — self-enhancement 회피가 그 절들에 **문장으로 명시된 적은 없다**(확인함,
grep으로 재확인). 그러나 두 선택 모두 결과적으로 extraction 모델(Qwen)과 다른 패밀리였다는
점은 사실이며, 그 부수적 완화 효과가 이번 결정으로 사라진다. **judge가 자신과 같은 계열이 만든
산출물을 채점할 때 더 후하게 점수를 줄 수 있다는 self-enhancement bias 우려를 이 판단이
의도적으로 감수한다** — 사용자는 이 경고를 (agent-systems-engineer 관점의) 재확인 질문을 받은
뒤에도 전환을 재확정했다. 이 사실은 `main.tex`/`main_ko.tex`의 §Study Design과 §Threats에
그대로 반영한다(아래 "2/4. main.tex·main_ko.tex 반영" 참고) — 결과 해석 시 **judge가 채점한
고점수가 self-enhancement에 의한 과대평가일 가능성**을 배제할 수 없다.

**추가로 공개해야 할, 별개의 재현성 우려 (자체 관찰, 브리프가 직접 요구하지 않았지만 숨기면
안 됨).** [2026-09-12] 절의 (a)/(b) 분류는 "공개 표준 API 엔드포인트"(a)와 "내부/OAuth 전용
프록시 경로"(b)를 나누고, (b)를 "논문에 실명으로 인용할 수 있는 경로가 아니다"라며 배제했다.
오늘 채택한 `<internal-endpoint>`는 이 저장소가 실행되는 특정 호스트에서만 접근 가능한
**사설(private) 엔드포인트**이며, 외부 리뷰어가 동일 이름·동일 엔드포인트로 재현할 수 없다는
점에서 성격상 (b)에 더 가깝다(확인함 — 이 엔드포인트는 표준 공개 API가 아니라 로컬 vLLM
서버). `gpt-5.4`/`gemini-3.6-flash`가 준수했던 "리뷰어가 그대로 재현 가능" 기준을 이번
전환은 만족하지 못한다. 이는 self-enhancement 문제와 **별개의** threat이며, §Threats에
함께 반영한다(로컬 judge 실행 자체는 가능하지만, 제3자가 동일 조건으로 재현하려면 별도의
로컬 배포가 필요하다는 사실을 명시).

**체크포인트 신원 — pruned 5-expert 포크 우려에 대한 조사 결과.** 이 세션 이전 어느 시점에
"기존 10-expert 모델을 pruned 5-expert 포크로 교체 중"이라는 경고가 있었다. 이번 세션에서
직접 조사했다:
- 서빙 컨테이너: `docker inspect <container>` → 이미지 `<image>`, 마운트
  `<models>/Qwen3.8-Flash-Next-W4A16-AutoRound-hybrid:/model`,
  컨테이너는 `2026-09-20T22:15:29Z` 생성, 포트 `<host-port>-><container-port>`으로 이 호스트에 노출
  (확인함 — `docker inspect` 직접 실행).
- 해당 디렉터리의 `config.json`: `"num_experts": 512`, `"num_experts_per_tok": 10`
  (top-10 routing, 512개 expert 전량 보유로 선언됨 — 확인함, `config.json` 직접 열람).
  "10-expert"라는 표현이 경고에서 말한 원본(top-10 routing)과 일치하며, "pruned 5-expert"로
  교체된 흔적(예: `num_experts_per_tok=5`, expert 수 축소)은 config 레벨에서 **발견되지
  않았다**.
- `README.md`(모델 카드, 같은 디렉터리): 이 체크포인트는
  `Intel/Qwen3.8-Flash-Next-W4A16-AutoRound`(→ 원본 `Qwen/Qwen3.8-Flash-Next`)를 기반으로
  한 **양자화 변형**(bf16 lm_head→int8 GPTQ-Marlin, 300개 side-layer 텐서→fp8, 51B n-gram
  PLE 테이블 외부 mmap 분리)이라고 명시하며, expert pruning/제거에 대한 언급은 **없다**
  (확인함 — README.md 직접 열람).
- **잔여 불확실성(모름으로 남김)**: 위는 모두 config/메타데이터 레벨 확인이며, 실제 safetensors
  가중치 텐서의 expert 차원을 직접 검증하지는 않았다(67개 shard, 총 ~73GB — 이번 세션에서
  가중치 레벨 검증은 수행하지 않았다). 따라서 "이 체크포인트가 pruned 5-expert 포크가
  아니다"는 **config/README 근거로 상당히 신뢰할 수 있는 추정**이나, 가중치 레벨의 독립
  검증은 아니다. 원본 경고가 어느 시점·어느 배포를 가리켰는지도 이 세션에서는 재확인할 수
  없다 — 지금 로드된 체크포인트가 그 경고 이후 교체된 것인지, 애초에 다른 대상이었는지는
  **모름**.

**엔드포인트/모델 스펙 (확인함 — 이 세션에서 직접 curl로 호출):**
- 엔드포인트: `<internal-endpoint>` (`GET /v1/models` → 200, `id: "qwen-next-flash"`,
  `max_model_len: 262144`).
- `POST /v1/chat/completions`에 `temperature=0.0`, `max_tokens=1024`,
  `response_format={"type":"json_object"}`를 실제 RUBRIC 시스템 프롬프트 + 예시 아티팩트로
  호출: `HTTP 200`, `finish_reason: "stop"`, content가 `{"score":3,"evidence":"..."}`로
  **유효하게 파싱됨** — JSON-mode를 vLLM OpenAI-호환 서버가 실제로 지원함을 확인했다.
- **추가로 확인된, 이전에 없던 축 — 그리고 처음의 낙관적 판단이 실제 셀로는 틀렸음.**
  이 모델도 Gemini와 유사하게 응답에 내부 `reasoning` 필드(사고 과정)를 얹는다
  (`reasoning_parser qwen3`가 서빙 커맨드에 지정돼 있음 — 확인함, `docker inspect`의
  `Cmd`). 처음에는 harness의 RUBRIC 시스템 프롬프트 + **짧은 예시 아티팩트**(2줄)로
  테스트했고, `reasoning_tokens=154`, `completion_tokens=194`(총 1024 중 194만 사용)로
  잘리지 않고 정상 완료되는 것을 보고 "1024 예산이면 충분하다"고 판단했다 — **이 판단은
  실제 셀로 재현되지 않아 틀렸다.** `harness/run_holdout.py`가 실제로 만드는 셀
  (Variant A, `primary:A:CQB12`, 아티팩트 69,914 토큰)으로 다시 호출하자
  `finish_reason: "length"`, `reasoning_tokens=1024`(요청한 `max_tokens` 전량),
  `content: null`이 나왔다(확인함, 이 세션에서 직접 호출) — 가장 작은 Variant인 A조차,
  실제 ontology 밀도의 아티팩트에서는 reasoning만으로 1024 토큰 예산 전체를 소진해 가시
  출력이 단 한 글자도 나오지 않았다. 이는 작은 toy 프롬프트로 확인한 앞 문단의 결과가
  실제 224셀에 일반화되지 않음을 보여준다 — **작은 예산에서 재현된 Gemini와 동일한 실패
  모드가, 실제 아티팩트에서는 큰 예산(1024)에서도 재현된다.**
- **해결책 — `chat_template_kwargs.enable_thinking=false`(확인함, 실제 호출로 검증).**
  Gemini의 `thinking_config`처럼 vLLM/Qwen3 계열도 reasoning을 끄는 표준 메커니즘을
  제공한다: 요청 바디에 `"chat_template_kwargs": {"enable_thinking": false}`를 최상위
  필드로 넣으면 된다. 단, **Gemini와 다른 wire shape**이다 — Gemini의 OpenAI-호환
  translator는 이 필드를 `"extra_body": {...}` 라는 **최상위 wrapper 키 안에 중첩**해야
  받아들이지만(확인함, Google 공식 curl 예시), vLLM은 정반대로 **중첩하면 무시**하고
  최상위(top-level) 필드로 보내야만 적용된다(확인함 — 동일 요청을 `extra_body` 안에
  중첩해 보내자 `reasoning_tokens=56`으로 여전히 소진됐고, 최상위로 평탄화해 보내자
  `finish_reason: "stop"`, `reasoning_tokens=0`, `completion_tokens=307`, content가
  `{"score": 3, "evidence": "..."}`로 유효하게 파싱됐다). 기존 `HOLDOUT_JUDGE_EXTRA_BODY`
  (중첩형, Gemini 전용 shape)는 이미 검증된 대로 그대로 두고, `run_holdout.py`에 **새
  환경변수 `HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS`**를 추가했다 — 이 값은 요청 바디 최상위에
  그대로 병합된다(`§harness 변경` 참고). `temperature`/`max_tokens`/`response_format` 등
  사전등록된 디코딩 파라미터는 전혀 건드리지 않는다 — [2026-09-20] addendum이 Gemini의
  `thinking_level=minimal`에 적용한 것과 동일한 원칙(judge family가 바뀌어도 "1024
  토큰이 실질적으로 가시 출력 예산"이라는 전제를 유지)을 vLLM에도 동일하게 적용한 것이다.

⚠️ **뒤늦게 발견된, rate limit과는 별개인 구조적 블로커 — 이 서버의 context window로는
Variant B–F를 원천적으로 채점할 수 없다.** 실제 224셀 실행을 시작하기 전에 smoke probe
2셀이 모두 `HTTP 400 Bad Request`로 실패했고(확인함, `harness/smoke_run/cells.jsonl`),
원인을 vLLM 서버의 에러 메시지로 직접 확인했다: `"This model's maximum context length
is 262144 tokens. However, you requested 1024 output tokens and your prompt contains
at least 261121 input tokens..."`. 이는 rate limit(Gemini의 429)과 전혀 다른 종류의
실패다 — 재시도로 해결되지 않는 **하드 architecture 제약**이다. vLLM의 `/tokenize`
엔드포인트로 6개 variant의 실제 렌더링 뷰 전체를 정확히 토큰화해 확인했다(확인함,
이 세션에서 직접 호출):

| Variant | 문자 수 | 토큰 수 (vLLM 실측) | `max_model_len=262144`에 수용 가능? |
|---|---|---|---|
| A | 292,845 | 69,759 | 예 (여유 있음) |
| B | 1,950,988 | 497,402 | **아니오** (한도의 1.9배) |
| C | 2,414,780 | 645,020 | **아니오** (한도의 2.5배) |
| D | 2,402,874 | 642,072 | **아니오** (한도의 2.4배) |
| E | 2,365,387 | 653,455 | **아니오** (한도의 2.5배) |
| F | 2,365,387 | 653,455 | **아니오** (한도의 2.5배) |

Variant A(naive baseline, 가장 짧은 렌더링)만 이 judge의 context window에 들어간다.
B–F(구조화 파이프라인 전체 — 이 논문이 실제로 평가하려는 조건들)는 전부 시스템/유저
프롬프트 오버헤드를 더하기 전부터 이미 한도를 1.9~2.5배 초과한다. `harness/real_run/`의
등록된 224셀 계획(primary 188 + ablated 24 + preserved 12)은 6개 variant에 고르게
분산되어 있으므로, **primary 셀의 약 5/6과 ablated/preserved control 대부분이 이
judge로는 구조적으로 채점 불가능할 것으로 예상된다**(추정 — 정확한 개수는 아래 "5. 실행"
결과에서 실측). 이는 self-enhancement 리스크와 **완전히 별개의, 더 근본적인** 문제다 —
self-enhancement는 "점수가 편향될 수 있다"는 우려이지만, 이 문제는 "대부분의 셀에서
애초에 점수 자체가 나오지 않는다"는 문제다. `gemini-3.6-flash`는 이 문제를 겪지 않았다
(224개 중 65개가 유효하게 파싱됐다는 사실 자체가 context length는 그 judge에서 병목이
아니었음을 보여준다 — Gemini의 공개된 context window는 이 로컬 배포보다 훨씬 크다).
**이 선택(qwen-next-flash, `--max-model-len 262144`로 배포된 이 특정 컨테이너)이
Variant B–F에 대해 유효한 confirmatory judge 역할을 할 수 있는지는 이 시점에서 근본적
의문이다 — 서버 재구성(더 큰 `--max-model-len`, 이 컨테이너의 GPU 메모리 예산이 허용하는
한도 내에서) 또는 다른 judge 선택이 필요할 수 있다. 이 세션은 공유 vLLM 컨테이너의 서빙
설정을 변경할 권한·범위를 갖지 않았으므로 변경하지 않았다 — 이는 사용자 판단이 필요한
결정점으로 별도 보고한다.**

새 judge 실행 시 다음을 export한다:

```
export HOLDOUT_JUDGE_ENDPOINT='<internal-endpoint>'
export HOLDOUT_JUDGE_MODEL='qwen-next-flash'
export HOLDOUT_JUDGE_API_KEY='dummy'
export HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS='{"chat_template_kwargs":{"enable_thinking":false}}'
unset HOLDOUT_JUDGE_EXTRA_BODY
```

이 실행은 4-way 동시처리(`harness/run_holdout.py`의 `ThreadPoolExecutor(max_workers=4)`,
`JUDGE_CONCURRENCY` 환경변수로 조정 가능)로 수행된다 — 로컬 서버는 외부 rate limit이 없어
동시 요청이 안전하다고 판단했다(§"harness 변경" 참고). `HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS`는
위 "해결책" 항목에서 확인한 vLLM 전용 top-level 병합 메커니즘이다 — 이것 없이는 대부분의
셀이 `content: null`로 실패한다(위에서 확인함). Variant B–F의 context-length 블로커는
이 플래그로 해결되지 않는다 — 별개의, 더 근본적인 제약이다(위 표 참고). 실제 실행 결과
(224개 중 유효 개수, sanity check)는 이 addendum이 아니라 별도 실행 로그·
`harness/real_run/MANIFEST.json`에 기록한다 — 사전등록 문서는 "어느 모델을 쓸지"를
재확정하는 문서이지, 결과를 담는 문서가 아니다(위 두 절과 동일한 원칙).

---

## 1. 주 종점(primary endpoint)과 주 estimand

셀 (v, q), |Q| = 36. J(v,q) ∈ {0..3} = judge Layer-1 점수,
A(v,q) ∈ {0,1} = 평가자의 증거 판정 (1 = 근거 span 존재).

### 1.0 adjudicated label L₁\* — 주 종점이 계산되는 라벨

**이 절은 2026-09-12에 추가되었다.** 이전 판은 π만 정의하고, 주 지표·확인적 대조·등가검정이
*어느 라벨 위에서* 계산되는지를 명시하지 않았다. 원고(§III)가 L₁\*을 도입하면서
**사전등록이 주 종점을 담지 않는 상태**가 되었고, 이는 사전등록의 목적 자체를 무효화한다.
**아직 freeze 전이므로 지금 수정한다** — freeze 이후였다면 사후 변경이라 보고 의무가 발생했을 것이다.

> **L₁\*(v,q) = J(v,q)           if A(v,q) = 1**
> **L₁\*(v,q) = min{ J(v,q), 1 } if A(v,q) = 0**

**단측(one-sided) by construction**: 근거 span이 없는 점수를 **낮출 수는 있어도 올릴 수는 없다.**
이 비대칭은 π의 비대칭과 동일한 것이며(§1.1 "왜 단측인가"), 둘은 같은 대상의 두 가지 읽기다 —
L₁\*이 강등시키는 셀의 집합이 정확히 π가 세는 셀의 집합이다.

**주 종점:**

> **Coverage(v) = ( Σ_q L₁\*(v,q) ) / ( |Q| · 3 ) × 100**

아래 모두가 **L₁\* 위에서** 계산된다 — J 위에서가 아니다:
- 주 지표 Coverage (유일한 headline 수치)
- 확인적 대조 2개 (A→B, B→B′) — §2 G6, §4 Holm 적용 대상
- 등가검정 TOST (±0.30 L1 마진)
- fragility / tipping-point 민감도 분석 (§4)

**adjudication이 없는 구간의 규칙(사전등록):** human pass는 1차 도메인 216셀에만 존재한다.
2차 도메인과 legacy pilot에는 A가 없으므로 **L₁\* = J**가 되며, 이 경우 보고되는 수치는
**judge-only 점수이고 사용 지점마다 그렇게 라벨링한다.** 이 둘을 1차 도메인 수치와
같은 표에 섞어 비교하지 않는다.

### 1.1 주 estimand — silent over-credit rate

> **π = Pr[ J(v,q) ≥ 2 ∧ A(v,q) = 0 ]**

= **silent over-credit rate**: judge가 "대체로 답변가능"(≥2) 이상이라고 했는데
**근거 span이 없는** 셀의 비율.

### 왜 단측(one-sided)인가

평가자는 도구의 저자이고, 잔존 편향은 **judge를 면책하는 방향**이다.
따라서 측정된 과대신용률은 **하한(lower bound)** 이고, **CI의 상한이 정직한 헤드라인**이다.

> 사전등록된 증거앵커 판정 하에서 judge의 silent over-credit rate는 π̂ = x%
> (95% CQ-clustered BCa CI [l, u]). 평가자가 도구의 저자이고 잔존 편향이 judge 면책
> 방향이므로 π̂는 **하한**이며, 따라서 구간 상한 u%를 실효 안전 수치로 제시한다.
> **judge가 독립적 전문가 판단과 일치한다는 주장은 하지 않는다.**

자기에게 불리한 진술은 신뢰할 수 있고 유리한 진술은 그렇지 않다 —
**이 비대칭이 이 연구의 인식론 전부다.**

**silent under-credit(judge가 놓친 진짜 근거)은 경계할 수 없고, 경계하려 시도하지도 않는다.**
이 방향은 편향이 반대로 작동하므로 같은 논리로 방어되지 않는다. 한계로 명시한다.

---

## 2. 수용 게이트 G1–G8

| # | 게이트 | 플랜 대비 | 임계값 | 방향 |
|---|---|---|---|---|
| G1 | **silent over-credit** π의 CQ-clustered CI 상한 | 존치, **주 지표로 승격**, span 기준으로 재정의 | 상한 ≤ 10% | 양측 |
| G2 | **intra-rater QWK** (washout 재채점, n=72) | 폐기된 human–human 게이트 **대체** | CI 하한 ≥ **0.70** | 양측, 필요조건이지 충분조건 아님 |
| G3 | 평가자 **음성 대조** (ablated 셀을 unsupported로) | **신규** | ≥ 22/24 | 양측 |
| G4 | **human–judge QWK** | **반증 전용으로 강등** | CI 상한 < 0.60이면 실패 | **실패만 가능, 통과 불가** |
| G5 | MAE(J,H) | 존치, judge 오차의 하한으로 재해석 | CI 상한 ≤ 0.50 | 양측 |
| G6 | A→B 일관성 + non-Qwen judge 방향 일치 + fragility K ≥ 6 | 존치, *일관성*으로 약화 | — | 양측 |
| G7 | **감사추적 무결성** | **신규** | 라벨 100% unblind 커밋 전 타임스탬프, 사후수정 0, 20초 미만 셀 < 3% | 양측 |
| G8 | **외부 36셀 스팟체크** (확보 시) | **신규** | 평균 부호차 CI가 관대한 방향으로 0 배제 시 실패 | **실패만 가능** |
| — | ~~human–human QWK ≥ 0.60~~ | **삭제 — 획득 불가** | — | — |

### 반증 전용(falsification-only) 게이트: G4, G8

이 둘은 **실패만 가능하고 통과로는 아무것도 주장하지 못한다.**

- **G4가 뒤집히는 이유**: 비독립 하에서 높은 human–judge 일치는 타당성과 무관하게 기대되므로
  **유리한 방향으로는 무정보**다. 낮은 일치는 "도구 공동설계자가 관대하게 읽어도 judge를
  재현하지 못했다"는 강한 반증이다. 반증 전용이 올바른 논리 형식이다.
- **G8**도 같은 형식이다. 평균 부호차 CI가 **관대한 방향으로 0을 배제**하면 실패이며,
  그렇지 않다고 해서 inter-rater reliability를 확보한 것이 아니다 —
  **그렇게 부르지도 않는다.**

### ⚠️ human–human QWK는 삭제되었다 (약화가 아니라 삭제)

human이 1인(= 도구 설계자 본인)이면 참조표준(reference standard) 설계는 성능이 떨어지는 게
아니라 **붕괴**한다 — 참조의 재현성과 독립성이 동시에 사라지기 때문이다.
**임계값을 낮춰 구제하지 않는다.** 참조표준을 필요로 하지 않는 설계로 교체했고,
human–human QWK 게이트는 **획득 불가로 판정하여 삭제**했다.

### G2가 0.60 → 0.70인 이유

intra-rater 일치도는 inter-rater보다 **체계적으로 높다**(같은 머리, 잔존 기억, 안정적 특이 해석).
0.60을 그대로 가져오면 **자동 통과라 의미가 없다.**

### ⚠️ G1 게이트 산술 — 사전등록 전에 반드시 짚는다

유효 독립 클러스터가 ~36개면 **rule of three**로 **관측 사건이 0이어도**
95% 단측 상한이 **3/36 ≈ 8.3%** 다.
36개 중 **1건만 나와도** 게이트를 실패한다. **[2026-09-13 산술 정정]**
이전 판에 적힌 "정확 상한 ≈13.7%"는 어떤 표준 방법으로도 재현되지 않는 값이었다.
n=36에서 Clopper--Pearson 정확 상한은 사건 0건일 때 95% 단측 **≈8.0%**
(97.5% 단측 **≈9.7%**), 1건일 때 95% 단측 **≈12.5%** (97.5% 단측 **≈14.5%**)다.
`3/36 ≈ 8.3%`는 rule-of-three 근사치이지 정확 상한이 아니다. 결론은 바뀌지 않는다 —
1건이면 어느 방법으로도 10%를 넘는다 — 그러나 수치는 정확해야 하므로 정정한다.

⚠️ **미해결 내부 불일치(사람 판단 필요).** §4는 zero-event 비율에 **97.5% 단측**
Clopper--Pearson을 쓴다고 적고, 이 절과 원고의 G1 서술은 **95% 단측**을 쓴다.
0건일 때 두 값은 8.0% 대 9.7%로, 후자는 10% 게이트에 **0.3%p** 여유만 남긴다.
어느 수준을 G1에 적용할지 데이터를 보기 전에 확정해야 한다.

> 즉 **G1은 이 표본크기에서 사실상 무관용(zero-tolerance) 기준**이다.

선택지는 (a) 15%로 완화 (b) 216셀 전체로 π 정의(단 설계효과로 유효 n이 36–72로 되돌아와
이득이 적음) (c) **10%를 유지하되 사전등록에 "n=36에서 이는 사실상 무사건 기준과 동등"이라고
명시**하는 것이었다.

> **채택: (c).** 10%를 유지하고, **그렇게 말한다.**
> 정직한 해석이고, 엄격한 게이트이며, 날카로운 리뷰어가 사후에 제기할 반론을 선점한다.

**[2026-09-12 개정 — freeze 이전, 결과 관측 이전]** 위 (c) 채택 이후, holdout CQ 뱅크
(`bank/cq_bank_brick_v2.csv`)를 **36행(6 category × 6) → 60행(6 category × 6 → 6×10)**으로
확장했다. 이 절의 원문(옵션 (a)/(b)/(c)와 "채택: (c)")은 **그대로 보존**하며 — 이 개정은
그 판단이 틀렸다는 뜻이 아니라, (c)가 감내하기로 한 "사실상 무관용" 성격 자체를 완화하는
후속 조치다. n=60에서 rule-of-three 산술을 다시 계산하면:

- 관측 사건 0건: 95% 단측 상한 **3/60 = 5%** (n=36의 8.3%보다 완화).
- 관측 사건 1건: 정확 상한 **≈7.7%** (n=36의 ≈13.7%에서 완화되어, **10% 게이트를 통과**할
  여지가 생긴다 — n=36에서는 1건만 나와도 자동 실패였다).

즉 이 개정 이후 (c)의 실질 의미가 "무관용"에서 "1건까지는 허용 가능한 엄격한 게이트"로
바뀐다. **(c) 채택 자체는 유지**하되(10% 임계값은 그대로), 그 임계값이 지금 걸려 있는
표본크기가 36이 아니라 60이라는 사실을 여기 기록한다.

**[2026-09-12 후속 — framing 확정, 위 미해결 항목 해소]** 위 미해결 항목을 아래와 같이
닫는다. **Framing B를 채택한다: 60행은 채점 대상이 아니라 eligibility pool(+교체 재고)이고,
실제 채점 대상은 여전히 36행(6 category × 6)이다.** 근거와 절차는
`bank/CQ_BANK_BRICK.md`의 "2026-09-12: eligibility screen performed, stratified draw
resolved, bank frozen" 절 참고 — 원 36행이 이미 6/category로 저작되었고, 60행 전체에 대해
단일 저자 channel-1 심사를 수행한 결과 **0/60 rejected**였으므로 24행 잉여에서의 교체는
0건 발생했다. 따라서 동결된 채점 대상은 정확히 원래의 36행이다(`cq_bank_brick_v1.csv`,
2026-09-12T12:22:32Z 동결, tag `access2026-cqbank-brick-v1-freeze`).

**이 결정이 위 rule-of-three 재계산에 미치는 영향 — 정정.** 직전 문단의 "n=60에서 관측 0건 ->
5%, 1건 -> 7.7%" 계산은 **G1 게이트 자체에는 적용되지 않는다.** G1은 human-adjudicated
silent over-score 사건을 **채점된 CQ 표본**에 대해 세는 게이트이고, framing B 하에서
채점 표본은 60이 아니라 36이다. 60행 확장이 사준 것은 rule-of-three 여유가 아니라
**eligibility 심사에서 탈락한 행을 대체할 재고**뿐이다(이번 심사에서 탈락이 0건이었으므로
그 재고 자체는 쓰이지 않았다). 따라서 **G1의 실제 표본크기는 n=36으로 되돌아가고, 위
"채택: (c)"에서 이미 말한 "사실상 무관용" 성격이 그대로 유지된다** — 관측 사건 0건 상한
≈8.3%, 1건 상한 ≈13.7%(모두 앞 절의 원 산식과 동일). 60행으로의 확장을 근거로 게이트가
완화됐다고 서술하면 그 자체가 통계적 오류이므로, 이 문서는 그 오해를 명시적으로 정정해
남긴다.

- §1의 `|Q| = 36` (셀 (v,q) 정의) 및 §3 셀 예산 표의 `1차 도메인(Brick) | 216 | 36 CQ × 6
  variant`는 **변경하지 않는다** — 채점 대상이 36이므로 두 값 모두 원래 그대로 유효하다.
  "60·360으로 바뀌어야 하는지"라는 미해결 질문은 "바뀌지 않는다"로 닫는다.
- §4의 MDE/SD/bootstrap 수치도 n=36 기준 서술이 그대로 유효하므로 변경하지 않는다.
- G1의 실패-사건 계수 단위는 **CQ-cluster 단위**로 유지한다(§2 및 §4 본문 참고) —
  cluster_id가 지금 각 행의 `cq_id`와 1:1로 실체화되어 있으므로(paraphrase가 아직
  저작되지 않아 클러스터가 아직 분할되지 않음), 현재는 "CQ 단위"와 "CQ-cluster 단위"가
  수치상 동일하다. paraphrase가 추가되어 클러스터가 CQ 여러 개를 묶게 되면 그 시점부터
  두 단위가 갈라지므로, 그 때 이 문서를 다시 갱신해야 한다.

---

## 3. 프로토콜 파라미터 (셀 예산)

| 층 | n | 비고 |
|---|---|---|
| 1차 도메인(Brick) | 216 | 36 CQ × 6 variant — 주장을 지탱 |
| 2차 도메인 반복 | 72 | 24 CQ × 3 variant |
| 시드 ablated 대조 | 24 | 미공지, 무작위 큐에 삽입 |
| 시드 preserved 대조 | 12 | 과잉교정(compensatory severity) 방어 |
| **1차 패스 계** | **324** | 셀당 ~90초 → 약 8–10시간 |
| washout 재채점 | 72 | **25%, 이 아래로 내리지 말 것** |
| human raw-TTL 패스 | 24 | `ASK` 불가 CQ 한정, 재채점 집합과 분리 |
| 외부 스팟체크 | 36 | 확보 시 |

### 재채점 n = 72 근거

참 QWK ≈ 0.80일 때 SE ≈ √(0.36/72) ≈ 0.071 → 95% CI ≈ [0.66, 0.94]이므로
**0.70 하한 게이트가 검정 가능**하다.
n = 36이면 CI ≈ [0.60, 1.0]이라 **게이트가 검정 불가능해진다.**

구성: **48 비례층화**(category × judge 점수대) + **24 불일치 강화**(`ASK` ↔ judge 충돌 셀).
강화 층은 범위제한(range restriction)으로 pooled QWK를 낮추므로
**두 층 따로 + 재가중 pooled, 3개 모두 사전등록**한다.

### 2차 채점자(second annotator) subsample — inter-rater 완화책 — [2026-09-22 추가]

**이것은 결정이지 실행이 아니다.** 외부 리뷰어 피드백("single-rater limitation을
더 구체적으로 다뤄라, 예: subsample에 대한 2차 annotator")에 대한 응답으로,
위 §2의 "한 명의 rater이며 그 rater는 저자이다" 한계에 **추가로** 적용할
완화책을 여기 사전등록한다. 어떤 annotator도 아직 섭외되지 않았고, 어떤
cell도 아직 채점되지 않았으며, 이 addendum은 그 결과를 담지 않는다(담을
수 없다 — 결과가 존재하지 않는다).

**설계.** 독립적인 2차 annotator — 이 논문의 저자가 아니고, CQ bank 저작·
rubric 설계·pipeline 구축 어느 쪽에도 관여하지 않은 사람 — 가 §1의 confirmatory
judge pass가 실제로 채점한 $188$개 primary-track cell(§Method Channel~2의
1차 patternset, ablated/preserved control 24+12는 제외 — 그 두 층은 이미
seeded-control 메커니즘으로 별도 관리된다) 중에서, 사전등록 seed로 비복원
층화추출한 $n=48$개 셀(카테고리당 8개, 위 washout 층화와 동일한 원리)을
같은 $L_1$ rubric으로 채점한다. 채점 대상 cell 목록과 2차 annotator의 신원은
채점 시작 **전에** 고정·예치한다 — 결과를 본 뒤 표본을 고르는 것은 이 문서
전체가 금지하는 바로 그 패턴이다.

**n=48 근거 (위 재채점 n=72와 동일한 근사식 사용).** 참 inter-rater
$\kappa \approx 0.6$(intra-rater self-consistency 목표인 $0.80$보다 보수적으로
낮게 잡는다 — 독립된 두 사람이 일치하는 것은 한 사람이 washout 후 자신과
일치하는 것보다 어려운 기준이기 때문이다)이라 가정하면,
$\mathrm{SE}(\kappa) \approx \sqrt{(1-\kappa^2)/n}$에서 $n=48$일 때
$\mathrm{SE} \approx \sqrt{0.64/48} \approx 0.115$, 95% CI $\approx
[0.60 - 1.96\times0.115,\ 0.60 + 1.96\times0.115] \approx [0.375, 0.825]$.
이는 넓은 구간이지만 **추정 불가능하지는 않다** — chance-level 근처(0에 가까운
값)와 완전 일치(1에 가까운 값)를 구별하기에는 충분하고, 그 이상의 정밀도를
주장하지 않는다. $n=48$은 주 채점 pass($188$셀)를 밀어내지 않으면서(추가
채점 부담이 주 pass의 약 26%) 이 정도 해상도를 얻는 지점으로 골랐다 — 완전
재채점($n=188$)은 예산상 불가능하고, 이 설계 목적(추정 가능한 CI 확보)에도
필요하지 않다.

**이것이 대체하지 않는 것.** 이 2차 채점자 subsample은 Channel~2
evidence-anchored adjudication(falsification-only, 단일 저자-rater가 수행,
silent over-credit $\pi$만 bound)을 **대체하지 않는다.** 두 메커니즘은 서로
다른 질문에 답한다 — Channel~2는 "judge가 근거 없는 credit을 주는가"를
audit하고, 이 2차 채점자 pass는 "두 명의 독립된 사람이 같은 rubric으로 같은
cell에 도달하는 결론이 얼마나 일치하는가"라는 통상적인 inter-rater
reliability를 측정한다. 산출되는 quadratic-weighted $\kappa$(Cohen 1968)는
$\pi$를 대체하지 않고 그와 **나란히** 보고된다. 이 subsample의 $\kappa$는
G1–G8의 어떤 pre-registered gate에도 입력되지 않는다 — 그 게이트들은 이미
동결되어 있으며, 이 addendum은 그것들을 바꾸지 않는다.

**변경되지 않는 것.** 위와 동일하게, 이 addendum은 §1.0/§Method의 정의,
G1–G8 게이트 정의, `annotation/` 문서, CQ bank, `labels_primary_pass_blank.csv`/
`labels_washout_reassessment_pass_blank.csv`(이미 224/72행으로 완성됨)를
전혀 건드리지 않는다. subsample은 이 기존 패킷의 primary pass 행들 중에서
사후에 추출하는 것으로 문서화될 뿐이며, 새 CSV를 만들 필요는 없다.

### washout ≥ 21일 (목표 28일) + 표면 교란

재채점은 **최소 21일, 목표 28일**의 washout 이후에 수행한다. 항목 표면을 교란한다:
**새 ID, 새 위치, 그리고 cluster paraphrase 제시.**

뱅크의 `cluster_id`가 현재 1:1 기본값이므로 **freeze 전에 ~15개 paraphrase를 저작**해 두면
통계가 intra-rater → **intra-rater-across-paraphrase**로 격상된다(더 어렵고 더 정직).
저비용·고수익이므로 freeze 전에 한다.

### 순서 무작위화 — ≥ 20 위치 분리 제약

같은 `cq_id`의 셀은 **20 위치 이상 떨어뜨린다.**
나란히 비교채점하는 경로가 "B가 A보다 나아야 한다"는 사전지식이 들어오는 **주 통로**다.

✅ [2026-09-12 해소] `scripts/make_human_anno_sheet.py`가 이 제약을 구현한다 —
시드 기반 제약 셔플(`constrained_shuffle`)이 같은 `cq_id` 셀을 ≥20 위치 떨어뜨리고,
제약을 만족 못 하면 **달성된 최소 간격을 숨기지 않고 경고로 보고**한다.

### ⚠️ variant blinding은 달성 불가 — 주장하지 않는다

저자는 내용만 봐도 variant를 안다(A는 산문형, B는 내부 IRI, E/F는 PROV-O).
따라서 **judge-score-blind와 order-blind만 주장한다.**
플랜의 "opaque ID" 표현은 **과대주장**이며, 이를 논문에 밝히는 비용은 0이고 신뢰도 이득은 크다.

(불투명 ID + 매핑 봉인 분리는 여전히 수행한다 — 우연한 노출을 줄이지만
**블라인딩을 달성하지는 못한다.** 현재 항목 ID가 `f"{v}-{cq}"`라 variant 문자가
평가자에게 그대로 노출되는 것은 별개의 결함이며 freeze 전에 고친다.)

### 피로 관리

세션당 **최대 60셀**, 세션 간 **≥ 12시간**.
순서에 따른 라벨 드리프트 진단을 **사전등록하고 보고**한다.
연습 12셀은 **legacy Ontology-101 아티팩트에서만** 뽑는다 — 연구 아티팩트에서 뽑지 않는다.

---

## 4. 통계 처리

### CQ-cluster bootstrap — 4가지 개정

1. **percentile이 아니라 BCa.** 클러스터가 36개면 percentile은 **과소피복**한다.
   10,000 resample, **시드 사전등록**.
2. **재표본 단위는 CQ가 아니라 의미 클러스터(semantic cluster).**
   paraphrase 추가 시점부터 실질적으로 달라지므로 **지금 배선해 둔다.**
3. **0-사건 비율은 bootstrap 금지.** 0건이면 **단측 97.5% Clopper–Pearson 상한**을 보고한다.
4. **MDE가 전제한 SD를 명시한다.** n=36에서 MDE = 0.467 · SD 이므로
   **MDE 0.53은 SD ≈ 1.14를 함의**한다.
   플랜은 SD 없이 0.53만 써서 **검증 불가 상태**였다 — 이 문서가 그것을 고정한다.

### intra-rater QWK의 CI

셀 단순 bootstrap **금지**(κ는 분할표 전체의 함수다).
72셀의 **CQ 수준 클러스터 BCa** + **Fleiss–Cohen 해석적 SE 교차확인**.

### fragility / tipping-point 분석 (신규·필수)

평가자 편향을 측정할 수 없으니 **가격을 매긴다.**
가설에 가장 유리한 셀들의 라벨을 **한 단계씩 적대적으로 강등**하여,

- ① A→B가 구별 불가가 되기까지 **몇 개 CQ가 움직여야 하는지**
- ② π 구간이 10%를 넘기까지 **몇 개인지**

를 보고한다. **K = 6 (뱅크의 1/6)을 G6 임계값으로 사전등록.**
비용 0, 정량적이며, 측정 불가능한 위협을 **독자가 수용 또는 거부할 수 있는 명시적 가격**으로 변환한다.
**편향을 추정하는 것이 아니라 가격을 매기는 것**임을 원고에 명시한다.

### ⚠️ 검정하면 안 되는 것 (사전등록된 금지 목록)

- **카테고리별 추론 일체.** 6 CQ/category ⇒ MDE ≈ 1.3 L1로 척도 가용범위에 근접한다.
  플랜의 "주결론 사용 금지"를 **CI·p-value 보고 자체 금지로 강화**한다.
- **D, E, F 미세 랭킹.** |Δ| < 0.53은 unresolved다.
- **"unresolved"를 "tie"로 부르는 것.** 등가(equivalence)는 **TOST 구간이 ±0.30 안에 완전히
  들어올 때만** 성립한다. n=36에선 구간이 마진보다 넓을 것이므로 대부분의 근사동점은
  엄밀히 **구별불가도 등가도 아니다.** (선행판의 "ties as ties" 표현은 미묘한 과대주장이었다.)
- **두 도메인 pooling(36+24=60)으로 검정력을 부풀리는 것.**
- **상관계수를 타당성 증거로 제시하는 것.** 비독립 하에서 해석 불가다.
  `human_kappa.py`가 Spearman을 내지만 **기술통계로만** 쓴다.
- **재채점 라벨을 주 추정에 재사용하는 것.**
- **사후 confirmatory judge 선택.**
- **확인적 대조 2개 외에 Holm을 적용하는 것.**

---

## 5. 사전등록된 실패 정책

- **G1 또는 G5 실패 시** — judge를 calibrated라고 부르지 않고 **음성 결과로 보고**한다.
- **G4 실패 시** — judge를 **uncalibrated로 선언**하고, 정량 결론을 **`ASK` 오라클 트랙으로 제한**한다.
- 어느 경우에도 **임계값을 사후에 옮기지 않는다.** 옮긴다면 옮겼다고 쓴다.

> **사전등록이 실패를 치명적이 아니라 보고 가능하게 만드는 것 — 그것이 사전등록의 최대 이유다.**

원고 §IX는 이 정책을 그대로 진술하고, **두 게이트(G4, G8)가 의도적으로 단측**이며
**실패는 가능하지만 통과로는 타당성을 주장할 수 없음**을 밝힌다.
실패했다면 음성 결과로 보고했을 것이며, **사전등록이 그 문장을 검증 가능하게 만드는 유일한 이유**다.

---

### 6-1. 렌더링을 동결 대상에 포함하는 이유 — [2026-09-13 추가]

은행·루브릭·judge·디코딩 파라미터·아티팩트를 **전부 고정**하고 렌더링만 바꾼
드라이런에서 Layer-1 coverage가 **54.6% → 75.9% (+21.3p)** 움직였다. 원인은 두 겹의
누락이었다.

- `owl:Class`만 순회 → `rdfs:Class`로 선언된 `rec:` 용어 373개 전량 미표시
- `skos:definition`만 독해 → `rec:`의 정의문이 담긴 `rdfs:comment` 미표시

즉 `rec:` 관련 문항들은 **답이 존재할 수 없는 자료**를 보고 채점되고 있었다.
카테고리별로는 `instances` +2.33, `concept_definition` +1.17이 올랐고
`slots_facets`는 −0.67로 **내려갔다** — 더 많이 보여주는 것이 모든 범주에 이득은
아니며, 이 크기의 자유도를 등록하지 않고 남겨 두면 결과를 본 뒤 렌더링을 바꿔
결론을 바꿀 여지가 생긴다.

따라서 렌더링 사양과 그 산출물의 digest를 위 freeze block에 함께 등록한다.
확인적 실행은 이 digest와 일치하는 렌더링에서만 수행하며, 불일치 시 실행을
중단하고 사유를 기록한다. 이후 렌더링을 바꾸려면 **데이터를 보기 전에** 새 digest로
재등록해야 한다.

⚠️ 위 +21.3p는 **시뮬레이션 드라이런**(judge = 로컬 qwen, 증거 판정 A도 모델 생성)
에서 나온 값이다. 렌더링 민감도의 크기를 보이기 위한 것이지 confirmatory 결과가
아니며, 원고의 결과 절에 인용하지 않는다.

#### 6-1-addendum. v1 → v2 재동결 (인스턴스 포함) — [2026-09-20 추가, 결과를 본 이후 개정]

위 6-1 원문(2026-09-13)은 그대로 둔다. 이 항은 그 위에 덧붙이는 개정 이력이다.

**발견**: A–F 여섯 파이프라인 변이 산출 그래프(`harness/variants/`)는 스키마
(`owl:Class` 7개)보다 인스턴스(`owl:NamedIndividual` 4,179–4,186개)가 압도적으로
많은데, v1 렌더링 규격은 인스턴스를 명시적으로 제외했다 — 근거는 "동결 Brick
v1.4.4 스냅샷에 인스턴스가 0개이므로 보여줄 것이 없다"였는데, 이 전제는
Brick 스냅샷 자체에는 참이지만 실제로 채점 대상이 되는 파이프라인 산출물에는
거짓이었다. 그 결과 37,455줄 그래프가 87줄로 렌더링되는 등 콘텐츠 대부분이
judge에게 보이지 않았다. 상세: `harness/variants/RENDERING_MISMATCH.md`.

**조치**: `rubric/RENDERING_SPEC.md`를 v2로 재동결(`owl:NamedIndividual`을
클래스/속성 스키마 뒤에 렌더링에 추가; 클래스 렌더링 규칙은 전부 불변).
동결 Brick v1.4.4 스냅샷은 인스턴스가 0개이므로 v1/v2 렌더링 뷰가 바이트 단위로
동일 — 위 freeze block의 "Rendered view SHA256 (Brick v1.4.4)" 값은 **변경되지
않았다**. "Rendering spec SHA256" 값만 v2로 갱신했다(위 freeze block 참고).
`main.tex`/`main_ko.tex`에 임베드된 본 PREREG.md의 digest(`d6bd30e6…`로 시작)도
이 재동결과 함께 갱신했다.

**남은 문제 — 이 재동결로 해소되지 않음**: eligibility preflight
(`harness/run_holdout.py::eligibility_preflight`)를 v2 렌더링으로 재실행한 결과,
36개 CQ 전량이 6개 변이 전부에서 여전히 `missing_grounding`으로 거부된다
(dry-run 재확인, 2026-09-20). 원인은 렌더링이 아니라 두 가지 별개 사실이다.

1. CQ bank의 grounding 앵커 상당수(`rdfs:comment`, `rdfs:subClassOf`,
   `prop:X`, `children:X`, `disjoint:X`, `inverse:X`, `subclassof:X`,
   `sh:path` 형태 — 36행 중 31행)는 **동결된 진짜 Brick v1.4.4 TBox를 그대로
   렌더링한 뷰에 대해서도** 매칭되지 않는다(직접 확인: 동결 스냅샷을
   `schema_view()`로 렌더링해 `_grounding_match_info`를 36행 전부에 돌려본 결과
   31/36 `can_ablate=False`). `_grounding_anchors()`(`harness/run_holdout.py`)가
   제어 구문 프리픽스(`prop`, `children`, `disjoint`, `inverse`, `subclassof`
   등)를 걸러낼 때 프리픽스가 아니라 로컬명을 기준으로 걸러내는 것으로 보여,
   `rdfs:comment`처럼 로컬명이 우연히 제어어 집합과 겹치지 않는 앵커는 렌더러가
   결코 문자 그대로 출력하지 않는 예측/정의문 텍스트를 요구하게 된다. 이는
   렌더링 규격이 아니라 preflight 앵커 매칭 로직(별도 파일, 별도 결정)의
   결함으로 보이며, 이번 작업 범위에서 손대지 않았다.
2. A–F 변이는 `ct:` 네임스페이스와 chunktograph 자체 술어(`ct:p_define` 등)만
   사용하며 `brick:`/`rec:` 프리픽스 IRI를 단 하나도 포함하지 않는다. 진짜
   Brick TBox 렌더링에 대해서만 통과하는 나머지 5개 CQ(예: `skos:definition
   brick:Sensor`)조차, 요구하는 정확한 qname이 파이프라인 산출물에 애초에
   존재하지 않으므로 인스턴스 포함 여부와 무관하게 통과할 수 없다.

즉 인스턴스 포함은 **필요했지만 충분하지 않았다** — 정당한 렌더링 결함을
고쳤을 뿐, 확인적 holdout을 막고 있는 나머지 두 문제(앵커 매칭 로직 결함,
CQ bank와 파이프라인 산출물 간 어휘 불일치)는 별도의 사용자 결정을 요구한다.

### 6-2. Eligibility gate 조정 — 확인된 코퍼스 희소성 — [2026-09-21 추가]

**결과를 본 이후의 개정이 아니다.** 이 절은 §6-1-addendum이 남긴 "앵커 매칭 로직 결함"
(2026-09-20 밤, 이후 `harness/run_holdout.py`의 namespace-/case-agnostic 매칭으로
해소, 커밋 `3675745`)을 고친 뒤에도 **남아 있는 별개의 잔여 실패**를 다룬다. 어떤 judge도
아직 호출되지 않았고(`HOLDOUT_JUDGE_API_KEY` 미설정), 어떤 J/A/L₁\* 값도 관측되지 않았다 —
이 절이 조정하는 것은 **judge 호출 이전 단계의 eligibility gate**뿐이다.

#### 재실증 (2026-09-21)

앵커 매칭 수정과 A–F 전 변이의 사전등록 모델(Qwen/Qwen3-Next-80B-A3B-Instruct-FP8,
<internal-host>, 커밋 `87d3c7e`/`3163f9a`) 재생성 이후, `run_holdout.py --dry-run`을 다시 실행하면
216개 1차(primary) 셀 중 **정확히 28개**가 여전히 `missing_grounding`(ablation 불가)으로
거부된다. 이 28개는 **13개 CQ**에 걸쳐 있으며, 두 그룹으로 나뉜다.

| 그룹 | CQ 수 | 셀 수 | 실패 범위 |
|---|---|---|---|
| (a) 전 변이 실패 | 3 | 18 (3 × 6 variant) | A, B, C, D, E, F **전부** |
| (b) Variant A 한정 실패 | 10 | 10 (10 × 1 variant) | **A만**; B–F에서는 grounding 확인됨 |
| 합계 | 13 | 28 | — |

**(a) 전 변이 실패 — 3개 CQ (18셀):**

| cq_id | grounding | 질문 |
|---|---|---|
| CQB15 | `prop:feeds` | Which property pair expresses supply/feed direction? |
| CQB22 | `prop:buildingPrimaryFunction` | Which property states the primary function of a Building? |
| CQB23 | `skos:definition brick:yearBuilt` | Which property records when something was built? |

**(b) Variant A 한정 실패 — 10개 CQ (10셀, 모두 `variant=A`):**

CQB13(`inverse:hasPoint~isPointOf`), CQB14(`prop:hasLocation`),
CQB18(`prop:hasAssociatedTag`), CQB19(`prop:hasUnit`), CQB20(`prop:lastKnownValue`),
CQB24(`prop:hasQuantity`), CQB32(`prop:deprecation`), CQB33(`prop:hasSubMeter`),
CQB35(`prop:hasQuantity-meth`), CQB36(`ref:hasExternalReference / brick:hasQUDTReference`).

**모델-무관성 재확인.** 위 28개는 Variant A만 사전등록 모델로 교체했을 때(`87d3c7e`, "188/216
primary cells... remaining 28 failures")와 이후 B–F까지 전부 교체했을 때(`3163f9a`,
"28/216 primary cells remain ineligible, identical in count to the prior A-only-regenerated
state") **완전히 동일한 개수·동일한 구성**으로 재현됐다 — 즉 잘못된/구형 모델의 산출물이
아니라, 사전등록된 모델의 **최종 산출물에서도** 재현되는 실패다.

**근거 재검증 — 원천 코퍼스 희소성 (2026-09-21 직접 측정).** `harness/brick_corpus.json`
(추출 파이프라인의 실제 입력 코퍼스)에서 각 grounding 로컬명을 단어 경계(`\b`) 기준,
대소문자 구분 정확 일치로 셌다(`re.findall(r'\bTERM\b', corpus)`):

| cq_id | 로컬명 | 코퍼스 내 정확 일치 횟수 |
|---|---|---|
| CQB15 | `feeds` | 5 |
| CQB22 | `buildingPrimaryFunction` | 2 |
| CQB23 | `yearBuilt` | 1 |
| CQB13 | `hasPoint` / `isPointOf` | 6 / 4 |
| CQB14 | `hasLocation` | 4 |
| CQB18 | `hasAssociatedTag` | 4 |
| CQB19 | `hasUnit` | 2 |
| CQB20 | `lastKnownValue` | 2 |
| CQB24 | `hasQuantity` | 2 |
| CQB32 | `deprecation` | 2 |
| CQB33 | `hasSubMeter` | 4 |
| CQB35 | `hasQuantity`(meth 접미사 제거 후 동일 로컬명) | 2 |
| CQB36 | `hasExternalReference` / `hasQUDTReference` | 2 / 2 |

13개 전부 **한 자릿수(1–6회)**로, 552KB 코퍼스 전체 기준 극희소하다는 배경 서술은 확인됐다
(원 배경 서술의 "1–4회"는 근사였다 — `feeds`=5, `hasPoint`=6이 약간 벗어나지만, 정정된
정확 수치로도 "극희소" 결론 자체는 바뀌지 않는다).

**그러나 (a)와 (b)는 같은 원인이 아니다 — 정직하게 구분한다.** (a)의 3개 CQ는 **B–F의
완전한 구조화 파이프라인(triple extraction + spaCy refinement + SKOS 계층화 + LLM typing,
렌더링 4,623+줄)조차** 해당 로컬명을 단 한 줄도 보존하지 못했다 — 코퍼스 자체에 너무
희소해 어떤 추출 조건으로도 복원되지 않는다는 뜻이다. 반면 (b)의 10개 CQ는 **B–F에서는
grounding이 확인**되고, **naive 단일 패스 baseline인 Variant A(렌더링 1,913줄, B의 절반
미만 — `harness/variants/MANIFEST.json`의 variant A `description`: "Naive direct-LLM
baseline: each atomic chunk is rendered to Turtle section-by-section, without triple
extraction or typing")에서만** 사라진다. 즉 (b)는 "원천에 없다"가 아니라 "코퍼스 희소성
때문에 naive baseline의 추출 신뢰도 경계에 걸린다"는 더 정확한 설명이며, Variant A가
의도적으로 열등한 baseline이라는 프로토콜 설계(§원고 "comparison_role": confirmatory A ->
B source endpoint)와 부합하는 **기대된 baseline 거동**이지, `VARIANT_A_BLOCKED.md`가
다룬 결함(65-triple stub, 이미 별도 해소)과는 다른 현상이다.

#### 결정

**CQ bank(`bank/cq_bank_brick_v1.csv`)는 손대지 않는다.** 대신 위 28개 primary 셀
(정확히 위 표의 (variant, cq_id) 조합 28개)을 confirmatory judge 실행에서 **명시적으로
제외**한다. 제외는 CQ 전체가 아니라 **셀 단위**다 — (b)의 10개 CQ는 여전히 5/6 variant에서
채점된다.

- **216 → 188.** 1차 도메인(Brick)의 채점 대상 primary 셀은 216(36 CQ × 6 variant)에서
  188(216 − 28)로 줄어든다. `harness/run_holdout.py`의 `_primary_cells()`가 여전히 216개
  전부를 열거하지만, `build_cell_plan()`이 이 28개를 최종 셀 큐에서 걸러낸다 — judge는
  188개만 받는다.
- **36개 CQ 중 3개가 1차 도메인에서 "판정 불가"로 표시된다.** CQB15/CQB22/CQB23은 **6/6
  variant 전부**에서 채점 데이터가 0개다 — 이 3개 CQ는 Coverage 계산에 어떤 variant에서도
  기여하지 않는다. 나머지 10개 CQ((b) 그룹)는 5/6 variant에서 정상 채점되며, Variant A
  한정으로만 데이터가 없다. 나머지 23개 CQ는 6/6 variant 전부 정상.

#### 주 estimand(§1.0/§1.1)에 대한 영향 — 새 통계량을 만들지 않는다

기존 정의를 그대로 유지하고, **정의되지 않은 항을 합·분모 양쪽에서 함께 제외**하는
표준적 방식으로만 확장한다(대치도, 0 대입도 하지 않는다 — 정의되지 않은 (v,q)는 분자
합과 분모 카운트 양쪽에서 단순히 존재하지 않는 항이다).

> **Coverage(v) = ( Σ_{q∈Q_v} L₁\*(v,q) ) / ( |Q_v| · 3 ) × 100**

원문(§1.0)의 `Q_v = Q, |Q_v| = |Q| = 36`이 고정이었던 것을, variant마다 실제로 채점된
CQ 집합으로 제한한다:

- `v = A`: `Q_A = Q \ {CQB13,14,15,18,19,20,22,23,24,32,33,35,36}` → `|Q_A| = 23`.
- `v ∈ {B,C,D,E,F}`: `Q_v = Q \ {CQB15,CQB22,CQB23}` → `|Q_v| = 33`.

**π(§1.1)와 A→B/B→B′ confirmatory 대조, TOST, fragility 분석**도 같은 원칙을 따른다 —
이들은 모두 L₁\* 위에서 계산되므로(§1.0), L₁\*(v,q)가 정의되지 않은 (v,q)는 자동으로
빠진다. 특히 **cq_id로 짝짓는(paired) 모든 대조**(A→B 등)는 두 variant의 `Q_v` **교집합**
위에서만 계산된다 — 정의되지 않은 짝은 대치가 아니라 목록별(pairwise) 제외다. 이는
Variant A가 관여하는 모든 대조(A→B 등)가 가장 축소된 CQ 집합(23/36, ≈64%)에서 계산됨을
뜻하며, 이 사실은 결과 절 작성 시 한계로 명시해야 한다(⚠️ 지금은 결과가 없으므로 지금
명시하지는 않는다 — TBD로 남긴다, 아래 §원고 반영 참고).

⚠️ **G1(§2)에 대한 전방 주의 — 이 절에서 G1 임계값 자체를 바꾸지 않는다.** §2의
rule-of-three 산술(n=36, 0건 → ≈8.3%, 1건 → ≈13.7%)은 **CQ-cluster 개수 n=36을 그대로
가정**한다. CQB15/22/23이 전 variant에서 0셀이 되면, 이 3개 cluster는 실제 채점
데이터에서 사건을 낼 수 없는 채로 사라진다 — 즉 G1의 실질 cluster 모집단이 n=36이 아니라
**n=33**이 될 가능성이 있다(0건일 때 3/33≈9.1%, 10% 게이트에 더 가까워짐). **이 문서는
G1 confidence level 절·`apply_g1_decision.py`를 이번 결정으로 수정하지 않는다** — 이는
실제 채점 데이터가 나온 뒤, G1을 적용하는 시점에 **별도로 재확인해야 할 사항**으로만
여기 기록해 둔다.

#### 등록된 대조군(ablated/preserved control) 재표본 — 같은 시드, 축소된 pool

`REGISTERED_SEED = 20260913`으로 primary pool에서 뽑는 `control_rng.sample(...)` 호출은
그대로이며, `harness/run_holdout.py::eligibility_preflight`가 표본 추출 **이전에** 위 28개
셀을 primary pool에서 제거하도록 고쳤다(아래 "harness 변경" 참고). 즉 **같은 시드, 축소된
pool(216 → 188)에서 재추출**이다 — `REGISTERED_ABLATED`(24)·`REGISTERED_PRESERVED`(12)
상수는 변경하지 않았다.

- **채울 수 있는지 확인함(2026-09-21, `run_holdout.py --dry-run` 재실행):**
  188개 eligible primary에서 ablated-control 24개, preserved-control 12개 모두
  **정상 표본 추출됨** — preflight가 `ablated_control_failures`/`preserved_control_failures`
  없이 통과하고, `build_cell_plan()`이 188(primary) + 24(ablated) + 12(preserved) = **224**
  셀 계획을 반환한다(직전에는 216 + 24 + 12 = 252). preserved-control 후보 조건(paraphrase
  존재)은 36개 CQ 전부가 paraphrase를 갖고 있어(`bank/cq_bank_brick_v1_paraphrases.csv`)
  188개 축소 pool에서도 12개 요구치에 크게 못 미칠 위험은 없었다.

#### harness 변경 요약

`harness/run_holdout.py`에 `DOCUMENTED_EXCLUSIONS`(정확히 이 28개 (variant, cq_id)
조합, 각각 사유 태그 포함)를 상수로 추가했다. `eligibility_preflight()`는 이제
- `can_ablate=False`인 primary 셀이 이 28개 목록에 있으면 `documented_exclusions`에
  기록하고 `missing_grounding`/하드 거부 대상에서 뺀다.
- 목록에 **없는** 어떤 새 grounding 실패든 여전히 `missing_grounding`에 들어가 이전과
  동일하게 `REFUSING TO RUN`으로 하드 거부한다(회귀 방지 — 목록은 절대 자동으로 넓어지지
  않는다).
- ablated/preserved control 표본 pool과 `build_cell_plan()`의 최종 `"primary"` 셀 모두
  이 28개를 제외한 pool에서만 구성한다.
- preflight 결과(성공/실패 양쪽)와 dry-run/실제 실행이 쓰는 `MANIFEST.json`에
  `documented_exclusions`(28개 항목 전체, 사유 포함) 필드가 항상 기록된다.

`harness/test_run_holdout.py`에 새 테스트 2개를 추가하고 기존 테스트 2개(원래 "216개
전부 실패"를 가정했던 테스트)를 새 동작에 맞춰 갱신했다:
`test_documented_exclusions_pass_preflight_and_shrink_the_primary_pool`(28개가 예외
처리되고 primary pool이 188로 줄어드는지),
`test_undocumented_missing_grounding_still_hard_refuses`(목록 밖의 새 실패는 28개가
동시에 면제된 상태에서도 여전히 하드 거부되는지 — 회귀 방지 테스트).

## 6. 동결 이후 남은 운영 항목

아래 항목은 2026-09-12 CQ bank freeze 이후 남은 운영·신뢰도 보강 항목이다.
이들은 이미 동결된 primary 36행의 scored sample을 소급해 변경하지 않으며,
전체 protocol freeze 또는 test--retest reliability를 완료한 것으로 간주하지 않는다.

- [x] `bank/verify_bank.py`의 `BASE` 하드코딩 절대경로 → `Path(__file__).resolve().parent.parent` 기준 상대경로
      (freeze 게이트가 이 스크립트의 exit code에 의존하므로 **감사 체인 자체의 재현성 버그**다.
      내부 절대경로 노출도 동시에 해소된다) — **[2026-09-12 해소]** `Path(__file__)` 기준 상대경로로 교체,
      추가로 `bank_name` 인자에 절대경로/탈출 방지 guard 추가.
      **[2026-09-12 갱신]** CQB21/CQB23 grounding 정정(아래 참조) 이후 재확인: 36행·55 term·0 missing, exit 0.
- [x] `scripts/make_human_anno_sheet.py` — legacy pilot 전용으로 opaque stable cell ID와
      opaque artifact filename을 생성하고, annotator-facing `output/human_kit[_pass2]/`에는
      answer key를 쓰지 않는다. owner/sealed key·variant/token/path mapping은 기본적으로
      `output/human_kit_sealed[_pass2]/`에 분리하며 `--sealed-dir`로 owner-only 경로를 명시할 수 있다.
      `--pass2`, seeded constrained shuffle, same-CQ 최소 간격(기본 ≥20), 그리고 미충족 시
      achieved 간격 보고를 보존한다. `human_kappa.py`는 sealed key를 명시적으로 읽고 key가 없으면
      실패한다. **이 hardening은 judge-score/order blinding만 보장한다. artifact content가 provenance를
      드러낼 수 있으므로 full variant blinding을 주장하지 않는다.** 기존 freeze hash나 authoritative
      packet semantics는 변경하지 않는다.
- [ ] `cq_bank_brick_v1.csv`의 `status` 컬럼을 enum으로 정규화(사유는 별도 `note` 컬럼)
- [x] 뱅크에 `ask_expressible` 컬럼 추가 — **[2026-09-12 해소]** `ask_expressible` +
      `ask_query_file` 컬럼이 `cq_bank_brick_v1.csv`(36행)와 `cq_bank_brick_v2.csv`(60행)
      전체에 추가되었고, 각 `ask_queries/CQB01.rq`..`CQB60.rq`가 스냅샷에 대해 `ASK` = `true`로
      독립 확인됨.
      **[2026-09-12 정정 기록]** 이 항목은 작성 당시 실제로는 거짓이었다 — `scripts/ask_oracle.py`
      실행 결과 CQB21/CQB23 두 행이 `ASK=false`였다(둘 다 `owl:DatatypeProperty`를 주장했으나
      스냅샷은 `brick:grossArea`/`brick:yearBuilt`를 `owl:ObjectProperty` + `brick:EntityProperty`로
      타이핑). 두 행의 grounding·expected_answer·`.rq` 쿼리를 스냅샷 타이핑에 맞게 정정한 뒤
      재실행하여 v1 36/36, v2 60/60 모두 `exit 0`을 확인했다(오라클 코드 자체의 인자 개수 불일치
      버그도 같은 세션에서 수정). **cluster paraphrase ~15개는 여전히 미저작** — 이 항목만 열어둠.
- [x] `bank/cq_bank_brick_v2.csv` (60행 = 6 category × 10, CQB37-CQB60 신규) —
      **[2026-09-12] `verify_bank.py cq_bank_brick_v2.csv`로 재확인: 60행·98 term·0 missing·
      exit 0** (CQB21/CQB23 정정 반영, term 수 94→98).
      **[2026-09-12 해소]** framing B 채택 확정 — §2 상단의 "framing 확정" 절 참고. §1/§3의
      `|Q|=36`·셀 예산 216은 **변경 없음**(60행은 eligibility pool + 미사용 교체 재고이지,
      채점 대상이 아니다). 이 항목은 완전히 닫혔다.
- [x] `CQ_BANK_BRICK.md`의 "Two experts independently screen" →
      "1인 전문가 심사 + `verify_bank.py` grounding 게이트 + 실행 가능한 `ASK` 검사"로 교체 완료

> 위 스크립트·게이트는 사전등록의 일부로 기능하므로, **사람이 dry-run으로 직접 확인한 뒤**
> 게이트로 삼는다. 검증 스크립트의 버그는 곧 감사 체인의 버그다.

## 7. [2026-09-21 addendum] ASK-oracle을 holdout run 그래프로 확장 시도 — 막힘, 기록만

**배경.** 224/224 셀 judge run(`harness/real_run/`, commit `700f6dc`)이 완료된 뒤,
§1.0의 A(v,q)를 채우는 별도 경로로 "36개 CQ 중 18개(=`ask_expressible=yes`)에 대해
`bank/ask_queries/CQB*.rq`를 그 셀이 실제로 쓴 variant의 생성 graph
(`harness/variants/{A..F}/graph_*.ttl`)에 대해 실행해서 adjudication을 자동화할 수
있는가"를 검토했다.

**결론: 하지 않는다. 두 가지 독립적 이유로 막혀 있다.**

1. **A(v,q)로의 변환 규칙이 애초에 사전등록되어 있지 않다.** §1.0은 A를
   "평가자의 증거 판정"으로 명시적으로 정의하고, §Method(`main.tex`
   Section~\ref{sec:method-reference})의 Channel~1(ASK oracle)은 "its reach is a
   measured property of the bank rather than a result of the holdout run"이라고
   똑같이 명시적으로 scope를 bank 검증(동결된 스냅샷 대비)으로 한정한다. Channel~2(사람
   evidence-span adjudication)만이 L₁\*에 들어가는 A를 만든다. `annotation/`
   문서(PROTOCOL.md, CALIBRATION_PLAN.md, LABELER_GUIDE.md, ADJUDICATION_TEMPLATE.md)
   어디에도 ASK 결과를 A로 대입하는 절차가 없다. `harness/analyze_holdout.py`의
   `join_labels()`도 사람 라벨 CSV 하나만 `cell_id`로 join하도록 되어 있고, 별도
   oracle 라벨 파일을 병합하는 경로가 없다. 이 규칙을 지금 만들어내는 것은 사후
   방법론 결정이므로 하지 않는다.
2. **설사 A로 쓰지 않고 §Method가 이미 계획한 "oracle--judge concordance"(순수
   descriptive, 어떤 gate도 아님)로만 쓰려 해도, namespace 불일치로 실행 자체가
   무의미하다.** `bank/ask_queries/CQB*.rq`는 canonical
   `https://brickschema.org/schema/Brick#`(`brick:`) IRI로 저작되어 있다. 그런데
   `harness/variants/{A..F}/graph_{A..F}.ttl` 여섯 개 전부가 Brick 개념을
   `http://example.org/chunktograph#`(`ex:`/`ct:`) 고유 namespace로만 렌더링하며,
   canonical `brickschema.org/schema/Brick#` IRI는 여섯 graph 전체에서 **0건**이다
   (`grep -c "brickschema.org/schema/Brick#" harness/variants/{A..F}/graph_*.ttl`로
   확인함). `ask_expressible=yes`인 18개 CQ의 `.rq`를 rdflib으로 여섯 variant 그래프
   전부에 대해 그대로 실행하면 **18×6=108건 전부 `ASK=false`**다(실제로 실행해서
   확인함, 스크립트는 아래 참고) — 이는 해당 fact의 실재 여부와 무관한 namespace
   artifact이지 신호가 아니다. 두 namespace를 잇는 term-alignment 규칙은 어디에도
   사전등록되어 있지 않고, 지금 즉석으로 만들면(예: local name만 비교) 그 자체가
   새로운, 검증되지 않은 방법론적 결정이 된다.

**확인 스크립트(재현 가능, 일회성 진단용 — adjudication 파이프라인에 연결되지
않음):** `bank/cq_bank_brick_v1.csv`에서 `ask_expressible == "yes"`인 18행을 골라
그 `ask_query_file`을 rdflib `Graph.parse()`로 로드한 `harness/variants/{A..F}/graph_*.ttl`
전부에 대해 `Graph.query()`로 실행 — 108/108 `False`, 예외 없음.

**변경되지 않는 것.** §1.0의 A(v,q) 정의, §Method Channel~1/2/3 구분, G1--G8 게이트
정의, L₁\* demotion 공식 — 전부 그대로다. 이 addendum은 "시도했고 왜 못 했는지"를
기록할 뿐, 어떤 절차도 바꾸지 않는다.

**바뀐 것 — annotation packet 실물화 (adjudication 규칙과 무관한, 순수 tooling
버그 수정).** `annotation/packet/build_label_packet.py`는 이전에는 run 디렉터리
전체에 대해 단일 공유 `schema_view.txt`를 모든 행의 `rendered_view_path`로 썼다.
formal run(`harness/real_run/`)은 애초에 이 파일을 쓰지 않으며 — variant마다 다른
`harness/variants/{variant}/rendered_view.txt`가 judge에게 실제로 주어진 자료다
(variant별 `graph_sha256`/`rendered_view_sha256`가 서로 다름, `harness/variants/*/MANIFEST.json`
확인함) — 이를 고치지 않고 실행하면 사람 annotator가 자신이 채점 중인 variant와
무관한 자료를 보게 될 뻔했다. `_read_cells`/`_make_rows`를 variant별 파일을 우선
resolve하도록 수정하고(레거시 단일-variant dryrun과 하위호환 유지), 동시에
`_constrained_shuffle`의 min-gap=20 제약이 실제 224셀 분포(최대 그룹 크기 9)에서는
이론상 충족 가능함에도(`(9-1)*(20+1)+3=171≤224`) 기존 500회 랜덤 재시도 휴리스틱이
achieved=2로 실패하던 문제를, 표준 "최다-잔여-eligible" greedy로 교체해 실제로
achieved=20(정확히 충족)로 고쳤다. Washout 72셀 subset은 그룹 분포상 min-gap=20이
수학적으로 불가능함(`(5-1)*(20+1)+1=85>72`)을 확인했고, 이 경우 least-recently-placed
fallback으로 achieved=10까지 내는 것으로 정직하게 저하시킨다(무작위 완전 재셔플로
achieved=1까지 떨어지던 이전 동작 대비 개선). 테스트는
`annotation/packet/test_build_label_packet.py`에 추가했다. 이 수정은 A값을 만들거나
추정하지 않는다 — 사람이 채울 빈 칸(`A`, `rater_L1`, `note`)의 메타데이터
정확성만 고친다.

## 8. [2026-09-22 addendum] Disclosed LLM auxiliary check — supplementary only, does not feed A(v,q)

**배경.** Channel~2 human evidence-anchored adjudication(사람이 $A(v,q)$를 만드는
유일한 절차, §1.0/§Method)은 이 addendum 시점에도 실행되지 않았다 --- annotation
packet(`annotation/packet/labels_primary_pass_blank.csv` 224행,
`labels_washout_reassessment_pass_blank.csv` 72행)은 실물이지만 모든 `A` 칸이 여전히
비어 있음을 재확인했다(이 addendum을 쓰기 직전 두 CSV 전부를 재검사함). 사용자는
사람 채점과 무관하게, 판정자-독립적인 LLM 보조 신호를 만들어 disclosed
supplementary material로만 원고에 넣기로 명시적으로 결정했다.

**한 것.** `harness/llm_auxiliary_check.py`(신규 스크립트, `cells.jsonl`이나
`run_holdout.py`는 수정하지 않음)가 `harness/real_run/cells.jsonl`의 $224$개 cell
전부에 대해 gpt-5.6-luna(OpenAI 계열, 이 환경에 이미 설정된 로컬
OpenAI-호환 proxy `<internal-proxy-endpoint>` 경유)를 호출한다. 이 모델은
extraction pipeline의 Qwen/Qwen3-Next-80B-A3B-Instruct-FP8과도, confirmatory
judge인 gemini-3.6-flash와도 다른 계열이며, 각각 "같은 파이프라인/같은
계열이 자기 자신을 채점"하는 self-enhancement 위험을 피하기 위해 의도적으로
선택했다. Judge 자신의 scoring rubric(`run_holdout.py`의 `RUBRIC`)과는 별도인
독립 프롬프트로, judge의 score는 전혀 보여주지 않은 채, judge가 인용한
evidence span이 CQ에 실제로 답하는지만 물었다(evidence-verification 과제이지
재채점 과제가 아님). Evidence span이 없는(전부 $J{=}0$) $67$개 cell은
`annotation/PROTOCOL.md`가 빈 span에 대해 사람 rater에게 적용하는 것과 동일한
규칙으로 모델 호출 없이 $A_{\mathrm{aux}}{=}0$으로 결정론적으로 처리했다. 결과는
`harness/real_run/llm_auxiliary_labels.jsonl`에 있으며, 모든 레코드의
`label_source`는 `llm_auxiliary_gpt-5.6-luna`로 고정된다 --- `human`이나 그
밖의 어떤 값도 아니다.

**결과 (실제 계산값, 이 자체는 TBD가 아님).** $224$개 cell 중
$A_{\mathrm{aux}}{=}1$이 $133$개, $A_{\mathrm{aux}}{=}0$이 $91$개
($67$개는 모델 호출 없는 empty-evidence 결정, 나머지 $157$개가 모델 호출,
실패 $0$건). Sanity check: mean judge score $J$는 $A_{\mathrm{aux}}{=}1$
cell에서 $2.677$, $A_{\mathrm{aux}}{=}0$ cell에서 $0.549$로 기대 방향과
일치한다. Cell-kind별로는 ablated-control $24$개 중 $19$개가
$A_{\mathrm{aux}}{=}0$(기대 방향과 일치, 그러나 완전하지는 않음: $5$개는
$A_{\mathrm{aux}}{=}1$), preserved-control $12$개 중 $7$개가
$A_{\mathrm{aux}}{=}1$(다수이나 강하지 않음: $5$개는 $A_{\mathrm{aux}}{=}0$).
이 control 분포는 완벽한 분리가 아니며, 원고에는 과장 없이 전체 mean-$J$
대비 수치만 보고한다.

**절대 하지 않은 것 (레드라인).** `harness/analyze_holdout.py`는 이 파일을
읽지 않으며, `--label-source`로 `llm_auxiliary_*`를 받아들이도록 고치지도
않았다 --- 그 스크립트의 `canonical_label_source`는 여전히 `human`(및 동의어)
또는 명시적 simulation marker만 허용하는 닫힌 집합이다. Coverage, $\hat\pi$,
$\kappa$, TOST 어느 것도 이 LLM 보조 라벨로 계산하지 않았다. `main.tex`/
`main_ko.tex`의 primary/confirmatory 결과 자리(Coverage, $\pi$, TOST,
$k_1$/$k_2$ 등)의 `\TBD`는 이 addendum 전후로 개수가 동일하게 유지된다
(EN 13개, KO 12개, 재확인함). §1.0의 A(v,q) 정의, §Method Channel~1/2/3
구분, G1--G8 게이트 정의, L₁\* demotion 공식 --- 전부 그대로다. 이 addendum은
disclosed, non-confirmatory한 보충 자료 하나를 추가할 뿐, 어떤 사전등록된
절차도 바꾸지 않는다.

**변경되지 않는 것.** 위와 동일하게, 이 addendum은 tooling 추가일 뿐이다.
PREREG.md 다른 절, §1.0/§Method의 정의, `annotation/` 문서, CQ bank는
건드리지 않았다.

## 9. [2026-09-22 addendum] Protocol deviation — Coverage/π/TOST now computed with the disclosed LLM auxiliary check, NOT the pre-registered human pass

**이 addendum이 위 §8의 레드라인을 뒤집는다는 것을 명시한다.** §8은 "Coverage,
$\hat\pi$, $\kappa$, TOST 어느 것도 이 LLM 보조 라벨로 계산하지 않았다"고
못 박았다. 이 addendum 시점부터 그 문장은 더 이상 사실이 아니다 --- 사용자가
명시적으로, 반복적으로 지시하여 방향을 바꿨다: 사람 채점(Channel~2)을
LLM이 대신했다고 속이는 것은 끝까지 거부했지만, LLM 보조체크를 **disclosed**
방식으로 주 지표 계산에 실제로 사용하고 그 사실을 본문·부록에 명시하는
것은 진행하기로 했다. 이 절은 무엇이, 왜, 어떻게 바뀌었는지를 기록한다 ---
§8의 원문은 위에 그대로 남기고 덮어쓰지 않는다.

**한 것.** `harness/real_run/llm_auxiliary_labels.jsonl`(224행, §8에서 생성)을
`cell_id,A,label_source` 3-column CSV(`harness/real_run/llm_auxiliary_as_labels.csv`)로
변환했다: `A` = `A_auxiliary`, `label_source`는 매 행 문자열 그대로
`"LLM, not human"`으로 고정 --- 이는 `analyze_holdout.py`의
`canonical_label_source()`가 이미 인정하는 명시적 simulation marker 집합
(`_SIMULATED_SOURCES`) 중 하나이므로, **`analyze_holdout.py`의 검증 코드는
단 한 줄도 고치지 않았다**: 그 스크립트가 "human 아니면 명시적 simulation
marker만 허용"하도록 짠 이유가 바로 이런 경우 값을 자동으로 SIMULATED=true로
정직하게 표시하기 위해서였고, 실제로 그렇게 동작했다. 실행:
`python3 harness/analyze_holdout.py harness/real_run/cells.jsonl --seed 20260913
--out harness/real_run/llm_auxiliary_results.json --labels
harness/real_run/llm_auxiliary_as_labels.csv`. 출력 JSON은 자동으로
`"label_source": "LLM, not human"`, `"SIMULATED": true`, `"judge_simulated": false`를
찍는다 --- 사람이 아님을 매 결과 레코드가 스스로 증언한다.

**결과 (`harness/real_run/llm_auxiliary_results.json`, 재현 가능).**
Coverage$(G)$: $A{=}56.41\%$, $B{=}56.10\%$, $C{=}62.28\%$, $D{=}50.00\%$,
$E{=}56.41\%$, $F{=}58.77\%$. $A\!\to\!B$ 확정 대조: $\Delta L_1^{\ast}=+0.261$,
CQ-cluster BCa 95% CI $[-0.286, 0.804]$ ($n{=}23$ clusters, Wilcoxon
$p=0.530$), 판정 **unresolved** ($\pm0.30$ margin 기준). $B\!\to\!B'$는 이
run에 $B'$ variant가 없어 계산 불가(별개의 cross-domain 설계 영역). G1
silent-over-credit: events=8, n\_clusters=33, one-sided Clopper-Pearson
upper bound **0.4226** vs.\ 임계값 0.10 --- **G1 fail**. G2--G8 중
G3(부정 통제)·G5(MAE)·G6(consistency)·G7(audit trail)는 이 체크가 만들지
않는 `rater_L1`(사람이 매기는 신선한 0--3점)을 요구하므로 `not_computable`;
G4·G8은 falsification-only라 등록된 diagnostic이 없으면 `not_computable`.
이 모든 gate 상태를 숨기거나 유리한 것만 고르지 않고 JSON 그대로 논문에
반영한다 --- G1 fail을 포함해서.

**논문 반영.** `main.tex`/`main_ko.tex`의 Study Design 절
(`sec:results-primary`), Abstract, Introduction, Conclusion을 위 실제
수치로 갱신했고, 매 등장 지점에서 "disclosed LLM auxiliary check, NOT the
pre-registered human pass" / "exploratory, not confirmatory"를 명시한다.
Coverage/π/TOST를 채우는 대신 남겨둔 것: $\kappa$, seeded-control recovery
$k_1/24$·$k_2/12$, audit-trail, consistency --- 이들은 `rater_L1`이 없어
여전히 계산 불가이고 원고에서도 계산 불가로 명시한다. gpt-5.6-luna 프롬프트
전문을 새 Appendix(`app:aux-prompt`)에 그대로 공개했다.

**여전히 절대 하지 않은 것 (레드라인, 유지).** 이 LLM 보조체크 결과를
`human`으로 표시하거나 사람이 채점한 것처럼 서술하지 않는다. 사전등록된
Channel~2 human evidence adjudication은 여전히 실행되지 않았고, 이 addendum도
그것을 실행하지 않는다 --- 그 사실을 원고 전체에서 반복해서 명시한다. $\kappa$를
포함한 사람-필요 게이트들은 TBD로 남는다. 이 addendum이 하는 일은 정확히 하나
--- 이미 만들어 놓은 disclosed LLM 보조 라벨을, 숨기거나 사람인 척하지 않고,
실제로 주 지표 계산에 쓰고 그 결과(성공이든 G1 fail 같은 실패든)를 투명하게
보고하는 것뿐이다.

## 10. [2026-10-07 addendum] Post-unblinding disagreement review stage — secondary·descriptive만, primary와 명목 분리; 첫 라벨 저장 이전에 등록

**등록 시점과 검증 가능한 근거.** 이 addendum은 2026-10-07, Channel~2 첫 라벨이
저장되기 **이전**에 추가되었다. 검증: `<labels>/primary_working.csv`의 sha256이
blank sheet와 동일하고(이 세션에서 재확인), harness QA가 아닌 실제 label_assist
session log가 존재하지 않는다. 즉 이 단계는 관측된 효과에 반응한 개정(결과 의존적
개정)이 아니라, 데이터를 한 방울도 보기 전에 등록된 절차다.

**배경.** 저자 질문: "AI 평가 초안을 사람이 교정하는 편이 라벨 품질에 낫지 않은가."
이 설계(AI-assisted correction)는 인간-vs-judge 불일치율이라는 주 estimand의
정의상 측정을 파괴한다 — 교정된 라벨은 구조적으로 AI 출력에 앵커링되어
agreement inflation을 만든다(이 addendum §10.1 참조, 주패스에 도입하지 않는다).
그 대신 아래 조건으로 **채널 분리된 2차 검토 단계**만 등록한다. 용어 충돌 주의:
§1.0과 §8에서 `adjudicated label L₁*`·`Channel~2 human evidence-anchored
adjudication`은 **1차 인간 판정 자체**를 뜻한다. 이 addendum의 검토 단계는 그
어느 것과도 무관하며 L₁*에 들어가거나 그것을 수정하지 않는다.

### 10.1 검토 단계 정의 (registered spec)

- **트리거 셀 집합.** 188 primary cell 중 `judge verdict ≠ human A`인 셀.
  (등기된 단일 규칙. L₁* 근접 불일치는 분석기가 diagnostic으로 나열할 수 있으나
  검토 트리거로는 등록하지 않는다.)
- **최초 개시 시점(순서 제약, 타협 불가).** S1~S4 완료 → blind 분석·G1--G8 산술이
  `holdout_results.json`에 확정 → **washout 재채점 완료 및 washout 분석 확정 → 그
  이후에만** 개시. washout이 검토보다 먼저인 이유는 검토가 mismatch 행의 judge
  verdict를 노출하기 때문이다 — 순서가 뒤집히면 washout 재채점이 오염되어 G2가
  무효화된다.
- **AI 초안의 생성 조건.** mismatch 셀에 대한 AI(교정 대상 LLM과는 별 선언의
  보조 초안) 의견은 **primary 라벨 잠금·unblinding 이후에 생성**된 것만 허용되며,
  생성 시각이 unblind commit 시각보다 늦다는 provenance(`generated_at >
  --unblind-commit-time`)가 산출물에 남아야 한다. 시각 순서를 증명할 수 없으면
  그 초안은 사용하지 않는다.
- **검토 산출.** mismatch 셀마다 소유자(single author-rater, §3의 2차 채점자
  규약과 동일 인물 관례)가 `review_outcome ∈ {confirm_human, revise_human,
  unresolved}` + 자유노트. 산출 파일은 저장소 밖 별도 파일(`adjudication_review_*.csv`)
  이고, primary 라벨 CSV는 immutable이다.
- **통계 지위.** 이 단계에서 계산되는 것은 **기술 통계만** — mismatch 수, outcome별
  수, pre-review/blind vs post-review agreement 병기. 새 검정·gate 재채점·G1--G8
  재계산·bootstrap 재실행은 등록되지 않았다. 주 estimand과 수용 게이트는 §1.1/§2
  그대로, **blind Channel~2 라벨만으로** 계산된다.
- **논문 보고.** 사전등록된 blind 수치가 1차 결과다. post-review 수치는 AI-assisted·
  post-unblinding·descriptive임을 문장 수준에서 명시하는 보충 수치로만 등장한다
  (§9의 "disclosed, non-confirmatory" 관례와 동일 격식).

### 10.2 도구 (등록 경로, primary 분석 입력 아님)

mismatch worksheet 생성기(`cell_id, human A/L₁/note, judge verdict/span, view
pointer`)와 검토 UI는 `harness/`에 추가되며, label_assist와 같은 audit·session
규약(시각 로그, 편집 사유, 저장 위치 게이트)을 적용받는다. 산출물은 primary
분석기 `analyze_holdout.py`의 입력으로 연결되지 않는다 — 연결되는 순간 이 등록이
취소된다.

### 10.3 변경되지 않는 것

§1.0 A(v,q)·L₁* 정의, §Method Channel~1/2/3 구분, §1.1 estimand, §2 G1--G8,
§3 프로토콜 파라미터(세션 60/12h/washout ≥21일 포함), §4 통계 처리, §5 실패 정책,
§6--9 전부, `annotation/` 문서, CQ bank. 이 addendum은 검토 단계라는 **보조
채널 하나를 추가**할 뿐이고, 그 채널이 주 경로에 역방향으로 영향을 주는 경로는
위 순서 제약으로 구조적으로 봉인된다.

## 11. [2026-10-07 addendum] Protocol change — Channel~2 1차 pass를 AI-drafted, human-revised(AH) 모드로 등록. §10은 이 항에 의해 supersede된다

**결정 주체와 시점.** 2026-10-07 소유자(저자-rater)의 명시적 결정으로 등록한다.
§10과 같은 날, Channel~2 첫 라벨 저장 **이전**의 개정이다(검증: `<labels>/`의
작업 CSV sha256이 blank sheet와 여전히 일치, 실제 session log 없음). §9와
동일 성격의 protocol deviation이며, §9와 동일하게 전 과정을 고지한다.

**§10의 지위.** §10(unblinding 후 mismatch 검토 단계)은 실행되지 않으며 이
addendum이 대체한다. AI 초안-사람-교정이라는 검토가 이제 1차 pass 그 자체가
되었으므로, 사후 검토 채널은 존재 이유가 소멸한다. §10 원문은 개정 이력으로
그대로 남는다.

**AH 설계.** 셀마다 AI 초안(A, rater_L1, evidence span, 노트)이 라이터에게 먼저
제시되고, 라이터는 **확인하거나 수정한 뒤** 저장한다. 모든 행의 provenance
(초안 값, 초안 모델 ID·생성 시각, 사람 확인/수정 시각, changed flag)는 감사
sidecar에 영구 기록되며 저장 후 삭제·갱신이 감사 로그에 남는다. 라벨 스키마와
`analyze_holdout.py` 입력 계약은 불변 — provenance는 스키마 밖(sidecar)에 있다.

**초안의 judge-blind 조건(코드 검증 가능).** 초안 생성 입력은 (i) 라벨 시트
그 자체(`judge_evidence_span` 열 포함 — 이건 라이터도 보는 검증 대상이라 라이터와
동일 정보 집합)와 (ii) rendered view로 한정하고, verdict를 담은 `cells.jsonl`을
물리적으로 읽지 않는다. 생성 스크립트·에이전트 브리프는 공개 대상이며 입력 집합은
코드로 확인할 수 있다. 초안 파일은 라이터의 첫 확인 이전에 sha256으로 봉인된다
(`draft/SEAL.md`: 모델 ID, 생성 시각, 파일 digest).

**주장 격하 — 이것이 이 addendum의 핵심 대가.** AH 모드로 만들어진 라벨은
"독립 블라인드 인간 판정"이 아니며, 원고는 그 어떤 자리에서도 그렇게 주장할 수
없다.
- 1차 Channel~2 수치는 **human-adjudicated AI draft(AH)** provenance로 보고한다.
  AH와 judge의 일치율은 AI 초안의 앵커링 구조상 inflated 방향이며, 그 방향성을
  수치와 함께 명시한다.
- 이미 사전등록된 **2차 annotator n=48 subsample(§3, [2026-09-22])은 100%
  블라인드로 유지**된다 — 초안 파일을 제시하지 않는다. 논문의 독립 인간 앵커는
  이 48셀이며, 일치율·G1계 주장은 224(AH)와 48(blind)에 대해 병기 보고한다.
- 교정률(사람이 초안을 뒤집은 비율)과 그 범주 분포를 새로운 **기술 통계**로
  등록한다. 새 검정·bootstrap·gate 재계산은 아니다.
- G2 washout(72행)은 AH pass의 test--retest임이 논문에 명시된다. washout 화면엔
  초안을 제시하지 않는다(이미 등록된 표면·ID 교란과 무관하게 초안 파일 자체를
  washout 절차에 연결하지 않는다).
- 게이트 수치 기준(G1--G8 임계값)은 §2 그대로이며, 라벨 출처와 해석 명칭만
  바뀐다. 재계산·완화는 금지.
**동의서·가이드.** CONSENT와 LABELER_GUIDE는 서명 이전에 작업 설명을
"AI 초안을 검토하여 확인·수정한다"로 반영해야 하며, 2026-10-07판에 반영된다.

**레드라인(유지).** (a) AH 라벨을 blind human judgement로 서술 금지 — 초안
모델·시각은 원고 본문에 disclosed된다; (b) `J_judge` verdict는 저장 전까지
라이터에게 봉인 유지(기존과 동일); (c) 48셀 블라인드 무결성 — 초안 파일 유출 시
그 subsample을 폐기하고 논문에 쓴다; (d) 이 모드로 새 가설 검정을 추가하지 않는다.

**변경되지 않는 것.** §1.0 A(v,q)·L₁* 산식, §1.1 estimand, §2 게이트 정의와
임계값, §3 시드 20260913·세션 60/12h·washout ≥21일, §4 통계 처리, §5 실패 정책,
CQ bank, rubric, Channel~1/3. 이 addendum이 바꾸는 것은 1차 라벨의 **provenance
모드와 논문의 주장 명칭**뿐이다.

## 12. [2026-10-09 addendum] human pass 종료 후 작성 — 프로토콜 이탈 기록(D1–D20), 분석 코드 정합 교정, washout(G2)·2차 annotator 전향 프로토콜

**표기.** (확인함) = 이 작성(초안 또는 확정 과정)에서 파일·코드·커밋·로그를 직접 읽거나 실행해 확인한 것. [UNVERIFIED] = 확인하지 못한 것. [추정] = 근거를 밝힌 추론. 행 번호 `L###`은 별도 표기가 없으면 이 addendum을 덧붙이기 전의 `PREREG.md`(§1–§11, 1,184행, sha256 `20d0d5f30534502eb28a0d024ecbbcf5deb3ffdd5df9dc479607beb12297e731`)를 가리킨다. 이 addendum은 파일 끝에 덧붙으므로 L1–1184는 병합 후에도 같다. `main.tex`·`main_ko.tex`·`analyze_holdout.py`·`label_assist.py`의 행 번호는 커밋 `f855e62` 판 기준이다(그 뒤 다른 작업으로 줄이 이동했거나 작업 트리에서 수정 중이다). 미커밋 파일 `harness/persona_pass.py`의 행 번호는 2026-10-08 21:57 KST 수정본 기준이다. 시각은 따로 적지 않으면 KST(+09:00)다. "LOCK"은 `harness/real_run/annotation_locked/LOCK_2026-10-09.md`다. "AH 라벨"은 §11의 AH pass에서 나온 LLM-assisted (AI-drafted, author-revised) labels를 줄여 쓴 이름이다. 이 라벨을 검증된 라벨이나 reference라고 부르지 않는다.

### 12.0 시점

**이 addendum은 human pass가 끝난 뒤, 그리고 human-label 분석이 실행된 뒤에 확정되었다.** L5–6의 관례대로 원문을 남긴 채 개정 이력으로 덧붙이며, 시점을 아래와 같이 밝힌다. 시각의 출처는 git 커밋 시각, 잠금 기록(LOCK), 서버 세션 로그, 이 addendum을 쓴 에이전트 세션의 대화 기록(JSONL의 UTC 타임스탬프를 KST로 환산)이다.

| 시각(KST) | 사건 | 근거 |
|---|---|---|
| 2026-10-07 15:03:43–15:12:20 | AH 초안 생성: variant A–F별 Sisyphus-Junior drafter 세션 6개(D16) | opencode 세션 기록 |
| 2026-10-07 15:21:21, 15:23:47 | `draft_224.csv` 작성, 봉인. sha256 `9489552d…`이 LOCK L13과 같다 | 파일 mtime, `<labels>/draft/SEAL.md` L2, L8 |
| 2026-10-08 19:48:18 | 첫 라벨 저장. AH 초안 봉인보다 뒤다 | LOCK L27 |
| 2026-10-08 21:06–21:38 | LLM-persona 실행과 부분 산출(§12.5). 21:57에 봉인 | `SEAL_LEDGER.md` |
| 2026-10-08 23:58:55 | 마지막 저장 | LOCK L27 |
| 2026-10-09 00:05:15 | 서버 정지 | LOCK L28, 서버 세션 로그 |
| 2026-10-09 00:23:09 | 라벨 잠금 커밋 `f855e62`(작업 CSV, 감사 sidecar, 세션 로그, AH 초안 파일의 sha256 매니페스트; LOCK L6–13) | git |
| 2026-10-09 00:40:42 | 이 addendum의 초안 작성을 에이전트에 맡김 | 대화 기록 |
| 2026-10-09 01:07:19 | 초안 첫 판 기록(29,251자: D1–D15, DN-1–DN-10, §12.0–§12.7). 같은 에이전트가 01:08:02–01:09:44에 11회 수정 | 에이전트 세션 기록 |
| 2026-10-09 01:47:42 | 분석기 커밋 `ef62ef8`(§12.2의 교정; 합성 fixture 테스트) | git |
| 2026-10-09 01:47:49 | human-label 분석 실행(등록 설정, strict-tie 민감도, LLM 보조 재계산). 출력 파일 mtime 01:47:50–01:47:52 | 대화 기록, 파일 mtime |
| 2026-10-09 01:51:35 | 결과 커밋 `b66f532`(rater-safe 집계; G4·G5와 셀 단위 값은 봉인) | git |
| 2026-10-09 02:18:55 | 하드닝한 분석기(커밋 전)로 같은 입력을 다시 분석해 비교(출력은 저장소 밖). 수치는 같았다 | 대화 기록 |
| 2026-10-09 02:20:48–02:21:09 | 초안 수정: D9 재작성, D16·D17 추가, 머리글 D1–D15 → D1–D17 | 에이전트 세션 기록 |
| 2026-10-09 02:21:09 | 하드닝 커밋 `0dbe6e9` | git |
| 2026-10-09 02:42:28 | 하드닝 판으로 같은 입력을 다시 분석(보존용). 수치는 같았다 | 대화 기록, `results_human_pass/README.md` L69–76 |
| 2026-10-09 02:43:36 | 커밋 `9189ccf`: rater-safe 결과를 하드닝 재실행에서 다시 만들고 순서 5분위별 평균 rater_L1을 제거 | git |
| 2026-10-09 03:10:30–03:11:05 | 초안 수정: D18 추가, 머리글 D1–D18, §12.2 (7)의 이유 목록에 D18 추가 | 에이전트 세션 기록 |
| 2026-10-09 07:36:52 | 저자가 추천안을 모두 승인(원문 대신 결정 요지). 같은 메시지에서 D3의 Claude 사용이 웹 채팅이었다고 보고 | 대화 기록 |
| 2026-10-09 07:49:15 | 저자가 세션당 60셀·세션 간 12시간 제한의 제거를 지시(결정 요지). D3의 모델을 Claude Sonnet 5.5로 보고 | 대화 기록 |
| 2026-10-09 07:49:50 | 저자: washout과 2차 annotation에서 AI 도구 허용(D20). 이어서 D19·D20 추가, DN-5·DN-6·DN-7 수정 | 대화 기록 |

**AH 초안과 §11 등록의 선후.** AH 초안은 2026-10-07 15:03:43–15:12:20에 생성되었고, `draft_224.csv`는 15:21:21에 작성되어 15:23:47에 봉인되었다. §11을 등록한 커밋 `dbdad70`과 `--draft` 모드를 넣은 커밋 `a0312c4`는 둘 다 2026-10-07 15:28:37(+0900)이다(`git log`, 확인함). 따라서 초안의 내용은 §11 등록 커밋보다 먼저 확정되었다. 첫 라벨 저장(2026-10-08 19:48:18)은 그 뒤이므로 §11의 "첫 라벨 저장 이전의 개정"(L1135)은 성립한다. §11 본문은 초안 파일을 라이터의 첫 확인 이전에 봉인한다고만 적었고(L1154–1155) 초안을 등록 뒤에 생성한다고 적지 않았으므로, 이 선후를 이탈로 기록하지 않고 사실로만 적는다. 참고로 §10·§11이 검증 근거로 적은 "실제 session log 없음"(L1075–1077, L1135–1136)과 관련해, 서버 세션 로그에는 §10 등록(14:59:12) 이전에 시작한 저장 0의 세션 S1(13:47:33)과 S2(14:20:28)가 있고 S2 안에 `12H_ACK_OVERRIDE` 기록(14:50:45)이 있다. 이 세션들이 QA였는지는 기록이 없다 [UNVERIFIED]. 저장된 라벨은 없었다.

**초안은 분석 전에 커밋되지 않았다.** 초안 첫 판은 "human-label 분석을 실행하기 전에 이 addendum 초안(또는 그 sha256)을 커밋하라"고 권고했으나 이행되지 않았다. 초안은 분석 실행 전에 쓰였지만(01:07:19) 커밋도 해시 기록도 없었고, 이 addendum이 병합될 때까지 git에 없었다(`git log --all`에 이력 없음, 확인함). 따라서 첫 판이 분석보다 앞섰다는 것은 에이전트 세션 기록의 타임스탬프로만 확인되며 git으로는 증명되지 않는다. 03:11 판 초안(`paper/access2026/PREREG_ADDENDUM_12_DRAFT.md`, 마지막 수정 03:11:05, sha256 `38090dad3b08f03651d8c61af9d2e35530fb0eea7e41002859473fd65d8a0261`)은 이 addendum과 함께 커밋한다. 둘을 비교할 수 있게 하기 위해서다.

**분석 실행과 교정 코드.** human-label 분석은 2026-10-09 01:47:49에 실행되었고 결과 커밋은 `b66f532`(01:51:35)다. 분석기 `ef62ef8`(01:47:42)은 실행 전에 커밋되었다. §12.2의 교정은 `ef62ef8`에 있다. 하드닝 커밋 `0dbe6e9`는 그 뒤에 들어갔고, 같은 입력의 재실행에서 같은 수치를 냈다(`harness/real_run/results_human_pass/README.md` L69–76).

**분석 이후에 초안에서 바뀐 것.** 대화 기록의 편집 이력(첫 Write와 이후 모든 Edit·sed)을 순서대로 적용하면 현재 초안 파일과 정확히 같아진다(확인함). 따라서 분석(01:47:49) 이후에 초안 파일에 들어간 편집은 위 표의 두 묶음(02:20–02:21, 03:10–03:11)뿐이다. 07:49 이후의 변경은 초안 파일(그대로 둠)이 아니라 이 확정 본문에 들어갔다.
- D9: 첫 판은 Holm family 크기를 1로 적었다(A→B만 계산 가능하므로 보정 p = 원래 p). 분석기(`ef62ef8`)는 처음부터 등록된 family m=2로 구현되었고 분석도 m=2로 실행되었다. 초안은 분석 뒤(02:20:48)에 m=2(보정 p = min(1, 2p))로 고쳐졌다. 보정 p가 커지는(더 보수적인) 방향이며 등록된 family(L305, L599)와 같다.
- D16, D17, D18: 분석 뒤에 추가되었다(02:20:54, 03:10:44). D18은 첫 판의 '부기'에 있던 한국어 번역 표시 관찰을 옮기고 사실로 대체한 것이다.
- 머리글의 항목 수와 §12.2 (7)의 이유 목록(D18 추가).
- 이 확정 작업(07:49 이후)이 더한 것: D19·D20, DN 결정 반영, DN-5·DN-6·DN-7의 문구 변경, 초안에서 대조 표시가 붙어 있던 항목(세션 로그, SEAL_LEDGER, 승인 시점 줄)의 확인 결과, 사실 정정. 정정은 D5(S7 시작 시각을 세션 로그로 바로잡음), D2 (d)(확정 재계산값 반영), §12.2 (8)(분석기는 입력 해시를 기록하지만 실행 전에 LOCK과 대조해 거부하지는 않는다), D11의 행 번호(`calibration/README.md` L11–12 → L11–14), D16(초안 생성기의 모델과 입력), §12.5(봉인 전 부분 집계 열람)다.

**제안 시점별 결정.** DN-1–DN-10은 모두 분석 이전의 첫 판(01:07–01:09)에 제안안(추천 포함)으로 있었다. 분석 이후에 추가되거나 바뀐 것은 D9, D16–D20과, 저자 승인 이후 바뀐 DN-5(세션 한도 제거, AI 도구 허용)·DN-6(명칭)·DN-7(근거 문구)이다. 여기에 DN-8 결정문, §12.4의 추출 코드·직렬화·sha256(라벨·J를 읽지 않는 절차이나 분석 뒤 확정)이 더해진다. 이 addendum의 검토 뒤에 확정한 것도 분석 이후다: G2 계산의 정의(§12.3), 표본 선택 절차의 고정(DN-3, DN-4a), G3-W의 판정 규칙(DN-7), §12.4의 통계 정의(DN-10). 저자의 승인과 변경 지시는 모두 분석 이후다.

**저자가 승인(2026-10-09 07:36:52) 시점에 알고 있던 것.**
- 분석 이전부터: 라벨의 주변분포와 과정 지표(LOCK L21–37: primary A=1 138 / A=0 50, 초안 대비 수정 수, dwell, 세션 override), 그리고 §9의 LLM 보조 결과(L1040–1052).
- 분석 이후의 집계 요약: Coverage(L₁\*), A→B 대조, π̂, G1과 G7의 통과·실패 상태. 결과 커밋 `b66f532`(01:51:35) 이후의 보고로 받았다.
- 저자에게 봉인된 것: G4·G5의 값(judge 대 rater 일치도)과 셀 단위 결과(`harness/real_run/results_human_pass/SEALED_until_washout/`). washout 라벨 잠금까지 유지한다(§12.3 노출 통제). 이 addendum은 그 값을 담지 않는다.
- 봉인의 균열: `b66f532`에 커밋된 rater-safe 사본은 순서 5분위별 평균 rater_L1을 담고 있었다. 이 값을 judge-only J 요약과 함께 읽으면 평균(J − rater_L1)의 부호를 알 수 있다(G4·G5 값 자체는 아니다; `results_human_pass/README.md` L52–53, L78–80). `9189ccf`(02:43:36)가 이 항목을 지웠다. 저자가 이전 사본을 열었는지는 기록이 없다 [UNVERIFIED].

**전향 범위.** §12.3(washout), §12.4(2차 annotator), D19, D20만 전향적(prospective) 등록이다. washout 라벨과 2차 annotator의 라벨은 아직 존재하지 않는다. 다만 이 등록은 AH pass의 집계 결과를 안 상태에서 이루어졌다. 나머지는 이미 일어난 일의 기록이므로 "결과를 보기 전"의 개정이 아니다. human pass 종료, 라벨 주변분포 관측, J와 라벨을 결합한 분석 실행, 집계 결과 열람 이후의 개정이다.

**작성 방식.** 이 addendum의 초안과 확정은 AI 에이전트(Claude) 세션이 저장소의 문서·코드·커밋과 로그를 읽고 썼다. 초안 작성 단계에서는 `<labels>/`와 `harness/real_run/persona_pass/`를 열지 않았다(초안 머리말). 확정 작업도 라벨 값(작업 CSV, 감사 sidecar, 초안 CSV의 내용)과 봉인된 결과(`SEALED_until_washout/`, `locked_labels/sealed_results_until_washout/`), persona 산출물은 열지 않았다. 확정 작업이 `<labels>/` 아래에서 읽은 것은 잠금 세션 로그, 잠금 해시 목록, AH 초안 봉인 기록(`draft/SEAL.md`)이고, 잠금 파일은 `sha256sum -c`로 해시만 대조했다(네 파일 모두 일치, 확인함). `harness/real_run/persona_pass/`에서는 `SEAL_LEDGER.md`만 읽었다. 초안 생성기의 출처(D16)를 확인하려고 opencode 데이터베이스와 사용 기록은 모델·시각·건수와 세션 제목만 질의했다.

### 12.1 이탈 기록 (D1–D20)

항목마다 등록 내용, 실제, 근거, 처리를 적는다. D1–D18은 이미 일어난 일의 기록이고, D19·D20은 아직 일어나지 않은 절차에 대한 전향적 변경이다.

**D1 — confirmatory judge 신원.**
- 등록: freeze block L20은 `qwen-next-flash`(2026-09-21 세 번째 재결정, L116–276)를 confirmatory judge로 적는다.
- 실제: 224셀 holdout은 `gemini-3.6-flash`로 채점되었다. `harness/real_run/MANIFEST.json`: `judge_model=gemini-3.6-flash`, `endpoint_host=generativelanguage.googleapis.com`, `judge_extra_body.google.thinking_config.thinking_level=minimal`, `generated_utc=2026-09-21T06:09:38Z`, `completed_cells=224`. 커밋 `700f6dc`(2026-09-21 15:10:53 +0900)(확인함).
- 이 전환을 기록한 addendum은 없다. L256 이후 PREREG에서 gemini가 나오는 곳은 §8의 지나가는 서술 하나(L974, "confirmatory judge인 gemini-3.6-flash")뿐이고 freeze block은 바뀌지 않았다(확인함, grep).
- 순서(확인함): 폐기된 Gemini 부분 실행에서 224셀 중 65셀이 유효하게 파싱되고 158셀이 HTTP 429로 실패했다(L121–126; `harness/real_run_gemini_partial_DISCARDED/README.md`). 다음으로 `qwen-next-flash` 시도가 context 한도 때문에 B–F를 채점하지 못했다(L221–256; `harness/real_run_qwen_attempt1_DISCARDED/MANIFEST.json`, 2026-09-21T03:02:30Z). 마지막으로 backoff를 붙인 `gemini-3.6-flash` 재실행이 224셀을 채점했다. 이 선택은 모든 사람 라벨(첫 저장 2026-10-08 19:48:18 KST)과 §8의 LLM 보조 체크(2026-09-22)보다 앞서지만, 폐기된 실행의 65셀 유효 점수가 생긴 뒤였다. 그 점수를 선택 전에 열람했는지는 기록이 없다 [UNVERIFIED].
- L598은 사후 confirmatory judge 선택을 금지한다. 이 addendum은 이 전환을 L598 위반이 아니라고 면책하지 않는다. 이탈로 기록할 뿐이다.
- 처리: 데이터는 `gemini-3.6-flash` 점수를 그대로 쓴다(재채점 없음). 원고는 이 judge를 "pre-registered"라고 부르지 않는다. `main.tex`(`f855e62` 판) L863–871("fixed *a priori* … run fresh and not post hoc … before scored data existed")과 L1646–1647("The pre-registered confirmatory judge (gemini-3.6-flash)")은 이 기록에 맞게 고친다. freeze block L20 원문은 고치지 않는다. 부수 사실: extraction(Qwen)과 judge가 같은 계열이라는 L131–145의 self-enhancement 우려는 실제 데이터에는 해당하지 않는다. 대신 G6의 non-Qwen 성분은 계산할 수 없다(D10).

**D2 — 사람 라벨 분석 전에 교정하는 분석 코드 결함.** `f855e62` 판 `harness/analyze_holdout.py`(이하 분석기)에서 확인함:
- (a) control 혼입. `analyse()`가 control 36셀(ablated 24, preserved 12)을 primary 셀과 섞어 Coverage(`by_variant`, 분석기 L880–881), 확인적 대조(분석기 L897의 `lo_by_q`: 같은 (variant, cq_id)의 control 쌍둥이가 primary 셀을 덮어쓸 수 있다), G1(분석기 L923), G5·G6(fragility 포함)·G7(분석기 L957–959)을 계산했다. 등록된 모집단은 primary 셀이다. control은 별도 장치이며(PREREG L453–454) control을 쓰는 게이트는 G3뿐이다(PREREG L345).
- (b) G7이 라벨 감사 기록이 아니라 judge 실행 telemetry를 읽었다. `_g7`(분석기 L797)이 읽는 `started_at_utc`/`elapsed_s`/`attempt`/`artifact_digest`는 judge 호출의 시각·소요 시간·시도 횟수다(`harness/run_holdout.py` L1180–1201).
- (c) G3이 존재하지 않는 verdict 필드를 찾았다. `_cell_verdict`(분석기 L555–565)는 `verdict`, `evidence_verdict` 등을 찾지만 `cells.jsonl`의 `judge_response`에는 `score`와 `evidence`만 있다. 어떤 입력으로도 G3을 계산할 수 없었다.
- (d) 이미 공개된 LLM 보조 수치(§9 L1040–1052, `harness/real_run/llm_auxiliary_results.json`)는 (a)의 영향을 받은 값이다. 교정한 분석기(`ef62ef8`)로 §9와 같은 입력(LLM 보조 라벨, 사람 라벨 아님)을 다시 계산하면 값이 달라진다: G1 사건 cluster 수 8 → 7, 97.5% 상한 0.4226 → 0.3891(fail 유지), A→B 판정은 unresolved 유지. 확정 재계산은 `harness/real_run/results_human_pass/llm_aux_corrected.json`(sha256 `aec993604aeb5669f9a31ade8df6d23492f75a8efdd5a50136bcd55c2feb0dfc`, 하드닝 판 `0dbe6e9`로 2026-10-09 02:42 KST 생성)에 있고 초안 작성 중의 점검값과 같다(확인함).
- 처리: §12.2.

**D3 — AH pass 중 등록되지 않은 LLM 보조.** 등록된 AI 초안(§11) 외에, rater(저자)가 primary 셀의 약 절반에서 Claude(Anthropic)에게 A 판단 제안과 evidence span 위치를 물었다고 2026-10-09 분석 전에 보고했다(LOCK L39–45). note 일부는 view 텍스트를 복사하고 짧은 코멘트를 붙인 것이다. 사용 경로와 모델은 분석 뒤에 저자가 추가로 보고했다(2026-10-09 07:36, 07:49, 대화 기록).
- 경로(저자 보고): Claude Code가 아니라 claude.ai 웹 채팅이다. 모델은 Claude Sonnet 5.5(저자 보고)다. 보조자는 저장소, judge run 파일, 초안 파일, 어떤 결과에도 접근하지 못했다.
- 입력(저자 보고): 셀의 약 절반에서 보조자는 저자가 붙여 넣은 텍스트만 보았다. 라벨 화면에서 복사한 셀 텍스트와 짧은 코멘트다. 용도는 A 제안과 evidence span 위치 찾기였다.
- 기록: 어느 셀이 보조를 받았는지는 기록되지 않았다. "약 절반"이라는 범위는 자기보고이며 셀 단위로 검증할 수 없다 [UNVERIFIED]. 정확히 무엇을 붙여 넣었는지도 기록이 없다 [UNVERIFIED].
- 화면이 보인 것(확인함): 라벨 화면은 judge가 인용한 근거 span을 회색 상자에 보였다(`harness/label_assist.py` L657–658; span이 비어 있으면 "(judge span 없음)"을 표시, L897). 시트에는 J 열이 없고(12열, L268–271) 화면 어디에도 J 값은 없다. 도움말(L560–563)과 `annotation/packet/LABELER_GUIDE.md` L56은 J와 judge 근거를 보거나 기록하지 말라고 적는다. 따라서 화면에서 복사한 텍스트에는 이 셀들에서 judge가 인용한 span이 들어갔을 수 있고, 그 span이 비어 있었는지도 드러났을 수 있다. J 값 자체는 화면에 없었으므로 화면에서 복사한 텍스트에는 들어 있지 않다(저자가 다른 경로로 J를 알았는지는 D12). 다만 이 run에서 span이 비어 있는 경우는 J=0과 일치하므로(D16), "(judge span 없음)"이 붙여 넣은 텍스트에 있었다면 J=0이 간접적으로 전달되었을 수 있다. 붙여 넣은 텍스트에 AI 초안 카드(`label_assist.py` L860–865)나 한국어 번역(D18)이 들어갔는지는 알 수 없다 [UNVERIFIED].
- 처리: 이 라벨은 "LLM-assisted (AI-drafted, author-revised) labels"로만 서술한다(§11 L1157–1160, L1176–1177). 검증된 라벨이나 reference라고 부르지 않는다. 라벨 기반 통계는 탐색적으로 보고한다(§12.2 (7)). 보조 여부로 셀을 나누는 분석은 기록이 없어 할 수 없으므로 하지 않는다. washout과 2차 annotation에서는 AI 도구를 허용하되 세션을 마칠 때 사용 여부, 도구 이름, 대략의 셀 수를 세션 로그에 적는다(D20).

**D4 — G7 실패(체류 시간).** primary 셀의 dwell(서버 기록 `elapsed_s`, 페이지 로드부터 저장까지)은 중앙값 9.3초(IQR 7.7–11.5)이고 91.0%가 20초 미만이다(LOCK L29–31). 등록 기준은 "20초 미만 셀 < 3%"(L349)이고, 계획한 셀당 시간은 약 90초다(L455; `OWNER_RUNBOOK.md` L76; `LABELER_GUIDE.md` L60). G7의 나머지 두 조건(unblind 전 타임스탬프, 사후수정 0)은 §12.2의 교정 코드로 계산했고 충족했다(확인함: 라벨된 primary 셀의 저장이 모두 boundary보다 앞서고, boundary 이후의 저장과 사후수정은 0). 20초 조건이 충족되지 않으므로 G7은 실패다. AH 모드에서 초안을 확인만 하고 저장하면 체류가 짧을 수 있다는 점은 설명은 되지만(초안의 출처와 입력은 D16), 기준(L349)은 모드를 구분하지 않는다. 이 addendum은 기준을 바꾸지 않고 빠른 셀을 사후에 제외하지도 않는다.
- 처리: G7 = fail로 보고한다. 라벨 기반 통계는 탐색적으로 보고한다(§12.2 (7)). 수치는 LOCK과 분석기 출력이 같다(20초 미만 171/188).

**D5 — "변경되지 않는다"로 등록된 세션 한도를 중도에 해제.** 등록: 세션당 최대 60셀, 세션 간 12시간 이상(L550). §11은 이 한도를 변경되지 않는 것으로 다시 적었다(L1182; §10.3 L1127도 같다). 실제(LOCK L34–37, 커밋 메시지, 서버 세션 로그 `primary_working.csv.session_log.txt`; 확인함):
- 60셀 상한은 라벨러 요청으로 S7 이전에 제거되었다(`feee347`, 2026-10-08 22:10:31 +0900).
- 12시간 간격은 `12H_ACK_OVERRIDE`로 네 번 넘겼다: 2026-10-07 14:50:45, 2026-10-07 16:23:45, 2026-10-08 19:47:33, 2026-10-08 22:24:07. 앞의 두 건은 첫 저장(2026-10-08 19:48:18)보다 이르다.
- 그 뒤 간격 gate 자체를 코드에서 제거했다(`9e4ba6d`, 22:27:25). 세션 로그에는 이 커밋 뒤에 시작한 세션이 없다. 따라서 이 빌드는 라벨을 서빙하지 않았다.
- 세션별 저장 수(세션 로그): 세션은 7개(S1–S7)이고 저장 수는 S1–S5가 0, S6이 60, S7이 140이다(합계 200 = primary 188 + control 12; LOCK L21–26과 같다). S6은 2026-10-08 19:46:03–22:10:39이고 저장 수가 상한 60과 같다. S7은 22:10:39–2026-10-09 00:05:15이며 `--defer-controls`(36행 미서빙)로 시작해 140셀을 저장했다. 22:24:07의 override는 S7 시작(22:10:39)의 13분 28초 뒤로 S7 안에 있다. 초안의 추정(22:24:07을 S7의 시작으로 읽음)은 세션 로그와 맞지 않아 고쳤다.
- 처리: 이탈로 기록한다. 순서 드리프트 진단(L551; §12.2 (5))에 세션별 요약을 넣는다. washout과 2차 annotation에는 L550의 한도를 적용하지 않는다(D19; §12.3 DN-5, §12.4).

**D6 — control이 미공지가 아니었고, 표시 결함이 있었다.** 등록: ablated 대조는 "미공지, 무작위 큐에 삽입"(L453), preserved 대조는 과잉교정 방어(L454), G3은 24개 중 22개 이상(L345). 실제(확인함):
- `cell_id`가 `ablated_control:F:CQB05`처럼 셀 종류·variant·CQ를 그대로 담는 형식이었고(`harness/run_holdout.py` L1095, L1104), S6까지 화면 헤더에 보였다(LOCK L23–25; `feee347`에서 숨김).
- S6에서 라벨된 control 12개(ablated 8, preserved 4)는 모두 표시 결함을 안고 있었다. 라벨 시트는 ablated control에 judge가 본 ablated view 대신 해당 variant의 원본 view(`harness/variants/{v}/rendered_view.txt`)를 가리키고(24/24), preserved control에 judge가 본 paraphrase 대신 원 CQ 문장을 담았다(12/12가 원문, 0/12가 paraphrase). `cells.jsonl`에 `question` 필드가 없어 패킷 빌더가 뱅크 원문으로 대신 채웠기 때문이다(`annotation/packet/build_label_packet.py` L130–145; judge 쪽 구성은 `harness/run_holdout.py` L1086–1109).
- 나머지 24개는 서빙되지 않았다(`--defer-controls`, S7).
- 처리: control 36개를 모두 사람 라벨 기반 분석에서 제외한다. 라벨된 12개의 값은 읽지 않고 라벨이 있는지만 센다. 등록된 G3은 계산 불가로 보고한다(§12.2 (4)). washout에서 대신 측정하는 방법은 §12.3 DN-7에서 정했다.

**D7 — washout 패킷(2026-09-21)이 등록 내용을 따르지 않는다.** 패킷은 `annotation/packet/labels_washout_reassessment_pass_blank.csv`이고 그 바이트 사본이 `harness/real_run/annotation_pending/washout_pass_72_ready_to_fill.csv`다(sha256 `ca854a18…`, `annotation_pending/DIGESTS.txt` L7). `build_label_packet.py`로 2026-09-21에 만들었다(커밋 `3e3a9e4`). 확인함:
- 같은 ID: 72행 모두 1차 패스와 같은 `cell_id`이며, 이 ID는 셀 종류·variant·CQ를 그대로 담는다. L523의 "새 ID"를 따르지 않는다.
- 같은 CQ 문장: 72행 모두 1차 시트와 같은 `cq_text`이고 paraphrase가 없다(`cluster_id`도 72행 모두 `cq_id`와 같다). L523의 "cluster paraphrase 제시"를 따르지 않는다. "새 위치"만 충족한다(같은 위치 0/72).
- 강화층 없음: (category × judge 점수대) 비례 배분 72개뿐이고 24개 불일치 강화층이 없다(`build_label_packet.py`의 `_washout_selection` L217–240, 주석 L224–226 "The extra ASK-conflict enrichment must be reviewed/selected by the project owner"). PREREG L466–468을 따르지 않는다.
- seed: 선택과 순서를 seed 20260914(`build_label_packet.py` L20의 `WASHOUT_REASSESSMENT_SEED`)로 정했다. L14는 등록 seed 20260913이 제시 순서와 "any stratified draw"를 정한다고 적는다.
- control 포함: 72행 중 12행이 control(ablated 6, preserved 6)이라 primary는 60행이다. control을 G2에서 빼면 L456의 "72, 이 아래로 내리지 말 것"보다 적다.
- 같은 CQ를 20위치 이상 떨어뜨리는 제약은 72행에서 수학적으로 만족할 수 없어 달성 간격이 10이다(§7 L951–954).
- 이 패킷은 한 번도 서빙되지 않았다. 처리: §12.3에서 다시 만든다(DN-2). 기존 파일은 기록으로 남기고 지우지 않는다.

**D8 — G1 신뢰수준이 정해지지 않았다.** L387–390이 미해결로 남긴 불일치가 그대로다. §4 L564는 0사건에 단측 97.5% Clopper–Pearson을 쓰고, `main.tex` 분석계획 표(Table `tab:analysisplan`, L1096–1099)는 단측 95%를 적는다. `annotation/CALIBRATION_PLAN.md` L31–36은 둘을 함께 적고, `DECISIONS/G1_confidence_level.md`는 95%를 추천했지만(같은 파일 L67–75, "추천이지 결정이 아니다") 결정 기록은 없다. 분석기 기본값은 `alpha=0.025`(97.5%)이며 데이터 이전부터 그랬다(분석기 L73, L865, L996). L805–812가 예고한 대로 실제 cluster 수는 33이다(CQB15/22/23이 모든 variant에서 빠짐, §6-2). n=33에서 단측 Clopper–Pearson 상한(확인함, `scipy.stats.beta.ppf`)은 0사건일 때 97.5%에서 10.58%, 95%에서 8.68%이고, 1사건일 때 95%에서 13.59%다. 97.5%에서는 0사건이어도 G1을 통과할 수 없고(0사건 통과에 필요한 최소 cluster 수는 36), 95%에서는 0사건일 때만 통과한다.
- 처리: §12.2 (6), DN-1(결정: 97.5%로 판정).

**D9 — B→B′는 계산할 수 없다. Holm은 등록된 family 크기 m=2로 적용한다.** 확인적 family는 A→B와 B→B′ 두 개다(L305; `main.tex` Table `tab:analysisplan`; L599). Brick holdout에서는 B′ variant가 채점되지 않았다(`cells.jsonl`의 variant는 A–F뿐, 확인함; §9 L1044–1045). B→B′는 계산 불가 구성원으로 family에 남기고, A→B의 보정 p는 min(1, 2p)다(분석 코드 `contrasts_family`, 커밋 `ef62ef8`).
- 처리: 출력과 원고 모두 family 크기를 2로 적고 B→B′를 not computable로 표시한다. B→B′를 다른 데이터로 대신하지 않는다. 이 항목은 분석 뒤에 m=1에서 m=2로 고쳐졌다(§12.0).

**D10 — G6의 non-Qwen 성분을 계산할 수 없다.** G6은 A→B 일관성, non-Qwen judge 방향 일치, fragility K ≥ 6으로 이루어진다(L348, L582). holdout에는 confirmatory judge 하나의 점수만 있고 비교할 judge의 점수가 없다(`cells.jsonl`에 해당 필드가 없다; `_g6`은 "non-Qwen judge scores are absent"로 not_computable을 낸다). confirmatory judge 자체가 non-Qwen 계열이라는 사실(D1)로 이 성분이 충족되었다고 읽지 않는다. 그것은 사후 재해석이다.
- 처리: G6 = not_computable. A→B 일관성과 fragility K는 따로 기술적으로 보고한다.

**D11 — calibration 연습 문항의 출처.** 등록: 연습 12셀은 legacy Ontology-101 아티팩트에서만 뽑고 연구 아티팩트에서는 뽑지 않는다(L552). 실제: `harness/real_run/annotation_pending/calibration/practice_items_13.csv`의 13개는 연구 variant A(10개)와 B(3개)의 제외 셀이다(`calibration/README.md` L11–14, 확인함). 연습을 실제로 했는지, 결과와 해석 메모가 남았는지는 확인하지 못했다 [UNVERIFIED].
- 처리: 이탈로 기록한다. 연습 결과는 어떤 통계에도 쓰지 않는다.

**D12 — 라벨링 전에 rater가 LLM 보조 G1 결과를 알고 있었다.** `harness/real_run/annotation_pending/OWNER_RUNBOOK.md` L134–135는 rater에게 "The sealed LLM auxiliary check already failed it (0.42)"라고 적었다. rater가 저자이므로 같은 수치는 §9 L1046–1047과 원고에도 있었다. 또 셀 단위 LLM 보조 라벨(`harness/real_run/llm_auxiliary_labels.jsonl`, 224행, gpt-5.6-luna로 생성: §8 L971·L983)과 judge 점수 파일(`harness/real_run/cells.jsonl`)이 라벨링 전부터 같은 저장소 안에 있었다. L22–24는 answer key를 평가자가 읽는 디렉터리 밖에 두라고 하며 "자가채점 저자에게 answer key 동거는 이론적 누출이 아니다"라고 적는다. `cells.jsonl`은 rater용 디렉터리(`annotation_pending/`) 밖에 있었지만 막는 장치는 지시문뿐이었다(`OWNER_RUNBOOK.md` L75–76). rater가 이 파일들을 열었는지는 기록이 없다 [UNVERIFIED].
- 처리: 이탈로 기록하고, 원고에 rater가 라벨링 전에 알고 있던 정보로 공개한다.

**D13 — human pass 규모가 문서마다 다르다.** L309는 human pass가 "1차 도메인 216셀에만" 있다고 적고, L455는 1차 패스 합계를 324(216 + 2차 도메인 72 + ablated 24 + preserved 12, L451–454)로 적는다. §6-2(L774)가 primary를 216에서 188로 줄였다. 실현된 것은 224행 시트(primary 188 + control 36)에서 primary 188/188과 control 12/36에 대한 라벨이다(LOCK L21–26). 2차 도메인 72셀과 raw-TTL 24셀(L457)의 human pass는 수행되지 않았다. 저장소에서 해당 시트나 라벨을 찾지 못했다 [UNVERIFIED: 저장소 검색 기준의 부재 확인].
- 처리: 원고는 실현된 규모(primary 188)를 쓴다. L309와 L455 원문은 남긴다.

**D14 — 2차 annotator 48셀은 아직 실행되지 않았고, CVI는 등록되어 있지 않다.** L470–518의 2차 annotator subsample은 아직 실행되지 않았다(LOCK L49–50). §11은 이 48셀을 AH pass와 나란히 보고하도록 했다(L1163–1165). 이 addendum은 그 라벨을 "second, non-author annotator"의 라벨로 부른다. "CVI"는 PREREG 어디에도 등록되어 있지 않다(grep 0건). 저장소에 약어 정의가 없어 content validity index로 읽었다 [UNVERIFIED].
- 처리: §12.4.

**D15 — 원고가 약속한 hash-chained 타임스탬프가 없다.** `main.tex` L1970–1972는 "a dry run on permuted labels", "tagging the label file before any script touches a judge score", "hash-chained per-cell timestamps"를 약속한다. 실제: 라벨을 서빙한 `harness/label_assist.py` 빌드(`84e3c9d`, `feee347`)의 감사 sidecar에는 hash chain이 없다. `hashlib`은 view sha256 확인에만 쓰인다(확인함). 라벨은 git tag가 아니라 SHA-256 매니페스트 커밋(`f855e62`, LOCK L6–13)으로 고정했다. 저장소의 tag는 `access2026-cqbank-brick-v1-freeze` 하나뿐이다(확인함). permuted-label dry run을 실행한 기록은 찾지 못했다 [UNVERIFIED].
- 처리: 원고 문장을 실제 절차(매니페스트 해시, 연쇄되지 않은 감사 로그)에 맞게 고친다. hash chain을 사후에 만들어 붙이지 않는다.

**D16 — judge 점수 블라인드가 부분적이다.** 등록: judge-score-blind 라벨링(L541), 판정은 저장 전까지 봉인(L1177–1178). 실제:
- 화면(확인함): 라벨 화면이 judge가 인용한 근거 span을 보여 주었다(`label_assist.py` L657–658, L897). 시트에는 J 열이 없고 화면에 J 값은 없다(D3).
- 이 run에서 span이 비어 있는 경우는 224셀 모두에서 정확히 J=0과 일치한다(`results_human_pass/legacy_counts.json`의 `checks.judge_span_empty_iff_J0_all_cells`; 이 스크립트는 judge run과 LLM 보조 라벨만 읽고 사람 라벨은 읽지 않는다. L979–980도 span이 없는 cell이 전부 J=0이라고 적는다). judge 프롬프트(`harness/run_holdout.py` L185–188)는 "verbatim span, or empty"만 요구하고 이 대응을 강제하지 않으므로, 이는 이 run의 경험적 성질이다. 따라서 J=0과 J≥1의 구분은 모든 셀에서 화면으로 알 수 있었다.
- AH 초안 생성기(§11은 초안의 모델과 입력의 공개를 요구한다)의 모델과 입력:
  - 모델: `Qwen/Qwen3.8-Flash-Next`다. 로컬 vLLM 엔드포인트가 로컬 OpenAI 호환 프록시 뒤에서 서빙했다. opencode 기록은 providerID `<internal-proxy>`, modelID `<internal-proxy>/Qwen/Qwen3.8-Flash-Next`, variant `medium`이다(opencode의 variant 필드이며 이 연구의 variant A–F와 무관하다). 서빙된 가중치와 양자화는 기록되지 않았다.
  - 파이프라인: opencode 1.18.34와 oh-my-openagent 플러그인(설치 버전 4.19.4 [추정])이다. orchestrator 세션이 `task(category=deep)`를 7회 호출했다. 6회는 variant A–F별 Sisyphus-Junior drafter 세션(2026-10-07 15:03:43–15:12:20)이었고, 1회는 `label_assist --draft` 모드와 검증기를 만드는 작업 세션(15:09:23–15:20:47)이었다. `draft_224.csv`는 15:21:21에 작성되고 15:23:47에 봉인되었다(`<labels>/draft/SEAL.md` L2, L8). sha256 `9489552d…`은 LOCK L13과 같다.
  - 기록의 한계: 초안 CSV의 `model` 열에는 모델 ID가 아니라 라벨 `agent-draft(Sisyphus-Junior-deep)`이 들어 있다. `SEAL.md` L4도 모델 ID 대신 "harness model id per config"라고 적었다. §11은 `draft/SEAL.md`에 모델 ID를 적는다고 했으므로(L1154–1155) 위 모델 ID는 이 addendum이 아래 로그에서 확인해 처음 기록하는 값이다(확인함). 생성·봉인 시각과 §11 등록 커밋의 선후는 §12.0에 있다.
  - 근거: `<agent-session-database>`의 message·session 필드(2026-10-07 15:00–15:25 구간의 메시지 202건이 모두 위 모델이고, 같은 구간의 Sisyphus-Junior 세션 7개가 모두 버전 1.18.34다); `<proxy-usage-log>`의 15:03:00–15:22:59 구간(Qwen/Qwen3.8-Flash-Next 성공 응답 209건, gpt-5.6 계열 호출 0건. 같은 구간에 `local` provider의 `qwen-next-flash` HTTP 502 응답이 23건 더 있다. 응답을 만들지 못한 호출이며 초안 생성과의 관계는 확인하지 않았다 [UNVERIFIED]); `<agent-config-file>`의 수정 시각 2026-10-04 14:42 KST(실행보다 앞선다). category deep의 모델 지정은 같은 파일 L14–16, L67–69라고 별도 에이전트가 확인했다(이 작성에서는 그 파일의 내용을 열지 않았다).
  - 입력: drafter는 라벨 시트 `annotation_pending/primary_pass_224_ready_to_fill.csv`(헤더: cell_id, cq_id, cluster_id, category, variant, cq_text, judge_evidence_span, rendered_view_path, evidence_span_verbatim, A, rater_L1, note; 확인함)와 자기 variant의 view만 보았다. 따라서 judge가 인용한 span을 보았고(rater 화면과 같은 노출이며, span이 비면 J=0과 일치한다), J는 보지 못했다(시트에 J 열이 없고 `cells.jsonl`·`llm_auxiliary*`에 접근하지 않았다; 별도 에이전트의 로그 대조). judge의 rationale도 보지 못했다. 이는 §11이 등록한 초안 생성 입력(라벨 시트와 view)과 같다. [UNVERIFIED: drafter 세션 하나의 bash 입력에 "verdict"라는 단어가 한 번 있고 출력은 없다. 그 내용은 열어 보지 않았다.]
- 처리: 이탈로 기록한다. 블라인드는 J∈{1,2,3} 사이에서만 성립한다. 초안도 같은 span을 읽었다.

**D17 — 불투명 ID 규칙과 다르게 variant와 cell_id가 보였다.** 등록: 불투명 항목 ID와 봉인된 매핑(L544–546). 실제: 라벨 화면이 모든 셀에 variant 표시를 보여 주었고(`label_assist.py` L873–874, 커밋 `3a3c824`(2026-10-07 13:34:29)부터, 첫 저장 이전; 확인함), S6까지는 전체 cell_id도 보였다(`feee347`이 헤더의 cell_id 줄을 지웠다).
- 처리: 이탈로 기록한다. variant 블라인드는 원래 주장하지 않았다(L538–542).

**D18 — 등록되지 않은 화면 변경: AI가 만든 한국어 CQ 번역 표시.** 등록: PREREG에는 번역된 CQ 문장을 라벨 화면에 보이는 규정이 없다(grep "번역"·"translation"·"Korean"·"한국어" 0건, 확인함). 실제:
- S6부터(첫 저장 2026-10-08 19:48:18 KST, LOCK L27) 라벨 화면은 영문 CQ 아래에 AI가 만든 한국어 번역을 보였다. 번역은 Claude Code로 만들었다(저자 보고; 원고 Acknowledgment (iv)와 같다).
- 표시 기능은 `label_assist.py --cq-ko`로, 커밋 `4bd18e3`(2026-10-08 19:33:59 +0900, 번역과 "핵심" 요지 줄)과 `84e3c9d`(19:46:01 +0900, 요지 줄을 빼고 번역만)에서 들어갔다(확인함, `git log`). 두 커밋 모두 첫 저장보다 앞선다.
- 화면은 번역 아래에 "번역은 참고용 — 판정은 영어 원문 CQ 기준"이라고 적었다(`84e3c9d`의 `label_assist.py` `_cq_ko_html`, 확인함). 즉 판정은 영어 원문을 따라야 한다고 안내했다.
- 서빙된 인스턴스에서 옵션이 켜져 있었다는 사실은 저자 보고다. 서버 세션 로그는 실행 옵션을 기록하지 않는다(`SESSION start` 줄에는 시각, pid, session_id, 초안 파일명, deferred 수만 있다; `label_assist.py` L277–281). 정황으로, 세션 S5(2026-10-08 19:34:01)와 S6(19:46:03)의 시작이 `4bd18e3`(19:33:59)와 `84e3c9d`(19:46:01) 직후이고 S7(22:10:39)은 `feee347`(22:10:31) 직후다(세션 로그, 확인함). 이는 코드가 바뀔 때마다 서버를 다시 시작했다는 뜻일 뿐 옵션이 켜져 있었다는 증거는 아니다 [UNVERIFIED]. S5는 저장이 0이고 첫 저장은 S6에 있다.
- 처리: 등록되지 않은 화면 변경으로 기록하고 원고에 공개한다(`main.tex` Table `tab:deviations` D18). 번역은 LLM 산출물이므로 D3과 같은 성격의 LLM 보조로 읽고, 라벨 기반 통계를 탐색적으로 보고하는 근거(§12.2 (7))에 더한다. washout과 2차 annotator 화면에는 번역을 보이지 않는다(§12.3 DN-2, §12.4).

**D19 — [전향] washout과 2차 annotation에 세션당 셀 상한과 세션 간 최소 간격을 두지 않는다(L550로부터의 이탈).** 아직 일어나지 않은 절차에 대한 전향적 변경이다(§12.3, §12.4와 같은 지위).
- 등록: 세션당 최대 60셀, 세션 간 ≥ 12시간(L550 "피로 관리"). §10.3(L1127)과 §11(L1182)이 이를 변경되지 않는 것으로 다시 적었다.
- 결정(저자, 2026-10-09; 원문 인용 대신 결정 요지): 세션당 60셀·세션 간 12시간 제한을 제거한다. washout(§12.3)과 2차 annotator(§12.4)에 세션당 셀 상한도 세션 간 최소 간격도 두지 않는다. L550의 두 한도만 제거한다. 같은 소절의 L551(순서 드리프트 진단)과 washout 최소 간격 21일(L522)은 바뀌지 않는다. 이 addendum의 초안은 L550 복원을 권고했으나 채택되지 않았다.
- 이미 실행된 AH pass가 같은 한도 없이 진행된 것은 D5가 기록한다. D19는 그 이탈을 앞으로의 두 절차에 적용하는 변경이다.
- 대가와 대체 기록: L550이 겨냥한 피로·순서 효과를 설계로 제한하지 못한다. 대신 세션 시작·종료 시각, 세션 수, 셀별 dwell(`elapsed_s`)을 기록해 보고하고 G7식 점검(20초 미만 비율과 3% 기준, 중앙값, IQR)을 낸다. 최소 체류는 강제하지 않는다(§12.3 DN-5).

**D20 — [전향] washout과 2차 annotation에서 AI 채팅 도구를 허용한다.** 아직 일어나지 않은 절차에 대한 전향적 변경이다(§12.3, §12.4와 같은 지위).
- 등록: 등록된 본문은 annotator의 AI 도구 사용을 다루지 않는다. §3의 2차 annotator 규정(L470–518)과 §11(L1163–1179)에는 AI 도구 사용의 허용도 금지도 없다(grep, 확인함). 등록된 것은 AI 초안(AH 초안 파일)의 비제시뿐이다(L1163–1165, L1168–1169, L1176–1178). 이 addendum의 초안(첫 판 2026-10-09 01:07)은 두 절차에서 AI 도구를 금지하고 "미사용"을 자기신고하라고 권고했으나 채택되지 않았다.
- 결정(저자, 2026-10-09 07:49:50, 대화 기록; 원문 인용 대신 결정 요지): 저자는 AI 도구를 쓰지 않는 조건을 받아들이지 않았고, 결정의 책임은 저자가 진다고 밝혔다. 이를 washout과 2차 annotation에서 채팅 어시스턴트 등 AI 도구를 허용한다는 결정으로 기록한다. AI 도구 사용은 세션을 마칠 때 기록한다. 각 labeler는 사용 여부(예/아니오), 도구 이름, 대략의 셀 수를 세션 로그에 적는다. 라벨링 화면에는 선택 입력인 셀별 "AI 사용" 체크박스를 둔다. 필수가 아니며 값이 없으면 "기록되지 않음"이다. 기록이 없으면 원고는 "기록되지 않음(not recorded)"이라고 적는다.
- 그대로인 것: AH 초안은 washout에 보이지 않는다(L1168–1169). washout 화면에는 번역 표시(`--cq-ko`)와 cq_id·category·variant chip도 없다(DN-2). 2차 annotator 화면에도 AH 초안과 번역 표시는 없다(§12.4). 2차 annotator는 이 연구 자신의 산출물(AH 초안, judge 출력, 저자의 라벨, persona·LLM 보조 결과, 결과 수치)을 보지 않는다. 이것은 연구 산출물에 대한 blind이며 AI 도구 규칙이 아니다.
- 결과: G2는 "same-rater agreement between the AH pass and the washout pass"라고 부른다. 계산(rater_L1의 QWK)과 임계값(CI 하한 ≥ 0.70)은 그대로다. test–retest reliability라고 부르지 않는다(§12.3 DN-6).
- 보고: washout과 2차 annotation의 결과는 AI 도구 사용(예/아니오)별, 도구별로 층화해 함께 보고한다. 기록되지 않은 세션과 셀은 "기록되지 않음"으로 따로 센다.
- 한계: AI 도구 사용은 자기보고로만 남고, 셀별 체크박스는 선택이라 비어 있을 수 있다. AH pass의 Claude 사용(D3)은 셀 단위 기록이 전혀 없다. `label_assist.py`(`f855e62` 판)의 세션 로그 줄(`SESSION start` L279–281, `SESSION end` L431)에는 이 기재란이 없고 라벨링 화면에도 셀별 체크박스가 없다. 세션 종료 기재란과 선택 입력 체크박스는 washout 전에 구현하고 합성 fixture로 테스트한다.

**부기 — ID를 붙이지 않은 관찰(저자 확인 필요).**
- `annotation/PROTOCOL.md` L27과 `OWNER_RUNBOOK.md` L86–88이 요구하는 second-human export·비식별 검증, 그리고 서명된 동의서(`annotation/CONSENT_TEMPLATE.md`)의 수행 기록이 LOCK에 없다 [UNVERIFIED].

### 12.2 분석 코드 정합 교정 (사람 라벨 분석 전)

이 절의 교정은 등록된 계산을 바꾸지 않는다. 코드를 등록 문서에 맞춘다. 교정은 커밋 `ef62ef8`(2026-10-09 01:47:42)에 들어갔고 합성 fixture(연구 라벨이 아님)로 테스트되었으며(커밋 메시지: harness 테스트 434 passed, 2 skipped), human-label 분석(01:47:49 실행)보다 앞선다. 하드닝 커밋 `0dbe6e9`가 그 뒤에 입력 검증을 보강했다(§12.0). (2)의 boundary와 (5)의 드리프트 조작화는 이 addendum이 처음 정하는 것이다. 둘 다 초안 첫 판(01:07)에 있었고 분석 실행 전에 코드에 반영되었다. 등록 문서로서는 이 addendum이 처음이며 분석 이후에 확정되었다.

1. **모집단은 primary 셀만.** Coverage(L₁\*), 확인적 대조, 셀 단위 π̂, G1, G2, G5, G6(fragility 포함), G7은 `cell_kind == "primary"`인 셀로만 계산한다. control 36셀은 사람 라벨 기반 통계에 들어가지 않는다. control 행의 라벨 값은 읽지 않고 존재 여부로만 센다(D6). 같은 (variant, cq_id)의 primary 셀은 하나여야 하며, 둘 이상이면 실행을 거부한다(`ef62ef8`에 구현, 확인함).
2. **G7은 라벨 감사 기록으로 계산한다.** 잠긴 `primary_working.csv.audit.jsonl`(LOCK L11)에서 다음 세 조건을 본다. (a) 라벨된 primary 셀의 저장이 모두 unblind boundary보다 앞선다. (b) boundary 이후의 저장과 사후수정이 0이다. (c) `elapsed_s` < 20초인 셀의 비율이 3% 미만이다(L349). judge 실행 telemetry는 읽지 않는다. boundary는 `f855e62` 커밋 시각(2026-10-09T00:23:09+09:00)으로 둔다(분석 실행 명령의 `--unblind-boundary`에 같은 값을 넘겼다). judge 점수는 2026-09-21부터 저장소에 있었으므로 "unblind"는 J와 라벨의 첫 결합으로 정의할 수밖에 없다. 잠금 커밋은 어떤 결합보다도 앞서므로, 분석 커밋 시각을 쓰는 것보다 (a)와 (b)를 엄격하게 만든다.
3. **G5의 CI는 점추정과 같은 추정량에 대해 구한다.** 점추정은 primary 셀 전체의 pooled mean |J − rater_L1|이다. CI도 이 pooled 통계량을 cluster 통째 재표본으로 bootstrap해서 구한다. 이전 코드처럼 cluster 평균들의 평균에 대한 CI를 붙이지 않는다.
4. **G3은 계산 불가로, 사유를 붙여 보고한다.** 사유는 다음 세 가지다: control 접두어가 S6까지 노출됨, S6에서 라벨된 12개의 표시 결함, 24개 미서빙(D6). control 36개의 라벨 존재 수를 함께 적는다. DN-7 (a)에 따라 washout의 G3-W를 따로 계산한다(§12.3).
5. **등록된 기술 항목을 구현한다.**
   - 순서 드리프트(L551). L551은 이름만 있고 정의가 없으므로 이 addendum이 정한다: 라벨(A, rater_L1)이 저장 순서(감사 로그에서 마지막 저장 시각의 순위)에 따라 어떻게 변하는지를 순위상관, 5분위별 평균, 세션별 평균으로 기술한다. 검정과 p값은 없고 judge 점수는 읽지 않는다. 분석기 출력의 `descriptive.order_drift`가 이 항목이다. 5분위별 평균 rater_L1은 봉인 사유로 현재 rater-safe 사본에서 빠져 있다(§12.0).
   - AH 교정률(L1166–1167). 최종 A가 초안 A와 다른 primary 셀의 비율(전체, category별, 방향별)과 span을 고친 비율을 기술 통계로만 보고한다. 결과는 LOCK L32–33의 과정 지표(A 1→0 26셀, 0→1 0셀, span 수정 86셀)와 일치해야 한다. 다르면 원인을 기록한다. 분석기 출력(`descriptive.ah_correction`)은 같은 값을 냈다(확인함).
6. **G1은 두 수준을 나란히 보고하고 97.5%로 판정한다(DN-1).** 단측 Clopper–Pearson 상한을 97.5%(L564)와 95%(`main.tex` L1096–1099)에서 모두 계산한다. α = 0.025의 단측 상한은 양측 95% Clopper–Pearson 구간의 상한과 같다. 실현된 cluster 수에서의 달성 가능성 진단도 함께 낸다(n=33: 97.5%는 0사건이어도 통과 불가, 95%는 0사건일 때만 통과; D8). 10% 임계값(L343)은 바꾸지 않는다.
   **DN-1 결정(저자, 2026-10-09): (a) 97.5%(L564)로 판정하고 95%를 병기한다.** 97.5% 상한이 항상 더 크므로 이 선택은 "두 수준 모두에서 통과해야 통과"와 같다. (a)를 택하면 n=33에서 G1은 구조적으로 통과할 수 없으며, 원고는 이 사실을 달성 가능성 진단과 함께 밝힌다. 판정이 실제로 갈리는 경우는 0사건일 때뿐이다. 이 결정은 G1 결과를 안 뒤에 내려졌다(§12.0). 분석기는 처음부터 97.5%를 기본값으로 두고 95%를 병기했으므로 계산은 이 결정에 의존하지 않는다. 선택하지 않은 안은 (b) 95% 판정(`DECISIONS/G1_confidence_level.md`의 추천, `main.tex` 분석계획 표)과 (c) 판정 보류다. L564가 0사건 상한의 계산 방법을 정하는 조항이고 분석기 기본값도 데이터 이전부터 97.5%였으며, 라벨이 이미 존재하는 지금 더 관대한 수준을 고르면 결과를 의식한 선택으로 보일 수 있기 때문이다.
7. **라벨 기반 통계는 탐색적 결과로 보고한다.** Coverage(L₁\*), A→B, π̂, G1, G5, fragility를 등록된 방식 그대로, washout의 G2·G3-W와 §12.4의 일치 통계를 §12.3·§12.4가 정한 방식으로 계산하고 보고하되, 원고는 이를 모두 confirmatory 결과가 아니라 탐색적 결과로 표기한다. 이유는 D3(셀 단위 기록이 없는 LLM 보조), D4(G7 체류 기준 실패), D18(화면의 AI 번역 표시)이다. "탐색적"은 해석의 지위를 바꾸는 표기일 뿐 계산을 바꾸지 않는다. 어떤 게이트 통과도 calibration 주장의 근거로 쓰지 않는다. G1이나 G5가 실패하면 §5(L605)대로 음성 결과로 보고한다.
8. **입력을 고정하고 등록된 재표본을 쓴다.** 분석기는 입력 파일(`cells.jsonl`, 라벨 CSV, 감사 로그, 초안 CSV)과 분석기 자신의 sha256을 출력의 `input_provenance`에 남긴다(`ef62ef8`에 구현, 확인함). 실행 전에 LOCK 매니페스트와 자동 대조해 불일치 시 거부하는 기능은 구현되지 않았다. 대신 하드닝 재실행 출력의 입력 sha256이 LOCK 매니페스트(L10, L11, L13)와 `cells.jsonl`의 `bfd5b3c8…`와 같음을 확인했고, 잠금 사본은 읽기 전용이며 지금도 LOCK 해시와 같다(`sha256sum -c`, 확인함). 첫 실행의 출력은 봉인되어 열지 않았으나 같은 잠금 사본을 입력으로 썼다. seed는 20260913, resample은 10,000, 단위는 비층화 semantic cluster, 방법은 BCa다(L560–563). 층화 bootstrap은 등록되지 않았으므로 주 분석에 쓰지 않는다. 쓴다면 미등록 민감도 분석으로 표기한다.

### 12.3 washout (G2) 전향 프로토콜

washout은 아직 일어나지 않았다. 이 절은 washout 라벨이 존재하기 전의 전향적 등록이다. 등록자는 AH pass의 집계 결과를 알고 있었다(§12.0). 아래 DN-n은 저자가 2026-10-09에 결정한 규칙이다. 항목마다 결정한 규칙과, 선택하지 않은 안을 한 문장으로 적는다.

**DN-2 washout 패킷 — 결정(저자, 2026-10-09): (a) 등록(L522–523)대로 새로 만든다.**
- 새 ID: 셀 종류·variant·CQ를 담지 않고 1차 ID에서 유도할 수도 없는 불투명 ID(봉인한 salt로 만든 hash). ID 매핑 파일은 rater가 볼 수 없는 곳에 두고, 그 sha256을 첫 washout 저장 전에 커밋한다.
- 새 위치: 등록 seed 20260913(L14)으로 같은 CQ를 20위치 이상 떨어뜨리는 제약 셔플을 한다(L529–536). 제약을 만족할 수 없으면 달성한 간격을 보고한다(§7 L951–954와 같은 처리). 선택과 순서 모두 seed 20260913을 쓴다.
- cluster paraphrase: 모든 행에 `bank/cq_bank_brick_v1_paraphrases.csv`의 `paraphrase_text`를 보인다(36행, sha256 `c02ecda3f2c6c3c27dc47e7f4845ac57739d5d85b059bfa813328c125682341f`; 기계 검증 2026-09-13 통과, `bank/PARAPHRASE_FREEZE.md` L9–14; 현재 파일의 `sha256sum`이 같다, 확인함). 파일은 2026-09-14(`682bfe3`) 이후 바뀌지 않았고, judge run의 preserved control 12개가 같은 바이트를 썼다(확인함). 바이트는 고치지 않는다.
- paraphrase 동결: 저자는 2026-10-09에 같은 일괄 승인 지시로 위 파일의 현재 바이트를 동결한다고 선언했다. 행 내용은 읽지 않고 한 선언이다. `PARAPHRASE_FREEZE.md` L62–66이 동결 선언은 사람이 해야 한다고 적었는데 이 선언이 그 기록이다.
- 의미 동일성 점검: rater가 아닌 사람이 해야 하며 아직 하지 않았다. washout 전에 끝나야 한다. rater가 washout 전에 paraphrase를 읽으면 표면 교란이 약해지기 때문이다(36행 중 21행은 2026-09-13 작업 세션에서 생성되었고 15행은 저자 초안이다, 같은 파일 L69–71). 부적합 판정을 받은 행은 그 cluster의 모든 washout 행에 원 CQ를 보이고 그 사실을 기록한다. human pass가 끝난 지금 새 paraphrase를 쓰지 않는다.
- 화면: 1차 패스와 같은 자료를 보인다. variant view, `judge_evidence_span`(검증 대상, `LABELER_GUIDE.md` L56), 텍스트·그래프·도움말 탭이다. AH 초안(L1168–1169)과 번역 표시(`--cq-ko`)는 뺀다. 1차 패스로 돌아가는 단서를 줄이기 위해 cq_id, category·variant chip도 보이지 않는다. view 자체가 출처를 드러낸다는 점은 L538–546대로 블라인딩을 주장하지 않는 것으로 처리한다.
- 한계(원고에 적는다): `judge_evidence_span`은 두 패스에서 같으므로 회상 단서가 될 수 있다.
- 선택하지 않은 안은 (b) 2026-09-21 패킷을 그대로 쓰고 D7을 이탈로 남기는 것이다. 패킷이 한 번도 서빙되지 않았으므로 등록대로 고치는 비용이 거의 없고, D7의 위반(ID, paraphrase, 강화층, seed, control 포함)이 한꺼번에 사라지기 때문이다.

**DN-3 표본 크기와 control의 계수 — 결정(저자, 2026-10-09): (a) primary 72셀(비례층 48 + 강화층 24, L456·L466)로 하고, control은 72에 넣지 않고 DN-7에 따라 따로 센다.** 비례층 48은 188개 primary 셀에서 (category × judge 점수 J ∈ {0,1,2,3}) 층에 비례 배분하고 seed 20260913으로 뽑는다. 이 선택에는 J가 필요하므로 rater가 아닌 사람이나 에이전트 세션이 실행하고, rater는 최종 시트만 받는다. 절차는 다음으로 고정한다.
- 층: sorted((category, J))의 비어 있지 않은 층만 쓴다. N_h는 층 h의 primary 셀 수이고 합은 188이다.
- 배분: n_h = max(1, 최대잉여 배분)이다. ⌊48·N_h/188⌋에서 시작해 최대잉여(48·N_h/188의 소수부) 순으로 +1석을 준다. 잉여가 같으면 category 오름차순, 그다음 J 오름차순으로 준다. max(1, ·) 때문에 합이 48을 넘으면 현재 n_h가 가장 큰 층에서 한 석씩 뺀다. 같으면 같은 순서를 쓴다.
- 추출: 난수는 단일 `rng = random.Random(20260913)` 하나다. 층 순서대로 `rng.sample(sorted(cell_ids), n_h)`를 호출해 비례층 S1(48셀)을 만든다(`cell_ids`는 그 층의 cell_id 목록). 강화층 24셀은 DN-4a가 같은 rng로 이어서 뽑는다.
- 선택하지 않은 안은 (b) 기존처럼 control을 포함해 72행(primary 60행)으로 하는 것이다. L456은 72를 하한으로 등록했고, G2는 primary 셀의 통계이기 때문이다(§12.2 (1)).

**DN-4a 강화층 24셀 — 결정(저자, 2026-10-09): (c) judge와 AH가 불일치하는 셀을 rater가 볼 수 없는 스크립트로 고른다.** 등록된 강화층은 "`ASK` ↔ judge 충돌 셀"(L466)이다. 그러나 holdout에서는 ASK 결과를 A로 바꾸는 규칙이 등록되어 있지 않고, namespace 불일치 때문에 108개 조합이 모두 ASK=false다(§7 L894–937). 등록된 정의 그대로는 만들 수 없다. 불일치는 1[J ≥ 2] ≠ A_AH로 정의한다(§10.1 L1091의 트리거 정의와 π의 J ≥ 2 기준 L316을 그대로 쓴다). 불일치 셀의 집합을 D라 하고 DN-3의 비례층 표본을 S1이라 한다. 같은 rng(`random.Random(20260913)`)로 S1 다음에 `rng.sample(sorted(D∖S1), 24)`를 호출해 강화층 24셀을 비복원 추출한다. |D∖S1| < 24이면 D∖S1을 모두 넣고, 부족분 k는 `rng.sample(sorted(남은 셀), k)`로 채운다(남은 셀은 S1과 D∖S1에 들지 않은 primary 셀). 그 수를 기록한다. 셀마다 포함 확률 π_i를 계산해 봉인 파일에 기록하고 재가중 pooled 추정에 쓴다(정의는 §12.3 "G2 계산"). J는 스크립트 안에서만 쓰이고 rater는 층 소속을 볼 수 없다. 이 선택은 washout 전에 J와 AH 라벨을 봉인된 상태로 결합해야 하는 비용을 진다. 선택 스크립트는 §12.2 교정(`ef62ef8`, 이미 커밋됨)이 들어간 코드와 함께 쓰고, 출력(셀 목록, 층, 포함 확률)은 sha256만 공개한 채 rater에게 봉인한다. 첫 washout 저장 전에 입력의 sha256(`cells.jsonl`, LOCK L10의 잠긴 작업 CSV `primary_working.csv`)과 선택 스크립트의 sha256을 출력의 sha256과 함께 커밋한다. 이 규칙은 분석 이전의 첫 판에 있었다(§12.0). 선택하지 않은 안은 (a) 비례층만 쓰는 안(L466–468의 세 추정 설계가 사라진다)과 (b) AH 라벨이 초안과 다른 셀을 고르는 안(rater 자신의 1차 수정 행동, 곧 A 변경 26셀 모두 1→0, LOCK L32를 조건으로 뽑게 되어 rater가 기억할 만한 셀을 골라 넣고 D3의 기록 없는 Claude 보조를 따라가는 선택이 된다)이다.

**DN-4b G2 게이트 입력 — 결정(저자, 2026-10-09): (a) G2 게이트(CI 하한 ≥ 0.70, L344)는 재가중 pooled 추정에 적용하고, 두 층의 추정은 함께 보고한다.** L467–468은 두 층 각각과 재가중 pooled, 세 추정을 모두 등록했지만 어느 것이 게이트 입력인지는 정하지 않았다. 재가중 pooled 추정은 72셀을 모두 쓰면서 188셀 모집단의 일치도를 추정한다. 가중치 w_i, 점추정 QWK_w, 구간, 판정은 §12.3 "G2 계산"에서 완전히 정의한다. 선택하지 않은 안은 (b) 비례층 48의 추정에만 게이트를 적용하는 것이다. 그러면 강화층 24셀이 게이트에서 빠지기 때문이다.

**DN-5 일정과 세션 조건 — 결정(저자, 2026-10-09; 세션 한도와 AI 도구는 승인 뒤 같은 날 바꿨다).**
- 일정: 최초 가능일 2026-10-30(마지막 저장 2026-10-08 23:58:55에 21일을 더하면 2026-10-29 23:58:55, L522). 목표는 28일, 즉 2026-11-06 이후다. 불가피할 때만 그보다 일찍 하되 2026-10-30 이전은 안 되며, 그 경우 실제 간격을 보고한다.
- 세션 한도(승인 뒤 변경, D19): washout에는 세션당 셀 상한도 세션 간 최소 간격도 두지 않는다. 저자가 2026-10-09에 이 제한의 제거를 지시했다. 등록된 L550(세션당 최대 60셀, 세션 간 ≥ 12시간)으로부터의 명시적 이탈이다. 세션 시작·종료 시각과 세션 수를 보고한다.
- 초안: AH 초안은 보이지 않는다(L1168–1169).
- AI 도구(승인 뒤 변경, D20): 채팅 어시스턴트 등 AI 도구를 허용한다(저자 결정, 2026-10-09 07:49:50; D20). 세션을 마칠 때 AI 도구 사용 여부(예/아니오), 도구 이름, 대략의 셀 수를 세션 로그에 적는다. 라벨링 화면에는 선택 입력인 셀별 "AI 사용" 체크박스를 둔다. 필수가 아니며 값이 없으면 "기록되지 않음"이다. 기록이 없으면 원고는 "기록되지 않음(not recorded)"이라고 적는다. 텍스트 검색과 그래프 탭 같은 결정적 도구는 1차 패스처럼 쓸 수 있다.
- 체류 시간: 셀마다 `elapsed_s`를 기록하고 G7식 점검(20초 미만 비율과 3% 기준, 중앙값, IQR)을 보고한다. 최소 체류를 강제하지 않는다. 강제하면 20초 점검이 의미를 잃는다. 목표 약 90초(L455)는 화면에 안내만 한다. 점검이 기준을 넘더라도 셀을 사후에 빼지 않고 G2와 함께 보고한다.
- 한계: 세션 한도를 없앴으므로 L550이 겨냥한 피로·순서 효과는 설계로 제한되지 않는다. AI 도구 사용은 세션 단위 자기보고와 선택 입력인 셀별 체크박스로만 남는다.
- 선택하지 않은 안은 이 addendum 초안의 추천이다. L550 복원과, AI 도구 금지 및 "미사용" 자기신고다. 저자가 2026-10-09에 둘 다 받아들이지 않았고 방법론적 이유는 기록하지 않았다. 일정은 추천대로다.

**DN-6 G2의 이름과 해석 — 결정(저자 승인 2026-10-09; 이름은 같은 날 AI 도구 허용 결정에 맞춰 바꿨다): (a) 등록된 계산을 그대로 하고 이름과 해석을 실제 조건에 맞춘다.** 계산(rater_L1의 QWK, L344, L569–572)과 임계값(CI 하한 ≥ 0.70)은 그대로다. 이 addendum은 G2를 "AH pass와 washout pass 사이의 동일 rater 일치도(same-rater agreement between the AH pass and the washout pass)"라고 부른다. 두 패스의 조건은 기록되는 대로 적는다: AI 초안은 AH pass에만 있다. AI 채팅 도구는 두 패스 모두 허용되며 사용은 자기보고로 기록된다. AH pass에서는 셀 약 절반에서 Claude 사용이 사후에 보고되었고 셀 단위 기록이 없다(D3). washout에서는 세션 종료 시 세션 로그에 적는다(D20). 1차 rater_L1도 초안이 미리 채운 값에서 출발했다(L1144–1145). 원고는 G2를 test–retest reliability라고 부르지 않는다. §11 L1168의 "AH pass의 test--retest" 서술은 이 addendum이 대체한다. AH pass에는 셀 단위 보조 기록이 없으므로 보조 여부별 분해는 하지 않는다. 선택하지 않은 안은 (b) 등록된 의미의 G2는 얻을 수 없다고 보고 계산 불가를 선언하는 것이다. 계산은 등록된 그대로이고 바뀌는 것은 라벨 출처와 해석 명칭뿐이기 때문이다(§11 L1171–1172와 같은 원칙).

**DN-7 control의 재사용 — 결정(저자, 2026-10-09): (a) control 36개를 모두 washout 안에서 primary 72셀과 섞어 다시 제시하고, 이 washout에서 G3을 계산해 "G3-W"라는 이름으로 보고한다.** 조건:
- 화면을 바로잡는다. ablated control은 judge가 본 ablated view를 `harness/run_holdout.py`의 `ablate_rendered_view`로 다시 만들고, sha256이 `cells.jsonl`의 `artifact_digest`와 같을 때만 보인다(다르면 그 셀을 빼고 보고한다). preserved control은 judge가 본 원본 view를 보인다. CQ 문장은 다른 모든 행처럼 paraphrase로 보인다. washout에서 원 CQ를 보이는 행이 있으면 그것만으로 control이 드러나기 때문이다. 이 때문에 ablated control의 CQ 문장은 judge가 본 원문과 다르며, 그 사실을 기록한다. 현재 라벨링 도구는 variant별 view만 다루므로(확인함: `label_assist.py` L176, L887, L898) 행별 view를 지원하도록 고치고 합성 fixture로 테스트해야 한다.
- DN-2의 불투명 ID와 같은 셔플을 쓴다.
- 판정: G3-W는 ablated 24개가 모두 digest 검사를 통과하고, 제시되고, 라벨된 경우에만 unsupported(A=0)가 22개 이상(≥ 22/24, L345의 임계값 그대로)인지로 판정한다. 그렇지 않으면 판정하지 않고 유효한 셀 수 대비 A=0 수를 보고한다. preserved 12개의 A=1 수는 기술적으로 보고한다(L454). control은 G2에서 뺀다.
- 민감도: S6에서 접두어와 함께 이미 본 ablated 8개를 뺀 16개 기준 값도 보고한다. 이것도 판정하지 않고 16개 중 A=0 수를 보고한다.
- 한계(원고에 적는다): rater는 control이 있다는 것과 ablation 방식을 알고 있으므로 "미공지"(L453)는 회복되지 않는다. G3-W는 AH 1차 패스가 아니라 AH 초안이 없는 washout 조건의 rater를 점검한다. AI 채팅 도구는 두 패스 모두 허용되고 사용은 자기보고로 기록되므로(D20) 이 점검은 도구 사용의 영향을 분리하지 않는다. control이 섞이면 washout의 엄격도가 control이 없던 S7과 달라질 수 있다.
- 근거: G3은 "모든 것을 credit하는 rater"를 막는 유일한 등록 장치다(L345; `main.tex` L1103–1105). AH 1차 라벨의 A=1 비율이 73%(138/188)인데 이 점검이 없으면 G1 계열 해석이 더 약해진다. washout은 AH 초안이 없는 조건이므로 음성 대조를 다시 넣을 수 있는 자리다. 엄격도가 달라질 수 있다는 비용은 G2의 해석에 영향을 주지만(DN-6에서 이미 해석을 바꿨다), G2의 계산 모집단은 primary로 고정되어 있다.
- 선택하지 않은 안은 (b) G3을 계산 불가로 선언하고 control을 다시 제시하지 않는 것이다. 가장 단순하지만 G3 정보를 영영 잃기 때문이다.

**washout 라벨 잠금 전의 노출 통제 (규칙).** washout 라벨을 잠그기 전까지 rater는 다음을 열람하지 않고 집계 수치만 본다: (i) human-label 분석 출력 중 셀·CQ 단위 필드(fragility의 이동 CQ 목록, 셀 목록 등)와 봉인된 게이트 값(G4, G5; `SEALED_until_washout/`)과 순서 5분위별 평균 rater_L1, (ii) washout 빌드 산출물(ID 매핑, 층 소속, 포함 확률), (iii) 2차 annotator의 라벨, (iv) persona 결과, (v) 셀 단위 LLM 보조 라벨. 근거: §10.1은 셀 단위 judge verdict가 노출되면 washout이 오염되어 G2가 무효가 된다고 적었다(L1094–1098). §10은 §11로 supersede되었지만 이 순서 논리는 그대로 유효하다. 같은 순서 규정(L1094–1095)에 따라 blind 분석은 washout 전에 돌려도 된다.

**G2 계산 (규칙).** washout 라벨을 잠근 뒤 primary 72셀의 rater_L1로 계산한다. AH pass의 값을 AH_L1, washout의 값을 WO_L1이라 한다. 게이트 입력은 아래의 가중 QWK_w이며, 아래 정의는 모두 washout 라벨을 결합하기 전에 고정한다.
- 포함 확률. π_i는 전체 선택 절차(비례층, 이어서 불일치 잔여층; DN-3, DN-4a)를 `random.Random(20260913+r)`, r = 1..100000으로 다시 돌렸을 때 셀 i가 뽑힌 실행의 비율이다. 소수점 아래 4자리까지 보고한다. w_i = 1/π_i는 셀의 고정된 속성이며, bootstrap 재표본에서 다시 계산하거나 정규화하지 않는다.
- 점추정. M_jk = Σ w_i·1[AH_L1 = j, WO_L1 = k]이다. QWK_w = 1 − O/E이고 O = Σ(j−k)²M_jk, E = Σ(j−k)²M_j+·M_+k/M_++이다.
- 구간. 분석기의 `cluster_bootstrap_stat`(`analyze_holdout.py`)로 구하는 95% 양측 BCa다. 비층화이고 CQ cluster를 통째로 재표본하며 가중치를 재정규화하지 않는다. B = 10,000, `default_rng(20260913)`, leave-one-cluster-out jackknife, mid-rank z0를 쓴다. 하한이 게이트다(CI 하한 ≥ 0.70, L344).
- E = 0인 replicate는 QWK = 0으로 센다. `_qwk_from_values`의 1.0 규약(E = 0이고 O = 0이면 1.0)을 쓰지 않는다. 그런 replicate의 수를 보고한다.
- 층별 추정. 비례층 48과 강화층 24 각각의 QWK를 따로 낸다(L467–468). 해석적 SE(L569–572의 Fleiss–Cohen(–Everitt, non-null) 교차확인)는 이 두 층의 가중하지 않은 QWK에 대해서만 보고하며 결정 입력으로 쓰지 않는다.
- pooled 추정에는 Kish의 유효 표본 크기 n_eff = (Σw)²/Σw²를 함께 보고한다.
- 달성 가능성(washout 전에 밝힌다. G1과 같은 방식). L462–464의 등록된 공식은 참 QWK 0.80, n = 72에서 SE ≈ √(0.36/72) ≈ 0.071이고 기대 구간은 약 [0.66, 0.94]다. 0.36을 1 − 0.80²로 읽어 SE ≈ √((1−ρ²)/n)로 일반화하면 [추정] 하한 ≥ 0.70을 통과하려면 참 QWK가 약 0.83 이상이어야 한다(ρ = 0.83에서 하한 ≈ 0.70). 이 사실을 washout 라벨이 존재하기 전에 이 addendum에 적는다.
- 층, 재가중, CI를 계산하는 코드는 washout 라벨을 결합하기 전에 합성 fixture로 테스트한다(현재 `washout_qwk`는 점추정만 낸다). A의 이진 일치는 기술 통계로만 낸다(`annotation/packet/README.md` L24). washout 라벨은 주 추정에 쓰지 않는다(L597).

### 12.4 2차 annotator(second, non-author annotator) 48셀 전향 프로토콜

등록 근거는 L470–518, L1163–1165, L1178이다. 아래 규칙은 그 등록을 구체화한다. DN-8–DN-10은 저자가 2026-10-09에 결정한, 등록과 다르거나 등록에 없는 선택이다.

- **자격.** L479–481의 자격(저자가 아님, CQ bank·rubric·pipeline에 관여하지 않음)에 더해, AH 초안, judge의 점수와 판정 근거(화면에 보이는 judge 인용 span은 제외), 저자의 라벨, LLM 보조와 persona 결과, 이 연구의 결과 수치를 본 적이 없어야 한다.
- **표본.** 188개 primary 셀에서 카테고리당 8개를 비복원으로 뽑는다(L483–484). seed는 20260913(L14)이다. 절차는 다음으로 고정한다. 입력은 `harness/real_run/cells.jsonl`(sha256 `bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af`)에서 `cell_kind == "primary"`인 188행의 `cell_id`, `cell_kind`, `category` 세 필드뿐이며, J와 라벨을 포함한 다른 필드는 읽지 않는다. 카테고리를 이름순으로 두고, 카테고리 안에서 `cell_id`를 정렬한 뒤, `random.Random(20260913)` 하나로 카테고리 순서대로 `rng.sample(sorted_ids, 8)`을 호출한다.
  ```
  rng = random.Random(20260913)
  picked = []
  for cat in sorted(categories):                      # 카테고리 이름순
      picked += rng.sample(sorted(ids[cat]), 8)       # ids[cat]: 그 카테고리 primary 셀의 cell_id
  data = ("\n".join(sorted(picked)) + "\n").encode("utf-8")
  ```
  카테고리별 primary 셀 수(concept_definition 36, instances 36, methodology 32, relations 27, slots_facets 21, taxonomy 36; 확인함)는 모두 8 이상이다. 직렬화는 뽑힌 48개 `cell_id`를 전체에서 다시 정렬해 UTF-8로 한 줄에 하나씩 쓰고 끝에 개행을 붙인 것이며(768바이트, 48행), 그 sha256은 `bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e`다(CPython 3.12.3에서 2026-10-09에 계산). 이 목록의 sha256을 이 addendum과 함께 커밋한다(DN-8). washout 표본과는 따로 뽑는다. 다른 사람이 채점하므로 겹쳐도 된다.
- **블라인드와 AI 도구.** 2차 annotator는 이 연구 자신의 산출물(judge의 점수와 판정 근거, AH 초안, 저자 라벨, 위 AI 산출물, 결과 수치; 화면에 보이는 judge 인용 span은 제외) 없이 채점한다. 이 blind는 연구 산출물에 대한 것이며 AI 도구 규칙이 아니다. AI 도구(채팅 어시스턴트 등)는 허용된다(저자 결정 2026-10-09 07:49:50; D20). 각 annotator는 세션을 마칠 때 AI 도구 사용 여부(예/아니오), 도구 이름, 대략의 셀 수를 세션 로그에 적는다. 라벨링 화면의 셀별 "AI 사용" 체크박스는 선택 입력이다(D20). 기록이 없으면 원고는 "기록되지 않음(not recorded)"이라고 적는다. 결과는 AI 도구 사용(예/아니오)별, 도구별로 층화해 보고한다. 초안 등이 유출되면 subsample을 폐기하고 그 사실을 보고한다(L1178 (c)). 2차 annotator의 라벨은 washout 라벨을 잠글 때까지 rater에게 봉인한다(§12.3 노출 통제).
- **자료.** AH pass와 같은 자료를 보인다. 원 CQ 문장, variant view, `judge_evidence_span`(judge가 인용한 span이며 점수가 아니다; `LABELER_GUIDE.md` L56의 검증 대상)을 보이고, `label_assist.py`를 `--draft`와 `--cq-ko` 없이 쓴다. 순서는 seed 20260913의 제약 셔플이다. AH pass와 나란히 비교하려면(L1165) 같은 과제여야 한다.
- **세션.** 세션당 셀 상한과 세션 간 최소 간격을 두지 않는다. L550로부터의 명시적 이탈이며 저자가 2026-10-09에 결정했다(D19). 48셀을 한 세션 또는 여러 세션에 나눠 채점할 수 있다. 세션 시작·종료 시각과 세션 수, 셀별 dwell(`elapsed_s`)을 기록하고 G7식 점검(20초 미만 비율과 3% 기준, 중앙값, IQR)을 보고한다. 최소 체류는 강제하지 않는다.
- **보고.** AH pass와 나란히 보고한다(L1165). 같은 48셀에서 아래를 모두 기술 통계로 낸다. 어느 것도 게이트 입력이 아니며(L510–512), 48셀 값으로 G1 판정을 대신하지 않는다. 이 라벨은 "second, non-author annotator"의 라벨로 부른다.
  - (i) AH 대 2차 annotator의 일치(같은 셀의 짝). A는 2×2표로 정의한다. 행은 AH, 열은 2차 annotator이고 n11, n10, n01, n00은 (AH, 2차)가 (1,1), (1,0), (0,1), (0,0)인 셀 수다. PPA = n11/(n11+n10), NPA = n00/(n00+n01)이다. 대칭적 specific agreement는 쓰지 않는다. Gwet AC1의 p_e = 2π(1−π)이고 π = (p₁₊ + p₊₁)/2이다. BCa replicate에서 정의되지 않는 통계(분모 0)는 제외하고 그 수를 보고한다. rater_L1은 quadratic-weighted κ와 정확 일치율을 보고한다(DN-10).
  - (ii) 48셀의 π̂. 범주당 8셀 균등 배분은 포함 확률을 0.222–0.381(8/36–8/21)로 만든다. 따라서 48셀의 π̂는 188셀의 π를 추정하지 않는다. 같은 셀에 대한 AH 대 2차 annotator의 짝지은 비교만 해석한다.
  - (iii) cluster 단위 Clopper–Pearson 상한(두 수준, 각 라벨 집합). 사건 cluster는 J ≥ 2 ∧ A = 0인 셀이 하나 이상 있는 cluster다. n은 48셀이 덮는 cluster 수 28이며 그중 15개는 셀이 하나뿐이다(확인함: 목록의 `cell_id`만으로 셈). 사건이 0이어도 상한은 97.5%에서 12.34%, 95%에서 10.15%로 10%를 넘는다. 따라서 이 상한은 기술용이며 G1과 비교하지 않는다.
  - (iv) judge 대 2차 annotator: QWK(J, rater_L1), 정확 일치율, 이진 κ(1[J ≥ 2] 대 A)다. 빈 span이 J = 0이므로(D16) J ∈ {1,2,3}로 제한한 값도 함께 낸다.
- **CVI.** 등록되어 있지 않으므로 산출하지 않는다. 따로 산출한다면 미등록 탐색 항목으로 표기한다 [UNVERIFIED: 약어 해석, D14].

**DN-8 annotator의 확정 시점과 예치 — 결정(저자, 2026-10-09): (a)를 분석이 이미 실행된 사실에 맞춰 바꾼다. 셀 목록의 sha256은 이 addendum과 함께 커밋하고, 신원 commitment는 annotator를 모집할 때 커밋한다.**
- 초안의 추천 (a)는 annotator를 human-label 분석 전에 정하고 신원 commitment와 셀 목록의 sha256을 그때 커밋하는 것이었다. 이 추천은 이 addendum이 분석 전에 승인되는 것을 전제로 했다. 실제로는 분석이 이미 실행되었고(2026-10-09 01:47:49) 이 addendum은 그 뒤에 승인되었으며, annotator는 아직 모집되지 않았다. 따라서 annotator의 신원을 분석 이전에 고정하는 것은 불가능했다.
- 결정: (i) 위 48셀 목록(seed 20260913으로 확정)의 sha256 `bd2333d4…854b7e`(전체 값은 위)를 이 addendum과 함께 커밋한다. (ii) 신원 commitment, 곧 sha256(이름 + 비공개 salt)는 annotator를 모집할 때, 그 annotator가 어떤 자료도 보기 전에 커밋한다. 이름과 salt는 2차 annotation 라벨을 잠근 뒤 제출 시점에 annotator가 동의하면 공개하고, 동의하지 않으면 요청 시 편집자에게 전달한다.
- 남는 위험: 표본은 seed로 결정되므로 목록 해시가 표본에 대한 여지를 닫는다. annotator 선택은 분석 결과(집계)가 이미 알려진 뒤에 이루어진다. 신원 commitment는 모집 시점 이후의 변경만 막으며 이 위험을 닫지 않는다.
- 선택하지 않은 안은 (b) 채점 직전에 예치하는 것(L485–487의 최소 요건)이다. 모집 시점에 예치하는 편이 annotator 선택의 시점을 더 일찍 고정하기 때문이다.

**DN-9 2차 annotator가 채울 라벨 열 — 결정(저자, 2026-10-09): (a) 1차 패스와 같은 네 열, 즉 A, rater_L1, evidence_span_verbatim, note를 모두 채운다.** §3(L485)의 "같은 L₁ rubric으로 채점한다"를 A까지 넓히는 수정이다. π와 G1은 A 위에서 정의된다(L316, §1.0). A가 없으면 48셀이 L1164–1165가 이 subsample에 맡긴 병기 보고 역할(G1 계열 병기)을 할 수 없다. 선택하지 않은 안은 (b) 등록대로 L₁만 채우는 것이다. 그러면 π와 G1을 같은 48셀에서 다시 계산할 수 없기 때문이다.

**DN-10 일치 통계 — 결정(저자, 2026-10-09): (a) A(이진)는 원 일치율, Cohen κ, Gwet AC1, PPA/NPA를 보고한다. rater_L1은 quadratic-weighted κ(L509)와 정확 일치율을 보고한다.** 구간은 CQ-cluster BCa(10,000 resample, seed 20260913)로 구하고, 모두 기술 통계다. PPA/NPA는 AH 열을 비교 기준으로 둔 양성·음성 일치율이다. AH는 참조표준이 아니므로 PPA/NPA를 민감도·특이도라고 부르지 않는다. 어느 것도 게이트가 아니다(L510–512). 정의는 §12.4 "보고"의 (i)–(iv)에 있다. 선택하지 않은 안은 (b) 등록대로 κ만 보고하는 것이다. AH pass의 A=1 비율이 73%(138/188, LOCK L21)로 높아서 κ가 유병률에 끌려 낮게 나오는 역설이 생기기 쉽고, AC1과 PPA/NPA를 함께 보이면 일치의 구조를 읽을 수 있기 때문이다.

### 12.5 LLM-persona 라벨링 — 탐색적 전용

- **무엇.** `harness/persona_pass.py`(미커밋)에서 세 LLM persona(P1 규칙을 문자 그대로 따르는 온톨로지 엔지니어, P2 Brick 도메인 전문가, P3 회의적 리뷰어; `persona_pass.py` L11–15, L83)가 224행 시트의 라벨 네 열을 채운다. 코드의 기본 모델은 `<route-name withheld>`다(같은 파일 L95). 봉인 기록 `harness/real_run/persona_pass/SEAL_LEDGER.md`(이하 ledger; 2026-10-08 21:57:15 KST 수정본, sha256 `2a10c3e95ff60fd1b08a83358eead499bc560ac4b4838f71cf7712577808250a`)는 pilot을 `<route-name withheld>`(내부 proxy 경유)로 돌렸다고 적는다. main run과 sensitivity run은 같은 에이전트가 같은 스크립트로 돌렸다고만 적고 모델명을 따로 적지 않는다 [UNVERIFIED: 두 run의 모델명은 봉인 디렉터리의 실행 기록에만 있어 열지 않았다].
- **언제.** ledger 기준(2026-10-08): pilot 21:06–21:10(6셀 × 3 persona), main run 21:11–21:35(8 workers; 상류 사용량 한도 뒤 SIGTERM으로 멈춤), ablated_control 24셀에 대한 민감도 실행 21:12–21:33(3 workers), 파생 산출 21:36–21:38, 봉인 21:57. human pass는 그때 진행 중이었다(S6 19:46:03–22:10:39, 첫 저장 19:48:18, 마지막 저장 23:58:55). persona 실행과 봉인은 모두 human pass가 끝나기 전이다. main run의 완료 셀 수는 ledger에 없다 [UNVERIFIED: 봉인 파일 안에만 있다].
- **등록 지위.** 이 addendum 전의 PREREG에는 persona가 없다(grep "persona" 0건). 이 절은 이미 시작된 실행에 제약을 덧붙이는 사후 기록이다.
- **봉인.** ledger에는 봉인된 파생 산출물 25개(sha256 기록), 원시 대화 기록 9개(봉인 시점 바이트 수와 sha256 기록), 봉인 시 삭제한 scratch 복사본 16개(삭제 전 sha256 기록)가 있다. ledger는 봉인 이후에 아무것도 계산하지 않았고 봉인 파일을 열지 않았다고 적는다. 봉인 전에는 생성 에이전트가 부분 집계(일치도, Coverage, π, 게이트, 라벨 비율)를 계산하고 읽었다. 값은 어떤 보고에도 반복되지 않았다고 ledger는 적는다. 저자가 그 값을 알게 되었는지는 ledger로 확인할 수 없다 [UNVERIFIED]. 이 확정 작업은 ledger만 읽었고(모델, 시각, 개수, hash 같은 메타데이터), 봉인된 산출물은 열지 않았다. 그 hash를 다시 계산하지도 않았으므로 봉인 파일의 현재 hash가 ledger와 같은지는 확인하지 않았다 [UNVERIFIED].
- **규칙.** persona 결과는 어떤 게이트(G1–G8), 주 지표, §12.3·§12.4 통계의 입력도 아니다. washout 라벨을 잠근 뒤에만 봉인을 푼다. 2차 annotator에게 보이지 않는다. 보고한다면 탐색적 결과로만 보고하며, provenance `llm-persona`와 분석기 표지 `"LLM, not human"`(`persona_pass.py` L81–82)을 붙인다.
- **과제 차이(기록).** persona는 CQ 문장과 variant view만 보고, judge가 인용한 span과 cell_id·category·variant는 보지 않는다(`persona_pass.py` docstring L18–21, `ALLOWED_SHEET_COLUMNS` L97–99). 따라서 AH pass와 같은 과제가 아니다. control 행은 같은 시트를 입력으로 쓰므로 main run에서는 D6의 표시 결함(원 CQ, ablated 전 view)을 물려받는다. ablated control 24셀의 민감도 실행(`--judge-visible-ablated`, ledger)은 별도이며 이 addendum은 그 내용을 다루지 않는다. 어느 쪽도 G3 용도로 쓰지 않는다.
- 재개 여부는 운영상의 판단이며 이 addendum이 정하지 않는다. 재개하더라도 위 봉인 규칙을 따른다(ledger는 재개를 허용하되 새 산출물을 ledger에 더하라고 적는다).

### 12.6 변경되지 않는 것

- §1.0의 A(v,q)와 L₁\* 산식, §6-2의 Q_v 확장(L789–796), §1.1의 estimand π(L316).
- §2 G1–G8의 정의와 임계값(L341–350). 어떤 임계값도 옮기지 않는다. 실패한 게이트(G7)를 구제하지 않는다. 계산할 수 없는 게이트(G3, G6)를 다른 양으로 채우지 않는다. DN-7의 G3-W는 다른 이름으로 따로 보고한다. G2는 계산과 임계값을 바꾸지 않고 이름만 "same-rater agreement between the AH pass and the washout pass"로 부른다(DN-6, D20).
- §4 통계 처리(L558–599): BCa, 10,000 resample, seed 20260913, semantic-cluster 단위, 0사건의 Clopper–Pearson, 금지 목록. 특히 L597(재채점 라벨을 주 추정에 재사용 금지), L598, L599.
- §5 실패 정책(L603–613).
- CQ bank(`993c5e11…`), rubric(`d0c39758…`), rendering spec(`eb0399af…`), paraphrase 파일의 바이트(`c02ecda3…`), judge run의 `cells.jsonl`(`bfd5b3c8…`, `annotation_pending/DIGESTS.txt` L1). 재채점과 재실행은 없다.
- 잠긴 라벨(`f855e62` 매니페스트). 수정하거나 다시 라벨링하지 않는다.
- §11의 주장 격하와 레드라인(L1157–1179). 그대로 유지하며, D3 때문에 오히려 강화된다. §10은 계속 supersede된 상태다. 다만 §11 L1168의 "AH pass의 test--retest" 서술은 DN-6이 대체한다. 또 §11 L1163–1165의 "100% 블라인드"와 "독립 인간 앵커"는 D16·D20으로 대체된다. 48셀의 라벨은 이 연구 자신의 산출물(AH 초안, J 값, 저자의 라벨)을 보지 않는 비저자 annotator의 것이다. 다만 빈 span이 J = 0을 드러내므로 J = 0은 식별할 수 있다(D16). 이 annotator는 AI 채팅 도구를 쓸 수 있다(D20). 결과는 AI 도구 사용(예/아니오)별, 도구별로 층화해 보고한다.
- washout 최소 간격 21일(L522), 등록 seed 20260913(L14), 순서 드리프트 진단(L551).
- freeze block(L8–20)과 §1–§11의 원문. 고치지 않는다. D1은 기록일 뿐 L20을 바꾸지 않는다.
- Channel 1/2/3의 구분.

**위 목록의 예외: 이 addendum이 전향적으로 바꾸거나 더하는 것은 다음이다: D19, D20, DN-4a, DN-4b, DN-7, DN-9, DN-10.**
- L550의 세션당 60셀·세션 간 12시간 한도를 washout과 2차 annotator에 적용하지 않는다(D19; 저자 결정 2026-10-09). 따라서 §10.3(L1127)과 §11(L1182)이 "변경되지 않는 것"으로 적은 "세션 60/12h"는 이 두 절차에 대해서는 더 이상 성립하지 않는다. AH pass의 한도 이탈은 D5가 기록한다. §12는 L550이 여전히 유효하다고 주장하지 않는다.
- washout과 2차 annotation에서 AI 채팅 도구를 허용한다(D20). 등록된 본문은 이를 다루지 않았다.
- L485의 "같은 L₁ rubric으로 채점한다"를 A까지 넓힌다(DN-9).
- 강화층의 정의(DN-4a): 등록된 "`ASK` ↔ judge 충돌 셀"(L466)은 holdout에서 만들 수 없어 1[J ≥ 2] ≠ A_AH로 바꾼다.
- G2 게이트 입력(DN-4b): 재가중 pooled 추정에 적용한다. L467–468은 게이트 입력을 정하지 않았다. 가중치와 구간은 §12.3 "G2 계산"이 정의한다.
- control의 재제시와 G3-W(DN-7): washout에서 control 36개를 다시 제시하고 G3-W를 따로 보고한다. 등록된 G3(L345)을 대신하지 않는다.
- 일치 통계(DN-10): L509의 κ에 더해 원 일치율, Gwet AC1, PPA/NPA, 정확 일치율을 보고한다. 모두 기술 통계다.

### 12.7 결정 체크리스트

저자는 2026-10-09 KST에 아래 추천안을 일괄 승인하는 지시를 내렸다(07:36:52). 같은 날 이어서 DN-5를 두 가지로 바꿨다. 세션당 60셀·세션 간 12시간 제한의 제거 지시(07:49:15)와, 그 뒤 washout과 2차 annotation에서 AI 도구를 허용한다는 결정이다. DN-6의 명칭과 DN-7의 근거 문구는 이 변경에 맞춰 같은 날 고쳤다. 아래 결정일은 모두 2026-10-09(KST)다.

- [x] DN-1 G1 판정 수준 — (a): 97.5%(L564)로 판정하고 95%를 병기한다. 결정일 2026-10-09.
- [x] DN-2 washout 패킷 — (a): L522–523대로 다시 만든다(seed 20260913, 새 불투명 ID, paraphrase 파일 바이트 그대로 동결 선언, 의미 점검은 rater가 아닌 사람, 초안·번역·메타 chip 비표시). 결정일 2026-10-09.
- [x] DN-3 washout 표본 — (a): primary 72(48 + 24), control은 따로 센다. 결정일 2026-10-09.
- [x] DN-4a 강화층 — (c): judge–AH 불일치(1[J ≥ 2] ≠ A_AH)를 rater가 볼 수 없는 스크립트로 고르고 포함 확률을 봉인한다. 결정일 2026-10-09.
- [x] DN-4b G2 게이트 입력 — (a): 재가중 pooled, 두 층은 병기. 결정일 2026-10-09.
- [x] DN-5 일정과 조건 — 일정은 추천대로 2026-11-06 이후(하한 2026-10-30). 세션 한도는 제거(D19), AI 도구는 허용(D20), 초안은 비표시, dwell은 기록하고 최소 체류는 강제하지 않는다. 추천이었던 L550 복원과 AI 도구 금지는 채택되지 않았다. 결정일 2026-10-09.
- [x] DN-6 G2 해석 — (a): 계산과 임계값은 그대로, 이름은 "same-rater agreement between the AH pass and the washout pass". 결정일 2026-10-09.
- [x] DN-7 washout의 control — (a): 36개를 다시 제시하고 G3-W를 계산한다(화면 교정, 16개 민감도). 결정일 2026-10-09.
- [x] DN-8 2차 annotator 확정과 예치 시점 — (a)를 수정: 셀 목록의 sha256은 이 addendum과 함께, 신원 commitment는 모집 시점에. 결정일 2026-10-09.
- [x] DN-9 2차 annotator 라벨 열 — (a): A, rater_L1, span, note. 결정일 2026-10-09.
- [x] DN-10 일치 통계 — (a): 원 일치율, κ, Gwet AC1, PPA/NPA, L₁ QWK와 정확 일치율, 모두 기술 통계. 결정일 2026-10-09.
- [x] D19 세션당 셀 상한과 세션 간 최소 간격 제거(washout, 2차 annotation; L550로부터의 이탈). 결정일 2026-10-09.
- [x] D20 AI 채팅 도구 허용(washout, 2차 annotation; 세션 종료 시 사용 여부·도구 이름·대략의 셀 수를 기재하고 셀별 체크박스는 선택). 결정일 2026-10-09.

**승인 때 함께 처리한 것.** 초안에서 승인 시점을 비워 두었던 §12.0의 줄을 채웠다. 대조 표시가 붙어 있던 항목은 서버 세션 로그와 `SEAL_LEDGER.md`에 대조해 바꿨다(D5, D18, §12.5). [UNVERIFIED] 항목 중 확인된 것(D3의 화면 사실, D5의 세션별 저장 수)은 고쳤고, 확인되지 않은 것은 그대로 남겼다: D1, D3(약 절반, 붙여 넣은 내용), D11, D12, D13, D14(CVI), D15, 부기, D16(drafter 세션 하나의 "verdict"), D18(옵션이 켜져 있었는지), §12.0(이전 rater-safe 사본의 열람), §12.5.

**washout과 2차 annotation 전에 남은 일(위 결정에서 따라 나오는 것).**
- paraphrase 의미 동일성 점검(rater가 아닌 사람, washout 전; DN-2).
- washout 패킷 재생성(불투명 ID, 제약 셔플)과 ID 매핑 sha256 커밋(첫 washout 저장 전; DN-2).
- 비례층·강화층 선택 스크립트 실행(rater 비접촉)과, 층 소속·포함 확률의 봉인 및 sha256 공개(DN-3, DN-4a).
- 표본 선택 스크립트와 π_i 계산의 합성 fixture 테스트, 같은 입력으로 두 번 돌려 출력 sha256이 같음을 확인, python·numpy·scipy 버전 기록(DN-3, DN-4a, §12.3).
- 라벨링 도구의 행별 view 지원과 합성 fixture 테스트(DN-7), G2 층·재가중·CI 코드의 합성 fixture 테스트.
- 세션 종료 기재란과 선택 입력 "AI 사용" 셀별 체크박스의 구현과 합성 fixture 테스트(D20).
- AC1, PPA, NPA와 §12.4의 통계를 구현하고 합성 fixture로 테스트(DN-10).
- 2차 annotator 모집, 신원 commitment 커밋, 자격 확인, 동의서와 second-human export 기록 확인(DN-8, 부기).
- 48셀 목록 파일의 커밋(sha256 `bd2333d4…`과 일치 확인; DN-8).
- 외부 공개 전(release-prep): 대화 인용을 결정 요지로 줄이고 내부 경로와 세션 ID를 뺀다. [이 공개 사본에서 수행함; release/REDACTION_LOG.md]

## 13. [2026-10-09 addendum] washout·2차 주석 구현 확정 사항 — 첫 washout 저장 전

### 13.0 시점

표기는 §12와 같다. 이 addendum은 2026-10-09에, §12를 커밋한 `39e3978` 뒤에, washout과 2차 주석의 자료가 누구에게도 제시되기 전에 쓴다. §1–§12는 고치지 않는다(`PREREG.md` L1–1523이 그대로다). §12는 동결되어 있으므로 §12.1의 D-목록을 잇는 D21도 여기에 적는다.
- 이 절의 규칙은 패킷 빌더와 분석기의 코드 검토에서 나왔다. 검토는 합성 데이터만 썼다. 규칙을 정한 것은 AI 작업 세션(Claude Code)이며, 저자가 2026-10-09에 일괄 승인하고 결과의 책임을 저자가 진다고 밝힌 범위 안에서 정했다. 저자는 각 규칙을 따로 승인하지 않았다.
- 실제 입력은 개수를 세는 데만 썼다. 재생성한 view(ablated control) 또는 원본 view(preserved control, primary 셀)의 digest가 judge 실행의 `artifact_digest`와 일치하는 수는 ablated control 24/24, preserved control 12/12, primary 셀 188/188이다.

### 13.1 확정 사항

1. **D21 — [전향] washout에는 어느 행에도 graph 탭을 두지 않는다(§12.3 DN-2가 적은 "텍스트·그래프·도움말 탭"으로부터의 이탈).**
   - 이유: graph 탭은 variant별 TTL 그래프다. ablated control에 보이면 지워진 근거가 드러난다. control에서만 숨기면 어느 행이 control인지 표시가 된다.
   - 2차 annotator는 AH pass와 같이 graph 탭을 유지한다(§12.4 "자료").
   - 한계: AH pass에는 이 탭이 있었으므로 두 패스의 조건이 다르다. 이는 일치도를 낮출 가능성이 크며 G2에는 보수적인 방향이다 [추정].
2. **셔플.** 입력 행을 `opaque_id`(봉인한 salt에 의존)로 정렬한 뒤, 등록 seed 20260913과 `packet_common`의 등록된 제약 셔플 함수로 순서를 정한다(§12.3 DN-2). 같은 CQ의 최소 간격 20이 불가능하면 19, 18, …로 내려가며 성공하는 가장 큰 간격을 쓰고 달성한 간격을 보고한다. 48셀 2차 annotator 시트는 간격 15에 도달했다. 이는 길이 상한이다((M−1)·gap + k ≤ n, M = 4, k = 2, n = 48).
3. **의미 점검 파일.** 열이 `cq_id`, `verdict`(pass/fail), `checker`(rater가 아닌 사람의 식별자 또는 이니셜), `date`인 CSV이고 36행 전부를 덮는다. 빌더는 불완전한 파일을 거부한다. 이 파일과 sha256을 첫 washout 저장 전에 커밋한다. 대체: washout 날짜까지 rater가 아닌 사람의 점검이 없으면 모든 행에 원 CQ 문장을 보이고, 이 사실을 manifest에 적고 보고한다.
4. **view digest.** primary 셀의 view digest가 불일치하면 빌드를 중단한다. 불일치하는 preserved control은 제외하고 보고한다. ablated control은 §12.3 DN-7의 G3-W 규칙을 따른다.
5. **포함 확률.** π_i는 재실행 비율을 소수점 아래 4자리로 반올림한 값(`Decimal`의 ROUND_HALF_UP)이고 w_i = 1/(반올림한 π_i)다. π_i = 0이면 오류다(§12.3 "G2 계산"의 구체화).
6. **정의되지 않는 통계.**
   - G2(§12.3): 재표본의 E = 0은 QWK 0으로 세고 그 수를 보고한다. 관측값의 E = 0이면 계산 불가다.
   - §12.4의 통계: 정의되지 않는 replicate는 제외하고 그 수를 보고한다(§12.4 (i)). 정의되지 않는 점추정은 "정의되지 않음"으로 보고한다.
   - 층별 G2 구간은 그 층 자신의 CQ cluster를 가중 없이 재표본한다.
   - 두 패스 사이의 이진 A 일치는 층별과 가중 pooled로 보고하며, 가중하지 않은 pooled는 내지 않는다.
7. **AI 사용 기록(D20의 구체화).**
   - 한 번 앉아 라벨링한 구간(sitting)마다 `sitting_id`를 둔다. sitting을 마칠 때 rater가 사용 여부(예/아니오), 도구, 대략의 셀 수를 보고한다. 보고는 추가만 가능하다(append-only).
   - 선택 입력인 셀별 체크는 시트의 `ai_used` 열과 감사 로그에 남는다.
   - 주 층화는 "세션이 AI 사용을 보고함"이다. 체크된 셀과, "예"로 보고된 sitting의 체크되지 않은 셀이 이 층이다. 체크만 쓰는 층화는 민감도 분석이다. 도구별 결과는 "예" 셀 안에서 따로 낸다.
   - "AI를 쓴 셀"이라는 표현은 체크된 셀에만 쓴다. 그 밖의 셀은 "AI 사용을 보고한 sitting의 셀"이라고 쓴다.
8. **패킷 모드의 필수 입력.** 모든 행에 A와 rater_L1이 필요하고, A = 1이면 span도 필요하다. note는 2차 annotator에게 필수이고(DN-9) washout에서는 선택이다.
9. **패킷 모드의 dwell.**
   - 패킷 모드의 `dwell_ms`는 행을 연 시점부터 저장까지 클라이언트 `performance.now()`의 증분(정수 밀리초)이다. 기기 시계의 어긋남이 dwell을 바꿀 수 없다. AH 모드는 `elapsed_s`를 그대로 쓴다.
   - dwell 점검은 primary 셀마다 모든 저장의 dwell 합을 쓰고, control은 따로 보고하며, 사분위는 선형 보간이고, 세션 수는 `SESSION start` 줄로 센다.
   - AH pass의 `elapsed_s`는 서버의 저장 시각에서 클라이언트가 행을 연 `Date()` 시각을 뺀 값이었다(`f855e62`의 `label_assist.py` L383–401, L704). 따라서 LOCK의 "서버 기록"이라는 표현은 정확하지 않다.
   - 시계 어긋남 점검(`harness/real_run/results_human_pass/dwell_skew_check.py`; 출력 `dwell_skew_check.json`, sha256 `db30c2b994b6127430e10726cf8f7ae415084d1a32c5ff9bec687a91f3d0f94e`; 집계만 담음):
     - 클라이언트–서버 차이 추정치의 세션별 중앙값은 S6 0.14초, S7 0.228초다.
     - null이거나 음수인 `elapsed_s`는 0/200이다.
     - 서버 시각만 쓴 저장 간격 기준으로도 primary 171/187(91.4%)이 20초 미만이고, 중앙값은 9.0–9.44초다.
     - 두 기준 사이에 20초 경계를 넘는 셀은 0개다.
     - 따라서 G7 탈락은 시계 어긋남 때문이 아니다(확인함). 이 점검은 시간 측정만 확인할 뿐 라벨러가 들인 노력은 확인하지 않는다.
10. **washout 간격.** AH pass의 마지막 저장(2026-10-08 23:58:55 KST)부터 첫 washout 저장까지의 일수를 보고한다.
11. **manifest.** rater가 볼 수 있는 manifest에는 행 수와 파일·코드 hash만 둔다. 층, 부족분(shortfall), 선택 개수는 봉인한다.
12. **G3-W 민감도 목록.** S6에서 본 ablated control 8개의 목록은 rater가 아니라 에이전트 세션이 잠긴 AH 감사 로그에서 washout 전에 만든다. preserved control 4개는 ablated 민감도 분석에 들지 않는다. 목록 파일의 sha256을 첫 washout 저장 전에 커밋한다.
13. **탐색적 표지.** washout과 2차 주석의 모든 출력에 "탐색적(exploratory)" 표지를 붙인다(§12.2 (7)).
14. **운영(프로토콜 변경이 아님).** 라벨링 서버를 외부에 서빙할 때는 실행마다 token을 요구하고, same-origin JSON POST와 크기 상한을 강제하며, 단일 writer 잠금과 원자적 쓰기를 쓴다. salt는 무작위 32바이트이고 파일 권한은 0600이다. 빌더, `label_assist.py`, 분석기의 sha256을 첫 washout 저장 전에 커밋한다.
15. **(기록 정정) paraphrase 출처.** DN-2는 `bank/PARAPHRASE_FREEZE.md` L69–71에 따라 "36행 중 21행은 2026-09-13 작업 세션에서 생성, 15행은 저자 초안"이라고 적었다. 이 기록은 세션 기록과 맞지 않는다.
   - 36행 CSV는 2026-09-13 10:55:24Z에 Claude Code 세션의 GPT-5.6 계열 서브에이전트가 썼다.
   - 11:00:05Z에 Claude Opus 5가 그중 2행을 고쳤다.
   - 위 두 사실은 도구 호출의 메타데이터로만 확인했고, 내용은 열람하지 않았다.
   - 15행이 저자 초안에서 왔는지는 확인할 수 없다 [UNVERIFIED]. 파일 바이트와 동결 선언은 그대로 둔다.

## 14. [2026-10-09 addendum] washout·2차 주석 미실시와 봉인 해제

### 14.0 시점과 결정

표기는 §12와 같다. 이 addendum은 2026-10-09에, §1–§13을 커밋한 `256cc19` 뒤에 쓴다. washout과 2차 주석의 라벨은 한 건도 없다.
- 저자의 지시(2026-10-09 13:45:36, 대화 기록; 원문 인용 대신 결정 요지): 2차 주석자를 모집하지 않고 washout도 실시하지 않는다. 같은 메시지가 13:45:42에 한 번 더 기록되어 있다.
- 이 결정은 G4·G5의 값, judge × rater 혼동 개수, 셀 단위 결과가 저자에게 봉인된 채로 내려졌다. 저자는 그 값들을 보지 않았다. 다만 §12.0에 적은 5분위별 평균 rater_L1 사본의 예외는 그대로다(G4·G5 값 자체는 아니다).
- 이 결정은 저자의 결정이며 이유는 기록되지 않았다.

**D22 — washout 미실시(§12.3과 §13의 washout 규칙을 대체한다).**
- G2는 계산하지 않는다. G2는 등록된 게이트(L344)로 남되 평가하지 않았다("평가하지 않음"). 통과도 실패도 아니다.
- G3-W는 존재하지 않는다. 따라서 G3은 계산 불가로 남는다(§12.2 (4), D6).
- AH 라벨(LLM-assisted (AI-drafted, author-revised) labels)의 동일 rater 재현성은 알려지지 않았다. 한계로 적는다.
- §12.3의 DN-2–DN-7과 §13의 washout 규칙(D21 포함)은 실행되지 않는다. D19·D20·D21은 적용할 절차가 없어 효력이 없고 기록으로만 남는다. §13의 이미 일어난 일의 기록(9번의 AH pass 시계 어긋남 점검, 15번의 paraphrase 출처 정정)은 그대로다.

**D23 — 2차 non-author 주석 미실시(§12.4를 대체한다).**
- §12.4의 통계는 하나도 만들어지지 않는다(AH 대 2차 annotator 일치, 48셀 π̂와 cluster 단위 Clopper–Pearson 상한, judge 대 2차 annotator 일치).
- 48셀 목록(sha256 `bd2333d4…`)과 시트는 커밋된 그대로 두고 쓰지 않는다. 신원 commitment도 만들지 않는다.
- 한계: 이 연구에는 비저자 annotator의 라벨이 없다. §11 L1163–1165가 48셀에 맡긴 병기 보고는 이루어지지 않는다.

### 14.1 봉인 해제

- §12.3의 노출 통제 규칙이 G4·G5의 값, judge × rater 혼동 개수, 셀 단위 값을 봉인한 이유는 washout(G2)을 보호하기 위해서였다. washout이 없으므로 이 addendum의 시점부터 봉인을 푼다. 봉인 해제는 `SEALED_until_washout/`와 `locked_labels/sealed_results_until_washout/`의 사본에 모두 적용된다.
- 값은 등록된 분석기가 낸 그대로 보고하고 다시 계산하지 않는다. 이 addendum은 값을 담지 않는다. 출처 파일과 sha256은 `harness/real_run/results_human_pass/README.md`의 값이다.
  - 하드닝 재실행(분석기 `0dbe6e9`): `SEALED_until_washout/holdout_results_human.rerun_0dbe6e9.json`, sha256 `ee2650c7cfa1e7655305def2c7437ee9972cf7f7e5813460b4c81c4a84d7da49`(README L40).
  - 첫 실행(분석기 `ef62ef8`): `SEALED_until_washout/holdout_results_human.json`, sha256 `bcb4cbb4f59a1831139f1de7af7fad89ebfeea3a43955b02babc895b11b6a379`(README L48). 두 실행의 수치는 같다고 README가 적는다(L69–76). 같은 디렉터리의 sensitivity와 per-cell 파일의 hash는 README L41–42, L49–50에 있다.
- G4는 등록된 대로 반증 전용으로 남는다. CI 상한이 0.60 미만일 때만 실패하고 통과는 없다(L346).
- G5의 임계값은 바뀌지 않는다. MAE의 CI 상한이 0.50 이하여야 한다(L347).
- persona 결과(§12.5)는 열지 않았고 보고하지 않는다. 실행이 끝나지 않았고 탐색적 용도뿐이다. 그 봉인은 `SEAL_LEDGER.md`대로 유지된다.

### 14.2 미사용 도구

§12.3·§12.4·§13을 위해 만든 도구(패킷 빌더, 분석기, `label_assist.py`의 packet 모드)는 쓰지 않는다. 이 도구가 존재한다는 사실은 어떤 결과도 바꾸지 않는다.

### 14.3 변경되지 않는 것

- 위에서 다룬 것 밖의 모든 등록된 정의와 임계값.
- 잠긴 라벨(`f855e62` 매니페스트).
- A에 기반한 모든 통계의 탐색적 지위(§12.2 (7)).
