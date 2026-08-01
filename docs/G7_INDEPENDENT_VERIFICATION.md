# G7 독립 재학습 검증 절차

이 문서는 EXP-131·EXP-125 작성자가 아닌 팀원이 수행합니다. 검증자는 자신의
GitHub ID와 실행 환경을 `reproducibility/expNNN_*/reproduction_metrics.json`에
기록합니다.

## 공통 준비

```bash
git clone https://github.com/fabxoe/open_cancer.git
cd open_cancer
git checkout 46a4384
uv sync --frozen --group experiment
```

`data/raw/`에 대회 원본 CSV를 배치하고 다음 해시가 원본 manifest와 같은지
확인합니다.

```bash
shasum -a 256 data/raw/train.csv data/raw/test.csv data/raw/sample_submission.csv
```

Release 번들 [exp-g7-candidates-v1](https://github.com/fabxoe/open_cancer/releases/tag/exp-g7-candidates-v1)은 checkpoint·OOF·test 확률·submission을 제공하지만 raw data는 포함하지 않습니다.

## 후보별 재학습

각 후보의 resolved config를 기준으로 5-fold를 재학습합니다. 실행자는 원본
작성자와 다른 팀원이어야 하며, 설정·seed·canonical split을 변경하지 않습니다.

```bash
# EXP-125
uv run python scripts/run_exp125_lightgbm_v1.py

# EXP-131 (GPU 환경 필요)
uv run python scripts/run_exp131_catboost_v1_extended.py
```

실행 후 저장 checkpoint에서 OOF·test 확률과 submission을 재생성합니다. 원본
`metrics.json`과 다음 조건을 모두 비교합니다.

- OOF/test 라벨 일치율 100%
- 확률 `atol=1e-6`, `rtol=1e-6`
- 제출 CSV byte-level SHA-256 일치
- OOF Macro F1 차이 `≤1e-6`

## 판정

모든 조건을 통과하면 해당 manifest의 재현 상태를 `TRAINING_VERIFIED`로
승격하고 검증자 ID·환경·비교 결과를 기록합니다. 하나라도 실패하면
`FAILED`로 기록하며 원인과 환경 차이를 적습니다. 실패한 후보는 최종 제출
후보로 사용하지 않습니다.
