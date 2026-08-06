# SAINT B0 128·256·512 smoke

## 상태

- Task Issue: [#508](https://github.com/fabxoe/open_cancer/issues/508)
- Parent plan: [#504](https://github.com/fabxoe/open_cancer/issues/504)
- 공식 실험: 아님
- EXP-ID·OOF·Public LB·History 갱신: 없음

## 목적

PR #507의 fold-safe parser-v4 semantic compressor가 만든 128·256·512열을
작은 SAINT row/column attention 모델이 실제로 처리할 수 있는지 확인했습니다.
이 단계는 성능 비교가 아니라 shape·OOM·NaN·gradient·결정적 추론 검사입니다.

## 실행 조건

- source cache: `data/processed/issue475_native_v3_analysis`
- canonical outer fold: 0
- outer-train: 4,960행
- validation: 1,241행
- test: 2,546행
- PyTorch: 2.13.0
- device: Apple MPS
- token dimension: 32
- depth: 2
- attention heads: 4
- batch size: 4
- optimization step: 차원별 2회
- model output: 26-class logits

실행 명령:

```bash
uv run --group experiment python scripts/run_saint_b0_smoke.py \
  --cache-dir data/processed/issue475_native_v3_analysis \
  --split-path data/splits/stratified_5fold_seed42.csv \
  --train-path data/raw/train.csv \
  --output reports/analysis/saint_b0_smoke/smoke_metrics.json \
  --device mps \
  --batch-size 4 \
  --steps 2
```

## 결과

| 차원 | binary | continuous | 파라미터 | runtime | peak MPS memory | finite | 고정 batch 추론 |
|---:|---:|---:|---:|---:|---:|---|---|
| 128 | 117 | 11 | 51,482 | 4.68초 | 13.77 MiB | 통과 | exact 일치 |
| 256 | 245 | 11 | 67,866 | 1.14초 | 6.58 MiB | 통과 | exact 일치 |
| 512 | 501 | 11 | 100,634 | 1.46초 | 9.22 MiB | 통과 | exact 일치 |

첫 128차원 실행에는 MPS 초기화 시간이 포함되어 차원별 runtime을 직접적인
성능 비교로 해석하지 않습니다. 모든 차원에서 forward, cross-entropy loss,
backward gradient와 validation/test logits가 finite였습니다.

## 결정성 및 주의점

동일 checkpoint와 동일한 고정 validation batch를 두 번 넣었을 때 logits tensor가
정확히 같았습니다. 그러나 row attention은 mini-batch 안의 다른 환자도 참조하므로
batch 구성과 순서가 달라지면 한 환자의 출력도 달라질 수 있습니다.

따라서 후속 B1/B2에서는 다음을 실행 계약으로 저장해야 합니다.

- train sampler seed와 epoch별 permutation
- validation/test ID 순서
- batch size와 마지막 batch 처리
- checkpoint inference의 고정 batch policy

또한 MPS backward에서 `index_put_with_accumulate_mps`의 deterministic 구현이 없다는
PyTorch 경고가 발생했습니다. 고정 batch inference는 통과했지만 공식 학습 재현성
검증은 CUDA 환경에서 수행하는 것이 안전합니다.

## 판단

세 차원 모두 메모리·shape gate를 통과했으므로 B1의 제한된 2-fold 차원 screening을
진행할 기술적 조건은 충족했습니다. B1은 별도 Experiment Issue에서 진행하고,
128·256·512 외의 구조·학습률 탐색은 섞지 않습니다.
