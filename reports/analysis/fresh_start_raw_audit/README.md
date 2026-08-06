# Issue #658 raw-first train/test audit

기존 모델 피처·OOF·Public 결과를 사용하지 않고 원본 변이 문자열에서 바로 계산한
분포 감사다. `SUBCLASS`는 읽지 않았고 환자별 값도 저장하지 않았다.

## 결과

- 입력 검증: train 6,201행, test 2,546행, 동일 순서의 유전자 4,384개
- 10개 raw 요약만 사용한 train/test domain 5-fold OOF AUC: **0.7277526507**
- fold AUC: 0.7214332190, 0.7199739089, 0.7209376386, 0.7382628810,
  0.7423093986

| raw 요약 | train 평균 | test 평균 | train 비영 비율 | test 비영 비율 | 단독 direction-free AUC |
|---|---:|---:|---:|---:|---:|
| multi-token gene count | 3.5520 | 24.8146 | 33.46% | 60.21% | 0.6919 |
| `X`-ending stop token count | 0.0000 | 5.7007 | 0.00% | 34.60% | 0.6730 |
| total token count | 41.1488 | 132.5656 | 98.48% | 98.78% | 0.6636 |
| non-WT gene count | 35.2996 | 78.1343 | 98.48% | 98.78% | 0.6368 |
| `*`-ending token count | 2.1655 | 0.7793 | 52.86% | 26.94% | 0.6336 |
| frameshift token count | 1.5988 | 10.1756 | 53.44% | 65.00% | 0.6206 |

정확한 전체 소수점과 quantile은 [`summary.json`](summary.json)에 있다.

## 해석

모델링 전에 알 수 있었던 가장 큰 사실은 단순 burden 차이뿐 아니라 표기 체계
차이다. `*` 종결 표기는 train에, `X` 종결 표기는 test에 치우쳐 있다. 이를 서로
다른 mutation family로 읽는 parser는 암종 신호가 아니라 데이터셋 출처를 학습한다.
다중-token·frameshift·range 표기도 함께 이동하므로 raw token multiplicity를 직접
강한 피처로 쓰는 설계는 위험하다.

이 결과는 QC이며 test 분포를 보고 피처를 삭제하거나 sample weight를 정하는 데
사용하지 않는다. parser의 의미 규칙은 notation-invariant fixture로 고정하고,
모델 피처의 채택 여부는 test를 보지 않는 canonical train 5-fold에서 판정한다.

## 재실행

```bash
uv run python scripts/run_fresh_start_raw_audit.py
```
