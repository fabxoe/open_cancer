# EXP-093 변이 유형·위치·주요 hotspot 조합 검증

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-093 / #93 |
| 목적 | 서로 다른 정보를 담는 변이 유형·최대 잔기 위치·고정 hotspot을 한 모델에서 함께 검증 |
| 핵심 입력 | EXP-005 mutation-type + EXP-069 max residue-position + EXP-085 hotspot 34개 |
| 모델 | XGBoost, 기존 설정 유지 |
| Local OOF Macro F1 | `0.4157606623` |
| Public LB | 미제출 |
| 재현 상태 | `INFERENCE_VERIFIED` |
| 판단 | 평균 성능은 개선됐지만 fold 변동성 기준 실패로 조합 동결 보류 |

## 원본 데이터와 입력

한 환자의 4,384개 유전자 셀에 기록된 변이 문자열에서 세 종류의 정보를 만듭니다.

1. **변이 유형**은 각 유전자에 missense, synonymous, nonsense, frameshift,
   complex 변이가 있는지를 나타냅니다.
2. **최대 잔기 위치**는 각 유전자 셀에서 읽은 단백질 잔기 숫자 중 가장 큰 값을
   사용합니다. 위치를 읽을 수 없는 셀은 `0`이며 complex token의 위치도 포함합니다.
3. **고정 hotspot**은 문헌으로 미리 고정한 34개 `(유전자, 잔기 위치, 기준
   아미노산)` 조합과 정확히 일치하는지를 나타냅니다.

원본 CSV는 수정하지 않았고 공용 split도 변경하지 않았습니다.

## 왜 세 피처를 합쳤나

변이 유형은 **어떤 변화인지**, 잔기 위치는 **단백질의 어디에서 일어났는지**,
hotspot은 **알려진 중요 위치와 정확히 일치하는지**를 표현합니다. 세 피처가 서로
다른 정보를 제공하면 단독 family보다 암종 구분이 좋아질 수 있다는 가설입니다.

Hotspot 목록은 validation이나 test 결과를 보고 바꾸지 않았습니다. 추가 15개
hotspot의 최소 5회 관측 조건도 각 fold의 fold-train에서만 검사했습니다.

## 검증 방법

- 공용 `stratified_5fold_seed42.csv` 전체 5-fold
- 전체 OOF Macro F1을 주 지표로 사용
- 기존 XGBoost 구조·seed·class-balanced sample weight 유지
- 비교 부모: EXP-069, EXP-085
- 사전 채택 기준:
  - 최고 부모보다 OOF Macro F1 `+0.001` 이상
  - fold 표준편차 악화 `0.002` 미만
  - 소수 클래스 F1, Accuracy, Log Loss의 뚜렷한 붕괴 없음
  - `INFERENCE_VERIFIED` 통과

## 실제 결과

| 실험 | OOF Macro F1 | Fold 표준편차 | Log Loss |
|---|---:|---:|---:|
| EXP-069 | 0.4131007993 | 0.0082058569 | 1.8525067568 |
| EXP-085 | 0.4125795545 | 0.0091265687 | 1.8315716982 |
| **EXP-093** | **0.4157606623** | **0.0126466581** | **1.8402239084** |
| EXP-075 참고 | 0.4157910775 | 0.0064700181 | 1.8446407531 |

Fold Macro F1은 다음과 같습니다.

```text
0.4094564310, 0.4312411436, 0.3986561217, 0.4090170143, 0.4292709896
```

- EXP-069 대비 OOF: `+0.0026598630`
- EXP-085 대비 OOF: `+0.0031811077`
- 현재 최고 EXP-075 대비 OOF: `-0.0000304152`
- EXP-085 대비 fold 표준편차: `+0.0035200894`
- EXP-069 대비 fold 표준편차: `+0.0044408013`

EXP-085 대비 ACC, PAAD, BLCA, GBMLGG 등이 개선됐지만 KIRC, UCEC, SKCM,
LIHC 등은 하락했습니다. 클래스별 변화가 한 방향으로 일관되지는 않았습니다.

## 해석과 판단

세 피처를 함께 사용했을 때 평균 OOF가 두 단일 부모보다 높아, 변이 유형·숫자
위치·hotspot이 완전히 중복된 정보만 담는 것은 아니라는 근거를 얻었습니다.

그러나 fold 표준편차 악화가 사전 허용치 `0.002`를 넘었습니다. 특히 fold 2는
`0.3986561217`, fold 1은 `0.4312411436`으로 차이가 큽니다. 따라서 이번 결과를
“안정적으로 개선된 최종 Feature Spec”으로 확정하지 않고 **조합 동결을
보류**합니다. Public LB에는 제출하지 않았습니다.

## 다음 실험 후보

새로운 도메인 정보를 추가하는 독립 family로, 고정 pan-cancer pathway별
`mutated_gene_count`, `lof_gene_count`, `hotspot_gene_count`를 검증합니다.
유전자 그룹과 변이 영향의 정의는 외부 근거·버전·라이선스·해시를 기록하고,
SUBCLASS나 test 분포를 사용해 선택하지 않습니다.

## 재현과 관련 파일

- Config: `configs/exp093_mutation_position_hotspot.yaml`
- Resolved config: `reproducibility/exp093_mutation_position_hotspot/config.resolved.yaml`
- Metrics: `reports/exp093_mutation_position_hotspot/metrics.json`
- Submission candidate: `submissions/exp093_mutation_position_hotspot.csv`
- Submission SHA-256: `de3fceb0f8c9d1a0ab6e3d566c7803bd50e95209d662d4a5265f49b425ad9635`
- Source commit: `62254643cd811ec0249d15456a1ec9b7fe6c328f`
- Reproduction status: `INFERENCE_VERIFIED`
- 재추론 결과: test 라벨 100% 일치, 확률 최대 절대 차이
  `2.9753112751329525e-08`, 제출 SHA-256 일치
