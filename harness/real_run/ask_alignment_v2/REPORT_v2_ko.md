# 실험 2 보고: 술어 정렬을 포함한 표준화 SPARQL 오라클 (addendum 16)

탐색적·사후 보강. 원고(`main.tex` 등)와 `PREREG.md`는 수정하지 않았다. 규칙은 동결 커밋 `f91fc40`(태그 `access2026-addendum16-freeze`)에 고정했고, 동결 뒤에 구현·실행했다. 이 코드와 결과는 AI가 만들었으므로 사람이 검토하고 테스트하기 전에는 원고에 쓰지 않는다. 확인함 = 이 세션에서 실행·열람한 값.

## 1. 결론 (사전 규칙 대비)

**판정: 불기능(not_functional).** 판정 모집단은 결정적 18 CQ × 변형 B–F(90회, 평가 가능한 primary 셀 55개, cluster 11개).

| 조건(16.4) | 기준 | 관측 | 결과 |
|---|---|---|---|
| C0 비상수 | true·false 모두 존재 | true 15 / false 40 | 통과 |
| C1 평가 가능성 | not_evaluable ≤ 10% | 35/90 = 38.9% | 실패 |
| C2 κ(오라클, S_AH) | ≥ 0.40 | 0.072 (BCa [0.00, 0.56]) | 실패 |
| C3 κ(오라클, S_독립) | ≥ 0.40 | 0.154 (BCa [0.00, 0.65]) | 실패 |

부분 기능의 조건(C0∧C2∧C3)도 채우지 못했다. 정렬은 v1의 108/108 false를 깼지만(B–F에서 true 0 → 15) 오라클을 독립 기준으로 만들지는 못했다. 사전 선언(16.4)대로 C1 실패는 예상된 것이고(용어 매핑을 바꾸지 않았다) C2·C3 실패는 예상하지 않은 것이다.

## 2. 정렬 전후 (결정적 18 / 전문가 필요 18; true / false / not_evaluable)

| 변형 | 결정적 18 전 | 결정적 18 후 | 전문가 18 전 | 전문가 18 후 |
|---|---|---|---|---|
| A | 7 / 8 / 3 | 7 / 8 / 3 | 10 / 8 / 0 | 10 / 8 / 0 |
| B | 0 / 11 / 7 | 3 / 8 / 7 | 2 / 16 / 0 | 3 / 15 / 0 |
| C | 0 / 11 / 7 | 3 / 8 / 7 | 2 / 16 / 0 | 3 / 15 / 0 |
| D | 0 / 11 / 7 | 3 / 8 / 7 | 2 / 16 / 0 | 3 / 15 / 0 |
| E | 0 / 11 / 7 | 3 / 8 / 7 | 3 / 15 / 0 | 3 / 15 / 0 |
| F | 0 / 11 / 7 | 3 / 8 / 7 | 3 / 15 / 0 | 3 / 15 / 0 |

- "전"은 v1 `ask_results.json`과 결정적 18에서 108칸 모두 일치한다(테스트로 확인함; 용어 매핑 54개도 v1 `mapping.csv`와 같다).
- outcome이 바뀐 쌍은 false→true 18개뿐이다: 결정적 15개(CQB13·14·16 × B–F, 규칙 P3 `ex:p_inverse`)와 전문가 필요 3개(CQB01 × B–D, 규칙 P4 `ex:p_define`). 그 밖의 쌍은 전부 그대로다(true→false 0). 목록은 `ask_results_v2.json`의 `changed_pairs`.
- 규칙 발동: P1·P2 = 6쌍/변형(subClassOf 질의), P3 = 7, P4 = 3, P7 = 6. P5·P6은 질의가 `rdfs:label`을 쓰지 않아 0회(사전 [추정]대로). 규칙 적용 수: 적용 7 + 항등 1, 제외 5, 대응 없음 5.
- 변형 A는 전후가 같다(재작성이 A의 결과를 바꾸지 않았다).
- 계층 질의 CQB07·08·10·12는 B–F에서 여전히 false다. P1·P2가 발동했는데도 그렇다(확인함, 사후 진단): B에서 `brick:Location`이 용어 매핑 6단계 중 `local_normalized`로 노드 `ex:location`에 묶이는데, 실제 계층 간선은 `ex:brick-building p_subclass ex:brick-location`처럼 접두 노드를 향한다. 두 노드가 따로 존재한다. 동결된 단일 후보 규칙의 한계이며 이 실험에서는 고치지 않았다. 참고(any-candidate 상한, 동결 외 보조 수치): B–F 결정적 90회 중 25회가 true(CQB07·10·13·14·16 × 5)이고 10회는 cap 초과다.

