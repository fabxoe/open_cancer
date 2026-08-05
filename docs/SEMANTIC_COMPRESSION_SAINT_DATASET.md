# Parser-v4 의미 압축기와 SAINT 입력 계약

이 문서는 [계획 Issue #504](https://github.com/fabxoe/open_cancer/issues/504)의
공통 Track 0 구현을 설명합니다. 구현 작업은
[Task Issue #506](https://github.com/fabxoe/open_cancer/issues/506)에서 관리합니다.
이 작업 자체는 모델을 학습하거나 실험 점수를 만들지 않습니다.

## 목적

parser-v4 native 행렬은 사건의 의미를 보존하지만 약 3만 개의 희소
`gene × semantic-event` 열을 가집니다. 이 열 전체를 SAINT의 column attention에
직접 전달하지 않고, 각 열의 이름과 의미를 유지한 채 128·256·512열로 제한합니다.

이 구현은 PCA·SVD·오토인코더처럼 이름 없는 잠재벡터를 만들지 않습니다.
선택 결과의 각 열은 원본 feature 이름, semantic family, support와 원본 index를
그대로 갖습니다.

## 선택 범위

고정 core는 다음 두 그룹입니다.

- sample burden: `mutated_gene_count`, `total_variant_count`,
  `multi_variant_gene_count`, `missing_gene_count`
- parser-v4 sample semantic count: `sample__native_v3_*_token_count`

남은 슬롯에는 `gene__<GENE>__native_v3_<EVENT>_any` 형식의 열만 들어갑니다.
같은 캐시에 들어 있는 compatibility mutation/missing 열은 선택 대상이 아닙니다.
따라서 새 입력이 의도하지 않게 과거 compatibility 모델로 되돌아가지 않습니다.

## Fold-safe 규칙

각 canonical outer fold마다 다음을 독립적으로 수행합니다.

1. outer-train 행만 사용해 support와 prevalence를 계산합니다.
2. outer-train 내부 deterministic 3-fold에서 support 순위와 안정성을 계산합니다.
3. semantic core를 먼저 놓고 안정적인 gene-event 열로 슬롯을 채웁니다.
4. 같은 선택 index를 validation과 test에 transform-only로 적용합니다.

정답 라벨, validation 통계, test 통계와 Public LB는 선택에 사용하지 않습니다.
128열은 256열의 prefix이고, 256열은 512열의 prefix입니다. 같은 fold·seed·입력
schema에서는 feature 이름·순서 hash가 같아야 합니다.

## SAINT 입력

`FittedSemanticCompressor.build_saint_dataset()`은 선택된 희소 행렬을
`float32` dense 행렬로 바꾸며 다음 metadata를 함께 반환합니다.

- feature 이름과 semantic family
- binary event 열 index
- continuous count/burden 열 index
- dense materialization 예상 byte 수

기본 메모리 상한은 512 MiB입니다. 6,201행 × 512열 `float32`는 약 12.1 MiB로
충분히 작지만, 행이나 차원을 확대할 때 무심코 큰 dense 행렬을 만들지 못하도록
상한 검사를 둡니다.

## 실행 예시

다음 명령은 fold 0의 selector manifest만 생성합니다.

```bash
uv run python scripts/build_fold_safe_semantic_compression.py \
  --cache-dir data/processed/issue475_native_v3_analysis \
  --output-dir data/processed/issue506_semantic_compression_smoke \
  --folds 0
```

선택된 희소 train·validation·test 행렬도 저장하려면 `--write-matrices`를
추가합니다. `data/processed/`의 생성물은 Git에 커밋하지 않습니다.

공식 SAINT 실험은 별도 Experiment Issue를 발급하고, 이 selector의 fold별 JSON과
model config·checkpoint·OOF/test 확률을 함께 저장해야 합니다.

## 실제 캐시 smoke 결과

Issue #506 구현 검증에서는 EXP-479 분석 캐시의 6,201 × 39,467 혼합 행렬을
사용했습니다. canonical fold 0 outer-train에서 다음을 확인했습니다.

| 차원 | core | binary | continuous | compatibility 선택 | 중첩 선택 |
|---:|---:|---:|---:|---:|---|
| 128 | 11 | 117 | 11 | 0 | 통과 |
| 256 | 11 | 245 | 11 | 0 | 통과 |
| 512 | 11 | 501 | 11 | 0 | 통과 |

이 수치는 모델 성능이 아니라 입력 계약과 누출 방지 구현의 smoke 결과입니다.
