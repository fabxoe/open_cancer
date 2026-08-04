# Issue #306 sparse denoising autoencoder fold-0 smoke

## 결론

`STOP`입니다. 이 설정은 공식 5-fold 실험이나 새 EXP-ID로 확장하지 않습니다.

원본 4,384개 mutation-presence 피처를 유지한 EXP-229에 64차원 잠재벡터를
추가했지만 fold 0 Macro F1이 `0.4125153614`에서 `0.3716417281`로
`-0.0408736333` 하락했습니다. 사전 고정한 최대 허용 하락 `-0.01`을 크게
넘습니다.

## 실험 경계

- 기준 모델: EXP-229
- 평가 범위: canonical split의 outer fold 0만 사용
- AE fit 범위: outer-train 내부의 label-free 90% partition
- AE early-stopping 범위: outer-train 내부의 label-free 10% holdout
- outer validation과 test: encoder transform만 수행
- downstream: EXP-229의 원본 피처를 삭제하지 않고 latent 64개만 추가
- checkpoint 선택: outer-validation Macro F1
- test·Public LB: 피처·checkpoint·판정에 사용하지 않음

## 결과

| 항목 | EXP-229 fold 0 | AE latent 추가 | 차이 |
|---|---:|---:|---:|
| Macro F1 | 0.4125153614 | 0.3716417281 | -0.0408736333 |
| Accuracy | 0.4020950846 | 0.3738920226 | -0.0282030620 |
| Log Loss | 1.8775094748 | 2.4438071015 | +0.5662976268 |

재구성 및 잠재공간 감사:

- gene-prevalence baseline unweighted BCE: `0.0404628628`
- autoencoder unweighted BCE: `0.2398404852`
- true-positive 평균 복원 확률: `0.6425561309`
- true-zero 평균 복원 확률: `0.1657797992`
- zero collapse: 없음
- near-constant latent dimension: `0 / 64`
- 최대 `|corr(latent, mutated-gene burden)|`: `0.9677136278`
- 전체 smoke runtime: `201.08초`
- peak RSS: `0.81 GiB`

## 게이트 판정

통과:

- zero collapse 없음
- 상수 latent 축 제한 통과
- AE checkpoint 재추론 정확히 일치
- downstream 추론 반복 결과 정확히 일치
- 실행 시간·메모리 제한 통과

실패:

- AE 재구성이 gene-prevalence baseline을 이기지 못함
- latent 축이 단순 mutated-gene burden을 과도하게 복제함 (`0.9677 > 0.95`)
- fold 0 Macro F1 하락 제한 실패

## 해석

희소 mutation-presence에서 positive-weighted BCE는 변이 위치를 0으로만
예측하는 붕괴는 막았지만, 전체 분포를 복원하는 능력은 단순 유전자별 출현
빈도보다 나빴습니다. 잠재공간도 새로운 암종 구분 구조보다 샘플별 총 변이량을
강하게 재표현했습니다. EXP-229에는 이미 burden·mutation type·pathway 요약이
있으므로 이 중복 신호가 XGBoost의 일반화를 악화시킨 것으로 해석합니다.

이 결과는 모든 representation learning을 부정하지 않습니다. 다만 현재의
`4384→128→64`, positive-only masking, weighted BCE 조합은 종료합니다. 향후 다시
검토하려면 같은 설정의 5-fold 확장이 아니라, 사전에 정의한 다른 목적함수나
구조를 새 일반 Task에서 fold-0 게이트부터 검증해야 합니다.

## 재현

```bash
uv run --group experiment python scripts/run_task306_autoencoder_fold0_smoke.py
```

macOS에서 PyTorch 2.13과 XGBoost 3.2를 같은 프로세스에 로드하면 네이티브
OpenMP 충돌이 발생했으므로, runner는 Torch encoder stage와 XGBoost stage를
별도 프로세스로 실행합니다. 성능 판정과 무관한 실행환경 호환성 조치입니다.

수치 원본은 [smoke_metrics.json](smoke_metrics.json)에 있습니다. checkpoint와
latent 행렬은 Git 비추적 경로 `models/task306_sparse_denoising_autoencoder/`에
저장됩니다.
