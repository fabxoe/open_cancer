# N8 pathway·hotspot 재검증 — truncating 분류 legacy vs parser v4 감사

> Task Issue: [#587](https://github.com/fabxoe/open_cancer/issues/587)
>
> Parent roadmap: [#422](https://github.com/fabxoe/open_cancer/issues/422)
> `reports/plans/parser_v4_baseline_reset_roadmap.md` §12 "N6 이후 재검증
> 순서" 3번(pathway·hotspot)
>
> N6/N7 선례: #493/#495/#497/#499(isoform), #584/#585(driver)

## 배경 — N7과 달리 여기는 실제 이관 대상이 있다

N7(driver) 감사에서는 legacy 의존 자체가 없어 정적 감사만으로 종료했다. N8은
다르다: pathway burden(`abc_c_features.fixed_pathway_burden_family`)과
hotspot(`hotspot_features.build_hotspot_matrix`)은 지금도 **legacy 정규식
기반 분류**(`open_cancer.mutation_features.classify_mutation_token`,
`hotspot_features.SUBSTITUTION`)를 그대로 쓰고 있다.

## EXP-374 자체는 stop 표기 버그를 이미 피해간다 — 오판 방지 기록

처음에는 N6가 발견한 legacy `_SUBSTITUTION` 정규식의 stop `X`/`Ter` 누락
버그가 pathway/hotspot에도 그대로 남아있을 것으로 예상했다. 실제로 코드를
읽어 확인한 결과는 달랐다:

- `scripts/run_exp374_stop_isoform_residue_mask.py`의 `build_fold_features()`는
  `fixed_pathway_burden_family`·`pathway_mutation_type_family`에
  `token_parser=parse_stop_notation_invariant_token`을 명시적으로 주입하고,
  `main()`에도 `mutation_cell_parser=parse_stop_notation_invariant_cell`,
  `hotspot_token_normalizer=normalize_stop_notation_token`을 전달한다.
- `hotspot_features.build_hotspot_matrix`는 `token_normalizer`가 주어지면
  `SUBSTITUTION.fullmatch` 전에 먼저 정규화를 적용한다(코드 확인,
  `normalized = token_normalizer(token) if token_normalizer else token`).
- 반면 이 default 주입은 `run_exp374_...py` 자체에만 있다.
  `run_exp229_pathway_mutation_types.py`(EXP-229/285/323/334의 부모 계보)의
  `PathwayMutationTypeFoldBuilder` 기본값은 여전히 미수정 legacy
  `fixed_pathway_burden_family`다 — EXP-369(#369) 커밋이 `burden_factory`를
  주입 가능한 파라미터로만 바꿔놓고 기본값은 그대로 뒀기 때문이다(diff 확인:
  `f49bf22`). 즉 **현재 팀 최고 계보(EXP-374 이후)는 stop 표기 버그를 이미
  피해가지만, 그 이전 계보(EXP-096/223/229 자체를 그대로 재실행하면)는 여전히
  버그가 있다** — 다만 이 부분은 새로 재실행할 계획이 없는 과거 계보라 이
  Task의 스코프에 넣지 않는다.

## 실제로 남아있는 gap — naive `.endswith("fs")` frameshift 판정

`stop_notation_invariant` 계열 정규화는 **단순 substitution stop-gain**만
`*`로 정규화한다(`robust_mutation_parser.normalize_stop_notation_token`,
`source_structure == "simple_substitution" and event_family == "stop_gain"`
조건 확인). frameshift·delins 토큰은 건드리지 않는다.

그런데 `classify_mutation_token`(`mutation_features.py`)의 frameshift 판정은

```python
if token.endswith("fs"):
    return "frameshift"
```

문자열 suffix 검사 하나뿐이다. `PROJECT_CONTEXT.md`가 명시적으로 경고하는
바로 그 실패 사례들(`SDEL133fs`의 `DEL`을 deletion으로 오인, `721_722LA>FS`의
`FS`를 frameshift suffix로 오인)이 여기 그대로 해당한다. delins 유래
nonsense(`protein_delins_semantics`가 다루는 stop 포함 delins)도
`classify_mutation_token`에는 아예 없어서 "complex"로 떨어진다.

parser v4는 이미 올바른 기준을 갖고 있다 — EXP-558(`compact_clinical_features.
_is_truncating`)이 실제로 채택해 쓰는 정의:

```python
def _is_truncating(event):
    return (
        event.route == "frameshift"
        or (event.route == "substitution" and event.event_type == "nonsense")
        or (event.route == "delins" and event.event_type == "nonsense")
    )
```

pathway burden의 `_TRUNCATING_TYPES = {"nonsense", "frameshift"}`(레거시
분류 문자열 기준)는 이 v4 정의와 판정 근거가 다르다.

## 감사 스크립트

`scripts/audit_pathway_hotspot_v4_truncating_diff.py` — target-independent,
SUBCLASS·Public LB 미사용. Sanchez-Vega canonical pathway 유전자
(`knowledge/canonical_pathways_sanchez_vega_v1.json`) ∪ hotspot 유전자
(`hotspot_features.EXTENDED_HOTSPOTS`) 범위로 스코프를 좁혀, train+test 전체
고유 (gene, token) 쌍에 대해 다음을 비교한다.

- legacy: `classify_mutation_token(normalize_stop_notation_token(token))`이
  `{"nonsense", "frameshift"}`에 속하는지(현재 pathway burden이 실제로 쓰는
  판정 경로 — EXP-374 stop-notation 수정 이후 상태를 그대로 재현)
- v4: `route_protein_mutation(token)`이 `_is_truncating` 기준을 만족하는지

실행(사용자 확인 필요, 에이전트가 직접 실행하지 않음):

```bash
uv run python scripts/audit_pathway_hotspot_v4_truncating_diff.py
```

출력은 `reports/analysis/n8_pathway_hotspot_truncating_audit/summary.json`
(방향별 건수, v4 route/event_type 분포)과 `diffs.json`(불일치 토큰 전체
목록)에 저장된다.

## 실행 결과(저장소 소유자 확인, 2026-08-06)

```json
{
  "pathway_hotspot_gene_count": 170,
  "unique_gene_token_pairs": 25479,
  "direction_counts": {"agree": 25472, "legacy_only_truncating": 7},
  "v4_route_of_new_truncating": {},
  "v4_route_of_lost_truncating": {"unresolved:other_unmappable": 7}
}
```

25,479개 고유 (gene, token) 쌍 중 **7건(0.027%)만 불일치**했고, 방향은 전부
"legacy만 truncating"이다(v4가 legacy보다 더 truncating으로 판단하는 경우는
0건). `diffs.json`을 열어보면 7건 전부 동일 패턴이다.

```text
PTEN -151fs   PTEN -46fs   PTEN -65fs   PTEN -74fs
TP53 -222fs   TP53 -278fs   TP53 -347fs
```

전부 `-NNNfs` 형태의 **signed frameshift 표기**다. 이는 새로 발견한 버그가
아니라 이미 문서화된 사례다 —
[`reports/analysis/partial_terminal_semantics/README.md`](../partial_terminal_semantics/README.md)가
`-762fs`류 signed 표기를 정상 protein residue 위치로 강제 해석하지 않고
"기존 adapter에서는 계속 `other_unmappable`"로 유지한다고 명시한다(5'
UTR/upstream 등 위치 자체가 모호하기 때문). 즉 여기서 legacy가 이 7개를
truncating으로 세는 쪽이 실제로는 **과대 계산**이고, parser v4가 "확정 불가"로
보수적으로 처리하는 쪽이 이미 결정된 올바른 설계다.

## 결론

- 불일치 규모가 극히 작다(0.027%, 2개 유전자, PTEN/TP53). N6(isoform, 2.14%
  불일치)조차 OOF에 측정 가능한 영향이 없었던 선례를 감안하면, 이보다 훨씬
  작은 규모의 diff가 OOF를 움직일 가능성은 낮다.
- 이 불일치는 "고쳐야 할 버그"가 아니라 "legacy가 이미 알려진 모호 표기를
  과대 계산하고 있었다"는 확인이며, parser v4 쪽 동작은 이미 팀이 결정한
  정책과 일치한다.
- 대회 마감(2026-08-07)이 임박한 점을 고려해, 재실행 Experiment는 제안하지
  않고 이 감사 결과를 문서화하는 선에서 N8을 COMPLETED로 마무리한다.