## 3. 일치도 (결정적 18, 평가 가능한 primary 셀)

행: 오라클(true=1) 대 각 기준. κ 구간은 CQ cluster BCa 95%. CP = cluster 단위 일치 cluster 비율의 단측 97.5% 하한(Clopper–Pearson, `clopper_pearson_upper` 재사용).

| 모집단 | n(cluster) | 오라클 true | κ(J≥2) | κ(S_AH) | κ(S_독립) | 단순 일치(S_AH / S_독립) | CP 하한(S_AH / S_독립) |
|---|---|---|---|---|---|---|---|
| B–F (판정) | 55 (11) | 15 | 0.088 [0.00, 0.56] | 0.072 [0.00, 0.56] | 0.154 [0.00, 0.65] | 0.364 / 0.455 | 0.109 / 0.167 |
| A (별도 행) | 8 (8) | 4 | 0.500 (구간 계산 불가) | 0.250 (불가) | 0.250 (불가) | 0.625 / 0.625 | 0.245 / 0.245 |
| 108셀 pooled (기술용) | 63 (11) | 19 | 0.118 [0.02, 0.57] | 0.087 [0.00, 0.57] | 0.167 [0.00, 0.60] | 0.397 / 0.476 | 0.060 / 0.109 |
| 민감도: 술어 부재 false 제외, B–F | 40 (8) | 15 | 0 | 0 | 0 | 0.375 | 0.085 |

- 2×2(B–F, 오라클 행 × S_AH 열): true/S=1 15, true/S=0 0, false/S=1 35, false/S=0 5. 오라클 true는 15개 모두 S_AH=1·S_독립=1·J≥2다(과대 인정 0). 그러나 S_AH=1인 50개 중 15개만 잡는다(재현율 0.30). κ가 낮은 이유는 오라클의 오류가 한 방향(누락)뿐이고 S=1이 91%(50/55)로 높아서다.
- 기준선(같은 55셀): κ(S_AH, S_독립) = 0.621, κ(J≥2, S_AH) = 0.899. 오라클은 사람·judge 쌍보다 훨씬 낮다.
- 오라클 true 15개는 CQB13·14·16(역관계 3개 × 5변형)에서만 나온다. 독립 단위는 3 CQ다. cluster 11개 중 7개(S_독립 기준 6개)가 불일치 cluster다.
- 민감도 행은 오라클이 true인 15셀이 모두 S=1이고 false 25셀도 모두 S=1인 모집단이라 κ가 0이다(두 번째 평가자가 상수). 판정에는 쓰지 않는다.

## 4. 남은 한계 항목

- **미매핑 용어(6단계, 변경 없음)**: B–F 7개 = `brick:EntityProperty`, `buildingPrimaryFunction`, `feeds`, `isReplacedBy`, `isVirtualMeter`, `yearBuilt`, `qudt:hasQuantityKind`. A는 2개(`brick:EntityProperty`, `qudt:hasQuantityKind`). 결정적 18 중 CQB15·21–24·32·33이 B–F에서 not_evaluable.
- **술어 부재 false**(결정적, 대응 규칙 없음): B–F 20회 = `sh:path` 10, `sh:class` 5, `owl:disjointWith` 5(CQB11·17·18 × 5), A 4회. 이 셀의 false는 변형 어휘의 부재이지 내용의 부재가 아닐 수 있다.
- 전문가 필요 18: 정렬 후 변형당 true 3개(A는 10개)뿐이고 나머지는 false다. `rdfs:comment`를 쓰는 질의는 B–F 그래프에 그 술어가 없어 false가 되는 것으로 보인다 [추정, 질의별 `predicates_without_triples`로 확인 가능]. 분포만 보고한다.

## 5. 한계

