# Experiment configurations

Issue를 만들 때 모든 하이퍼파라미터를 작성할 필요는 없습니다. 실험별 override가
있을 때만 `exp012_<slug>.yaml` 형식으로 저장합니다. override가 없으면 모델 코드의
기본값을 그대로 사용합니다.

실행 코드는 기본값과 override를 병합한 실제 값을
`reproducibility/exp012_<slug>/config.resolved.yaml`에 기록해야 합니다. 이 resolved
config가 실제 파라미터의 단일 원본이므로 Issue나 History에 같은 값을 다시 적지
않습니다.

공통 기본값과 선택 항목은 `PROJECT_CONTEXT.md`의 “실험 설정 계약”을 따릅니다.

ABC-Stack v2 후보 family의 공통 기본값은 점수를 만들지 않는 Task 설정으로
분리합니다. A family는 [`abc_stack_a_families.yaml`](abc_stack_a_families.yaml)을
사용하며 모든 family는 기본적으로 꺼져 있습니다. 공식 5-fold를 실행할 때만 새
Experiment Issue의 `expNNN_*.yaml`에서 정확히 한 family를 켜고, resolved config에
병합된 실제 값을 저장합니다.

## Residue-position family

Feature Factory v1.1은 다음 설정을 지원합니다. 실제 공식 평가에서는 새
Experiment Issue의 config에 필요한 조합 하나만 기록합니다.

```yaml
features:
  mutation_type:
    enabled: true
  residue_position:
    enabled: true
    aggregates: [min, max, span]
    missing_policy: indicator       # zero | indicator
    complex_tokens: exclude         # include | exclude
    transform: coarse_bin           # raw | coarse_bin
    bin_width: 100                   # coarse_bin에서만 사용
```

- `zero`: 위치를 읽지 못한 유전자의 위치 피처는 희소행렬의 0으로 남긴다.
- `indicator`: 위 0 처리에 `residue_position_observed` 피처를 자동 추가한다.
  현재 데이터에서는 기존 mutation-presence와 완전히 같으므로 신규 실험에는
  사용하지 않고, 데이터 계약이 바뀐 경우 semantic equivalence QC 후 사용한다.
- `exclude`: `_`, `>` 등 complex 토큰에서 읽은 위치는 위치 aggregate에서 제외한다.
  frameshift는 별도 mutation type이므로 포함된다.
- `coarse_bin`: `(position - 1) // bin_width + 1`의 고정 구간 번호를 사용한다.
- 유전자별 정규화는 각 validation fold를 제외한 fold-train에서 분모를 다시
  fit해야 하므로 정적 Factory 옵션으로 제공하지 않는다. 후속 fold transformer가
  준비되기 전 `gene_train_max` 같은 설정은 오류로 차단한다.

기존 EXP-047 config처럼 옵션을 생략하면 `min + zero + include + raw`가 적용돼
기존 결과와 피처 순서를 유지한다. fold-train recurrent hotspot은 fold마다 fit이
필요하므로 이 정적 family에 포함하지 않고 별도 Experiment의 fold selector로
구현한다.
