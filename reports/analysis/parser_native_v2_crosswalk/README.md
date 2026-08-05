# Parser compatibility·native v2 비중복 family 전수 감사

> Issue: [#462](https://github.com/fabxoe/open_cancer/issues/462)
>
> 모델 학습 없이 표현 차이만 측정했습니다.

## 결론

- missense·synonymous/no_change·nonsense·frameshift의 gene-level any는
  compatibility와 native v2가 완전히 같습니다.
- sample summary는 compatibility가 token count, native v2가 affected-gene
  count이므로 동일하지 않습니다.
- native v2의 strict range는 stop-containing range를 QC-only로 제외하므로
  EXP-444의 broad supported-range와 같지 않습니다.
- 다음 유효 ablation은 range 정의를 그대로 고정하고 native v2의 sample
  집계만 token count로 통제하는 것입니다.

## Train feature 비교

| family | gene any 동일 | sample count 다른 행 | 최대 차이 |
|---|---|---:|---:|
| `missense` | `True` | 1,353 | 4470 |
| `synonymous` | `True` | 530 | 2510 |
| `nonsense` | `True` | 136 | 162 |
| `frameshift` | `True` | 209 | 14 |

## 다음 행동

별도 Experiment Issue에서 EXP-456의 semantic routing과 gene-level any를
그대로 유지하고 sample summary만 token count로 바꿉니다. 그다음에만
strict range와 EXP-444 broad range의 차이를 별도 판단합니다. 두 변수를
한 실험에서 동시에 바꾸지 않습니다.
