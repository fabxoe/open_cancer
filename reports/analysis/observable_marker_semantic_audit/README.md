# 고정 암종 표지 mutation-proxy 의미 감사

## 목적

Issue #299의 공식 모델 실험 전에 공개된 일반 암종 표지 유전자 목록이 실제
대회 4,384개 유전자 panel에 존재하는지, 생성 후보가 상수이거나 기존 유전자
피처와 정확히 같은지를 target 없이 확인했습니다.

이 분석은 모델을 학습하지 않았고 `SUBCLASS`를 읽지 않았습니다. Public LB,
test label, 암종별 결과도 사용하지 않았습니다.

## 동결 입력

- 지식 파일: `knowledge/fixed_observable_cancer_markers_v1.json`
- train: 6,201행
- test: 2,546행
- 후보: panel 5개 × 이진 요약 4개 = 20개
- 변환: `src/open_cancer/observable_marker_features.py`

## 가장 중요한 발견

캡처에 나온 유전자 중 `KRAS`, `NRAS`, `MSH6`는 실제 4,384개 대회 panel에
없습니다. 따라서 외부 목록을 그대로 사용하지 않고 다음 고정 교집합만 계산해야
합니다.

| panel | 외부 동결 목록 | 대회 panel 교집합 |
|---|---|---|
| lung | EGFR, KRAS, BRAF | EGFR, BRAF |
| breast | BRCA1, BRCA2, ERBB2, PIK3CA | 동일 |
| colorectal | KRAS, NRAS, BRAF, MLH1, MSH2, MSH6, PMS2 | BRAF, MLH1, MSH2, PMS2 |
| ovarian | BRCA1, BRCA2 | 동일 |
| bladder | FGFR3 | 동일 |

누락 유전자를 비슷한 유전자로 임의 대체하거나, 결과를 본 뒤 panel을 확장하지
않습니다. 원 목록과 교집합·누락 목록을 모두 재현 산출물에 저장합니다.

## 후보 QC

- `bladder_fgfr3_variant_proxy__multi_gene_mutated`는 단일 유전자 panel이므로
  정의상 항상 0입니다. 공식 후보에서 제거해야 합니다.
- `bladder_fgfr3_variant_proxy__any_mutated`는 기존
  `gene__FGFR3__mutated`와 완전히 같습니다. 의미 중복 필터에서 제거해야 합니다.
- 나머지 후보는 관련 유전자 블록의 단일 기존 열과 정확히 같지 않았습니다.
- 최종 공식 runner에서는 관련 블록만이 아니라 EXP-229 전체 base matrix와 다시
  byte-equivalence 검사를 수행합니다.

## target-independent 출현 수

| panel proxy | train any mutated | test any mutated | train any LoF | test any LoF | train multi-gene | test multi-gene |
|---|---:|---:|---:|---:|---:|---:|
| lung | 639 | 396 | 21 | 18 | 36 | 42 |
| breast | 985 | 534 | 68 | 44 | 116 | 100 |
| colorectal | 588 | 329 | 45 | 30 | 48 | 62 |
| ovarian | 293 | 189 | 59 | 38 | 29 | 40 |
| bladder | 74 | 78 | 10 | 8 | 0 | 0 |

test는 행 수가 더 적은데도 일부 표지 panel의 양성 수가 상대적으로 큽니다. 이는
성능 향상을 보장하는 신호가 아니라 train/test shift 가능성을 보여주는 QC
결과입니다. panel 구성이나 가중치를 이 분포에 맞춰 바꾸지 않습니다.

## 해석 한계

- ALK·ROS1·NTRK fusion, HER2 amplification, MSI/dMMR, germline status는 이
  입력으로 판정할 수 없습니다.
- `BRCA1 변이 proxy`는 유전성 BRCA 위험 또는 PARP 치료 적응증이 아닙니다.
- `MMR-gene 변이 proxy`는 MSI-H 판정이 아닙니다.
- 이 후보는 암종별 임상 진단 규칙이 아니라 모든 샘플에 동일하게 적용하는 작은
  mutation-pattern 요약입니다.

## 다음 행동

1. Task PR에서 상수·의미 중복 제거 계약과 테스트를 완료합니다.
2. 별도 Experiment Issue에서 EXP-229 설정을 고정하고 canonical 5-fold를 1회
   실행합니다.
3. 사전 채택 기준을 통과하지 못하면 이 panel을 Public 결과에 맞춰 반복
   수정하지 않고 archive합니다.

