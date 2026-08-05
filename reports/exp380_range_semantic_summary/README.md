# EXP-380 range stop·no-change 의미 요약

## 결론

EXP-369의 stop 표기 정규화와 기존 피처를 그대로 유지하면서, 구간·복합 치환
토큰에서 직접 해석할 수 있는 `range_stop`과 `range_no_change` 의미를 샘플별
고유 유전자 수와 존재 여부로 각각 요약해 4개 피처를 추가했다.

OOF Macro F1은 `0.4221880021`로 부모 EXP-369의 `0.4229885745`보다
`-0.0008005725` 낮았다. 반면 fold 표준편차는 `0.0098679649`에서
`0.0062025822`로 감소했고 Log Loss도 `1.8509613276`에서
`1.8463485241`로 개선됐다.

대회 주 지표인 Macro F1이 하락했으며, 네 피처는 모델을 단순화하지도 않는다.
따라서 **이 네 개의 sample-level 요약 표현**은 성능 피처로 채택하거나
리더보드에 제출하지 않고 `ARCHIVE`한다. 다만 이는 range parser, 개별 사건의
정규화, mutation-type 재분류 또는 다른 feature representation을 기각한 결과가
아니다. 구간 표기를 버리지 않고 안전하게 구조화할 수 있다는 구현·분포 증빙은
후속 parser 버전을 위해 보존한다.

## 실험 계약

- Issue/브랜치: #380 / `issue-380-exp-range-semantic-summary`
- 부모: EXP-369
- canonical stratified 5-fold, seed 42와 26개 클래스 순서 고정
- XGBoost·balanced sample weight·Macro-F1 checkpoint 정책 고정
- EXP-369의 stop 정규화, mutation type, hotspot, pathway 피처를 모두 유지
- 추가 피처는 다음 네 개뿐이다.
  - `sample__range_stop_gene_count`
  - `sample__range_stop_any`
  - `sample__range_no_change_gene_count`
  - `sample__range_no_change_any`
- count는 원시 token 수가 아니라 샘플별 고유 유전자 수다.
- `range_stop`: 구간 치환의 alternate 서열에 stop(`*`)이 포함된 사건
- `range_no_change`: 구간 치환의 reference와 alternate 서열이 같은 사건
- 일반 range replacement, 유전자별 range indicator, pathway LoF 확장은 제외
- SUBCLASS·test 분포·Public LB를 피처 정의에 사용하지 않음

## 피처 분포

| 피처 | train 합계 | train 비영(非零) 샘플 | train 최대 | test 합계 | test 비영 샘플 | test 최대 |
|---|---:|---:|---:|---:|---:|---:|
| range stop gene count | 62 | 56 | 3 | 11 | 11 | 1 |
| range stop any | 56 | 56 | 1 | 11 | 11 | 1 |
| range no-change gene count | 63 | 47 | 4 | 9 | 9 | 1 |
| range no-change any | 47 | 47 | 1 | 9 | 9 | 1 |

피처가 희소하고 train/test의 절대 발생량도 작다. 이 실험만으로 표기의 생물학적
중요성이 없다고 결론내릴 수는 없지만, 샘플 수준 4개 요약이 EXP-369의 결정
경계를 개선할 만큼 충분한 신호를 제공하지는 못했다.

## 결과

| 지표 | EXP-380 | EXP-369 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4221880021 | 0.4229885745 | -0.0008005725 |
| Fold 평균 | 0.4222193056 | 0.4232332489 | -0.0010139434 |
| Fold 표준편차 | 0.0062025822 | 0.0098679649 | -0.0036653827 |
| Accuracy | 0.4107402032 | 0.4125141106 | -0.0017739074 |
| Log Loss | 1.8463485241 | 1.8509613276 | -0.0046128035 |

fold Macro F1은 `0.4173773 / 0.4204568 / 0.4154077 / 0.4250923 /
0.4327624`이며 선택 iteration은 `122 / 151 / 240 / 161 / 247`이다.

클래스별 F1은 TGCT `+0.02011`, CESC `+0.01825`, PAAD `+0.01414`로
개선됐지만 PRAD `-0.02273`, DLBC `-0.01455`, LUAD `-0.01343`으로
하락했다. 소수 클래스를 포함한 개선 방향이 일관되지 않다.

부모 대비 OOF argmax는 6201행 중 647행, test argmax는 2546행 중 108행이
달라졌다. 네 피처가 실제 모델 결정에 사용됐다는 뜻이지만, 정답 없는 test의
변화 방향은 해석하거나 선택 근거로 사용하지 않는다.

## 재현성

- 소스 commit: `623cd06bf82f4f6186fd468c963f4305d48299fc`
- Config: `configs/exp380_range_semantic_summary.yaml`
- Runner: `scripts/run_exp380_range_semantic_summary.py`
- 역사적 피처 구현: `src/open_cancer/range_semantic_summary_features.py`
  (병합 당시 최신 `range_semantic_features.py`의 fold-safe gene indicator와
  이름 충돌을 피하기 위해 별도 legacy 모듈로 격리했으며 계산식은 변경하지 않음)
- Metrics: `reports/exp380_range_semantic_summary/metrics.json`
- OOF: `oof/exp380_range_semantic_summary.csv`
- test 확률: `preds/exp380_range_semantic_summary_test_proba.csv`
- submission: `submissions/exp380_range_semantic_summary.csv`
- submission SHA-256:
  `d985514f3ddd620b406e8acfe980d5a97dba14b82cd717a6fe6d00f7fcb776c3`
- 재현 상태: `INFERENCE_VERIFIED`
- checkpoint 재추론: submission SHA-256 byte-level 일치, test 라벨 100%,
  확률 최대 차이 `1.48e-7`

## 판단과 다음 행동

EXP-380의 **정확히 이 네 개 피처 조합**은 `ARCHIVE`한다. range 의미 파서와
테스트는 공용 기반으로 유지한다. 이 결과 하나로 sample·gene·pathway 표현 전체를
닫지 않으며, 같은 네 값을 단순히 더 세분화하는 기계적 확장만 보류한다.

후속 작업은 다음 세 층을 별도 버전과 독립 ablation으로 관리한다.

1. **Notation normalization**: `*`·`X`·`Ter`, 대소문자, 공백처럼 동일 의미의
   표기만 canonical token으로 통일한다.
2. **Semantic parser**: multi-letter frameshift, range stop, no-change, indel과
   ambiguous token을 raw 손실 없이 구조화한다.
3. **Feature representation**: 구조화된 의미를 mutation-type 교정, sample 요약,
   gene indicator 또는 pathway 집계 중 어떤 형태로 모델에 전달할지 각각 검증한다.

EXP-380은 3번의 첫 번째 좁은 표현 실험일 뿐이다. 다음 parser 실험은
`SDEL133fs` 같은 현재 오분류 표기를 실제 mutation-type 경로에서 바로잡는 단독
ablation으로 설계하고, 다른 요약 피처를 동시에 섞지 않는다.
