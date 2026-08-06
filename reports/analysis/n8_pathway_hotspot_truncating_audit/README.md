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

## 다음 단계

이 README와 스크립트를 근거로 N8 Task Issue를 연다. 스모크 실행 결과
(`summary.json`)를 확인한 뒤:

- 불일치가 미미하면(예: 0건 또는 한 자릿수) N7처럼 "재현·문서화만 하고
  COMPLETED" 처리한다.
- 불일치가 유의미하면 EXP-096/223/229/369/374 lineage 중 실제로 재실행할
  가치가 있는 대표 모델(가장 유력한 후보: 현재 팀 최고 EXP-374 자체, 아직
  frameshift/delins truncating 판정을 v4로 교체하지 않았으므로 이 버그의
  대상이다)을 골라 별도 Experiment Issue로 재실행을 제안한다. N6(EXP-497)
  선례처럼 NULL_RESULT일 수도 있다는 점을 미리 인지하고 접근한다.
