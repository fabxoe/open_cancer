# Parser-v4 벡터화 희소 scan·compiled cache

Issue [#607](https://github.com/fabxoe/open_cancer/issues/607)의 비모델 성능
최적화 결과다. parser 의미, 피처 이름·차원·순서·값과 모델 점수는 바꾸지
않는다.

## 변경

- 6,201×4,384 dense 셀을 Python 이중 루프로 순회하지 않고 256개 유전자
  블록별 NumPy/Pandas mask로 non-WT 좌표만 추출한다.
- 실제 parser 호출은 발견된 non-WT 셀에만 수행한다.
- canonical token·cell LRU를 각각 262,144개로 확대했다.
- cache lineage에 notation normalizer, semantic router, canonical identity,
  feature family version, 유전자 컬럼 순서 SHA-256을 포함한다.
- semantic count, patient semantic vector, native-v3 consumer가 같은 scan/cache
  경로를 사용한다.
- raw token과 unresolved provenance는 그대로 보존한다.

## 전체 데이터 검증

대상:

- train 6,201행, test 2,546행
- 유전자 4,384개
- train non-WT 셀 218,893개
- legacy patient-vector 기준 commit: EXP-614 소스 `698eb32`

| 검사 | 결과 |
|---|---|
| legacy/new non-WT 좌표·값·순서 | 완전 동일 |
| semantic-count legacy/new/warm 행렬 | 완전 동일 |
| patient-vector train legacy/new | sparse 행렬·SHA-256 동일 |
| patient-vector test legacy/new | sparse 행렬·SHA-256 동일 |

Patient vector SHA-256:

- train: `7c9622b72a62ab5dc8381fdcf9c5b07813d6eadd865c3c5a9c88e3ada75a8fd0`
- test: `46a4fd9d8f16c17f566ea6eb123c25f5cbd32b67e9ad1e47ef00f04912aceea6`

## 속도

| 경로 | legacy/cold | new cold | new warm |
|---|---:|---:|---:|
| non-WT scan(train) | 3.849초 | 1.692초 | - |
| parser-v4 semantic count(train) | 9.690초 | 7.288초 | 2.065초 |
| patient semantic vector(train) | - | 7.598초 | 2.904초 |
| patient semantic vector(test) | - | - | 6.849초 |

scan 단독 속도는 2.28배 개선됐다. warm semantic-count는 legacy 전체 대비
약 4.69배 빠르다. 이 최적화는 반복 parser 비용을 줄이지만 XGBoost·Optuna
학습 시간 자체를 줄이는 기능은 아니다.

## 캐시 감사

warm run 종료 시:

- token cache: hit 164,178 / miss 189,889 / current 189,889
- cell cache: hit 432,185 / miss 204,531 / current 204,531
- 최대 크기: 각 262,144
- parser contract: `normalizer=4.0.0|router=4.0.0|identity=1.0.0`

원본 수치는 [`benchmark.json`](benchmark.json)에 보존한다.

## 재실행

```bash
uv run python scripts/benchmark_parser_v4_sparse_cache.py \
  --legacy-patient-cache-dir <legacy-cache-dir> \
  --output reports/analysis/parser_v4_sparse_cache/benchmark.json
```

이 작업은 일반 Task이며 EXP-ID·OOF·submission·리더보드 결과를 만들지 않는다.
