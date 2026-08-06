# Parser v4 hierarchical event-token adapter

이 adapter는 환자별 canonical event token을 두 블록으로 변환합니다.

1. `detail|gene=TP53|aa_transition=R>H`처럼 유전자를 보존한 세부 token
2. `global|aa_transition=R>H`처럼 유전자를 제거한 coarse fallback token

`family` token에는 `substitution`, `inframe_structural`, `frameshift`, `range`,
`unresolved`의 `route_group` fallback도 추가합니다. 이는 새 생물학적 사실을
추정하는 것이 아니라 parser가 이미 판정한 의미의 해상도만 낮추는 것입니다.

## fold 계약

- `fit_hierarchical_event_adapter()`에는 outer-train 환자 token만 전달합니다.
- detail 기본 최소 support는 환자 2명, global 기본 최소 support는 1명입니다.
- validation/test는 fitted adapter의 `transform()`만 호출합니다.
- unseen detail은 train에서 관찰된 global 의미가 있을 때만 복구합니다.
- global 의미까지 train에 없으면 OOV로 유지하며 임의 coefficient를 만들지
  않습니다.

## 출력

- feature 순서는 detail 사전순 다음 global 사전순입니다.
- 실제 feature 이름·support·normalization을 포함한 SHA-256을 제공합니다.
- `raw`는 사건 count를 유지합니다.
- `row_l2`는 같은 vocabulary와 count 행렬을 만든 뒤 환자 행별 L2 norm을
  1로 맞춥니다. mutation이 전혀 없는 0행은 그대로 보존합니다.

다음 공식 Experiment에서는 동일 vocabulary로 `raw`와 `row_l2`만 바꾸어
canonical 5-fold Macro F1을 비교해야 합니다. TF-IDF는 그 다음 독립 실험으로
분리합니다.
