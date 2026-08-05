# Parser v4 N4 L/C/N 결과 감사

> Issue: [#442](https://github.com/fabxoe/open_cancer/issues/442)

## 결과 요약

| Arm | EXP | OOF Macro F1 | Fold std | Accuracy | Log Loss |
|---|---:|---:|---:|---:|---:|
| Legacy L | 433 | 0.4132762899 | 0.0095342035 | 0.4029995162 | 1.9535857439 |
| Compatibility C | 435 | 0.4111034467 | 0.0086359500 | 0.4046121593 | 1.9422048330 |
| Native N | 438 | 0.4102050373 | 0.0109564971 | 0.4021931946 | 1.9731860161 |

Native N은 L 대비 OOF argmax 1,007행, test argmax 422행을 바꿨고 OOF 오류
상관은 0.8461입니다. 표현이 실제로 다른 신호를 만들었지만 Macro F1과 Log Loss가
모두 나빠졌으므로 첫 replacement adapter는 수정 대상입니다.

## 발견한 표현 문제

### Train support 0인 model-active 열

`sample__native_frameshift_ref_position_alt_gene_count`는 train nonzero가 0인데
test에서는 900행(35.35%)에 나타납니다. 첫 schema가 이를 model-active로 선언한 것은
N1의 train-support 원칙과 맞지 않습니다. 이 열은 QC-only로 내려야 합니다.

### Coarse fallback의 큰 annotation shift

`native_non_simple_or_unresolved` sample prevalence는 train 2.50%, test 34.84%입니다.
train 155행에 불과한 coarse 열 하나가 test 887행의 deletion·insertion·delins·unresolved
표기를 함께 받습니다. 서로 다른 생물학과 annotation novelty가 한 열에서 섞이므로
첫 baseline의 모델 입력으로 안전하지 않습니다.

### Replacement로 잃은 정보

Native N은 기존 5-family를 완전히 제거했습니다. missense/no-change/nonsense/frameshift는
대체 가능하지만, 기존 `complex`가 제공하던 넓은 lexical fallback과 native의 세분화
경계가 다릅니다. 정확한 parser를 유지하면서도 익숙한 coarse signal을 한 번에 버린
것이 성능 하락의 유력한 원인입니다.

## 다음 표현을 사전 고정

첫 후속 Experiment는 다음 hybrid만 시험합니다.

```text
full parser v4 compatibility 5-family
+ N1 train-support gate를 통과한 range_replacement 의미
```

- compatibility 5-family와 mutation presence·missing 유지
- byte-equivalent native missense/no-change/nonsense/frameshift 열 추가 금지
- train support 0 grammar와 unresolved/coarse fallback은 QC-only
- isoform·driver·pathway·hotspot·residue-position·Optuna 금지
- EXP-435와 동일 model/fold/seed/checkpoint/weight

이 결정은 N1의 train-only support와 L/C/N Local OOF를 사용했습니다. test prevalence는
원인 감사와 배포 위험 설명에만 사용했으며 schema 채택·threshold 선택에는 사용하지
않았습니다. 전체 수치는 [`audit.json`](audit.json)에 있습니다.