1. 셀 55개·cluster 11개이고 오라클 true는 CQ 3개가 전부다. κ 구간은 하한이 0에 붙고 폭이 0.5 이상이라 점추정을 신뢰할 수 없다(해석은 "기준을 못 넘었다" 이상으로 하지 않는다).
2. 오라클 true는 정밀하다(15/15) 하지만 커버리지가 작다. "오라클이 틀렸다"가 아니라 "대부분의 셀에서 말할 수 없다 또는 누락한다"이다.
3. 동결 규칙의 임계값(10%, 0.4)과 DN16-2 결정은 AI 세션이 정했고 저자가 개별 승인하지 않았다(addendum 체크리스트의 마지막 칸이 열려 있다).
4. 규칙은 v1 결과를 안 뒤에 정했다. 사전등록의 지위는 "매핑 적용 결과를 보기 전"이라는 순서뿐이다. 동결 전에 열람한 것은 addendum 16.0에 적었다.
5. 독립 평가자 라벨은 `labels_v3.csv`의 `S_label`이다. 독립성은 저자의 지정이며 이 세션이 검증하지 않았다 [UNVERIFIED]. S_AH와 S_독립은 S=1 비율이 모두 높아(55셀 중 각각 50, 45) 천장 효과가 있다.
6. 단일 후보 용어 매핑이 만든 오류(위 계층 질의)는 정렬 규칙으로 고쳐지지 않았다. 용어 쪽 개선은 별도 사후 규칙이다.
7. 재현: 동결 입력 sha256과 스크립트 sha256은 `ask_results_v2.json`에 있다. 테스트 `harness/test_ask_alignment_v2.py` 17개 통과(확인함; 규칙 단위, v1 대조, 두 번 실행 바이트 동일). 명령: `PYTHONPATH=<repo>/src <repo>/.venv/bin/python harness/real_run/ask_alignment_v2/run_oracle_v2.py`.

## 6. 원고용 초안 (삽입하지 않음; 외부 배포 전에 기밀·개인정보·경로 확인)

**영문 문단(5문장).**

> After the ASK oracle returned false on all 108 query-by-variant runs, we registered a post hoc supplement (addendum 16, frozen before any rewritten query was run) that maps seven pipeline predicates to their Brick counterparts and applies the map to the queries, never to the graphs. The map turned the oracle true on 15 of the 90 runs on variants B to F (three inverse-relation queries on each variant), but 35 of the 90 runs stayed not evaluable because 7 query terms have no counterpart. On the 55 evaluable primary cells the oracle agreed with the AH labels at $\kappa=0.07$ and with the independent rater at $\kappa=0.15$, against 0.62 between the two sets of labels, so it did not meet the registered criterion ($\kappa\ge0.40$ against both label sets and at most 10\% not evaluable). Every true oracle outcome coincided with a supported label, but the oracle recovered only 15 of the 50 supported cells, and all of its true outcomes come from three queries. We therefore keep the oracle as a precise but low-coverage check and not as an independent reference standard.

**compact 표(`tab:oraclev2` 제안).**

```latex
\begin{table}[t]
\centering
\caption{$n=55$ evaluable primary cells on variants B--F, 18 deterministic queries; unit = cell; interval = CQ-cluster BCa $95\%$; post hoc, registered in addendum 16 before execution. Oracle outcome after predicate alignment against the judge score and the two label sets.}
\label{tab:oraclev2}
\begin{tabular}{lccc}
\toprule
Reference & $\kappa$ [interval] & Agreement & Oracle true / reference positive \\
\midrule
Judge $J\ge2$ & 0.09 [0.00, 0.56] & 0.38 & 15 / 49 \\
AH label $S$ & 0.07 [0.00, 0.56] & 0.36 & 15 / 50 \\
Independent rater $S$ & 0.15 [0.00, 0.65] & 0.45 & 15 / 45 \\
\midrule
Not evaluable (90 runs) & \multicolumn{3}{c}{35 (38.9\%); registered limit 10\%} \\
\bottomrule
\end{tabular}
\end{table}
```

**삽입 위치 제안.** `main.tex` L948의 "(a) The query oracle after mechanical namespace alignment" 단락 바로 뒤(`tab:ask` 다음)에 문단과 `tab:oraclev2`를 넣고, L949의 "Even after alignment ... 4 of the 63" 문장을 "술어 정렬 후에도"로 연결하는 한 문장만 손본다. L1242 "(construct)" 한계 문장과 서문 L234–235의 oracle 설명에는 "predicate-aligned oracle, post hoc" 한 구절을 더한다. 표의 "reference positive" 열(49/50/45)은 `ask_results_v2.json`의 2×2에서 다시 센 값이므로 삽입 전에 한 번 확인한다(J≥2 양성 49 = 15+34, S_AH 양성 50 = 15+35, S_독립 양성 45 = 15+30).
