# Vera EXP-094 후속 검토

## 목적

EXP-094로 Feature Spec v1을 동결한 뒤, 기존 모델 다양화·stacking 로드맵을
Vera의 후속 권고와 비교했습니다. 원 대화는
[Vera Health](https://www.verahealth.ai/search/22adc84e-7e57-4766-945f-a21fa795db24)에
있으며, 이 문서는 답변을 그대로 복사하지 않고 프로젝트에 필요한 결정만
요약합니다.

## 수집 방법

전체 DOM snapshot은 사용하지 않았습니다. 실제 스크롤 컨테이너의 60.03%부터
99.999%까지 viewport 높이 1,402px에서 최대 980px씩 이동해 약 30%가 겹치는
41개 프레임을 임시 디스크에 저장했습니다. 프레임 간 최대 이동량이 viewport보다
작아 60~100% 구간에 빈 화면 영역이 없음을 manifest로 확인했습니다.

EXP-094 결과를 Vera에 전달한 뒤 새 답변은 하단부터 질문 경계까지 7개 겹침
프레임으로 별도 저장했습니다. 임시 원본은 저장소에 커밋하지 않습니다.

## 일치한 판단

- EXP-094는 F1, fold 안정성, log loss와 재현성을 함께 개선해 최종 후보 자격이
  있습니다.
- Feature Spec v1은 다시 열지 않고 동일 피처·fold로 모델 다양화를 먼저
  확보합니다.
- 실행 순서는 희소 선형 모델, LightGBM, 필요 시 CatBoost가 안전합니다.
- calibration과 class-wise threshold는 최종 후보 전까지 보류합니다.
- OOF 또는 Public LB를 보며 가중치와 피처를 반복 수정하지 않습니다.
- 최종 후보는 EXP-094 단일 모델과 검증된 ensemble/stack 최대 2개로 제한합니다.

## 강화한 기준

| 항목 | 기존 PR #99 초안 | 후속 확정 |
|---|---:|---:|
| base 모델 품질 하한 | EXP-094 대비 -0.020 | EXP-094 대비 -0.004 |
| 오류 상관 gate | 0.95 미만 | 0.92 이하 또는 라벨 불일치 10% 이상 |
| log loss gate | 명백한 악화 없음 | 최선 단일 대비 +0.01 미만 |
| 새 base 추가 중단 | 미정 | stack +0.001 미만이며 저빈도 클래스도 미개선 |
| 최종 stack 채택 | 최고 단일 대비 +0.002 | 최고 단일 또는 고정 blend 대비 +0.002 |

## Codex가 더 엄격하게 유지한 부분

Base 모델의 OOF를 모아 meta learner를 한 번 학습하면 test 예측은 만들 수 있지만,
그 meta learner의 학습 점수를 stack OOF로 사용할 수는 없습니다. 최종 로드맵은
meta learner도 canonical fold 안에서 다시 cross-fitting해 각 행을 보지 않은
meta 모델의 예측으로 stack OOF를 만듭니다.

또한 EXP-094 구성요소 제거 ablation은 해석에는 도움이 되지만 Feature Spec v1을
다시 여는 선택 편향 위험이 있습니다. 현재는 모델 다양화를 지연시키지 않고,
필요할 때만 `explore` 진단으로 분리합니다.

## B-1·C-1 결정

- B-1 functional spectrum은 모델 다양화 이후 예산이 남으면 v2 단일 ablation
  1회만 허용합니다. `+0.001` 미만 또는 저빈도 클래스 악화 시 중단합니다.
- C-1 fixed pathway burden은 출처·버전·라이선스·해시와 규정 허용성이 먼저
  확인돼야 합니다. `+0.002` 이상이 아니면 문서화·규정 비용을 감수하지 않습니다.
- 두 결과 모두 Feature Spec v1을 수정하지 않으며, 채택되면 v2로 별도 관리합니다.

## 저장소 검증 기준 A/B/C 매핑

Vera가 제공한 표는 당시 공유된 설명을 바탕으로 한 추론이므로, 아래 표는 실제
History·config·보고서로 보정한 저장소 기준 해석입니다.

- **A — driver/hotspot 패턴:** gene×mutation type·residue position·고정
  hotspot·고정 co-mutation 관계처럼 유전자 사건을 직접 구분합니다.
- **B — mutational process/spectrum:** 샘플별 burden, 변이유형 count·ratio와
  분포를 요약합니다.
- **C — tissue/function group:** 사전에 고정한 기능·driver·pathway·조직 관련
  유전자군을 그룹 단위로 집계합니다. 외부 문헌을 사용했다는 사실만으로 C가
  되지는 않습니다.

`부분`은 해당 축을 직접 최적화하지 않았지만 부모 피처나 집계값에 일부 포함됐다는
뜻입니다. Blend는 새로운 피처 축을 만들지 않으므로 부모 축을 상속합니다.

| EXP | 핵심 변경 | A | B | C | 저장소 기준 해석 |
|---|---|---|---|---|---|
| EXP-003 | mutation presence | 중 | 낮음 | 없음 | 유전자 사건 유무만 사용 |
| EXP-005 | gene×mutation-type 희소 피처 | 높음 | 부분 | 없음 | 현재 A축의 기본 코어 |
| EXP-012 | COSMIC 보호 유전자 분석 | 낮음 | 낮음 | 높음(분석) | C 개념을 분석했지만 모델 학습은 없음 |
| EXP-021 | COSMIC 가중 burden | 중 | 중 | 높음 | 고정 기능 유전자군 집계를 실제 모델로 시험한 초기 C 실험 |
| EXP-026 | presence + mutated-gene count | 중 | 높음 | 없음 | 샘플 변이량 proxy를 직접 추가 |
| EXP-029 | 변이유형 ratio·log burden | 높음 | 높음 | 없음 | B 확장, OOF 하락으로 현 구성 기각 |
| EXP-030 | notation 희소 피처·샘플 변이 수 | 높음 | 중 | 없음 | 정확 사건 표현과 burden을 함께 사용 |
| EXP-033 | EXP-005 + log burden 3종 | 높음 | 높음 | 없음 | B의 제한된 log 집계가 소폭 개선 |
| EXP-031 | 고정 hotspot 34개 | 매우 높음 | 부분 | 없음 | 문헌 목록이지만 그룹 집계는 아니므로 A |
| EXP-043 | 샘플 변이분포 28종 | 높음 | 높음 | 없음 | B 대규모 확장, OOF 하락 |
| EXP-045 | 분포 피처 nested selection | 높음 | 높음 | 없음 | B 선택을 시도했지만 기준 모델 미달 |
| EXP-047 | 최소 residue position | 매우 높음 | 부분 | 없음 | 위치 기반 A 강화 |
| EXP-050 | 반복 선택 분포 피처 2종 | 높음 | 높음 | 없음 | 제한된 B 재검증, 미채택 |
| EXP-052 | 고정 co-mutation pair 3개 | 높음 | 부분 | 낮음 | 문헌 관계를 사용하지만 tissue/function 그룹 집계는 아님 |
| EXP-058 | co-mutation pair 2개 ablation | 높음 | 부분 | 낮음 | EXP-052 관계 축 축소 |
| EXP-063 | residue observed indicator | 높음 | 부분 | 없음 | presence와 완전히 같은 중복 열로 확인; 결측 분리 아님 |
| EXP-065 | complex 위치 제외 | 매우 높음 | 부분 | 없음 | A축 파싱 robustness 검증 |
| EXP-067 | residue coarse bin | 매우 높음 | 부분 | 없음 | 위치 일반화 방식 검증 |
| EXP-069 | maximum residue position | 매우 높음 | 부분 | 없음 | Feature Spec v1의 위치 피처 |
| EXP-075 | EXP-067·069 확률 blend | 매우 높음(상속) | 부분(상속) | 없음 | 새 피처가 아닌 두 A계열 모델 앙상블 |
| EXP-078 | max position + indicator | 매우 높음 | 부분 | 없음 | 중복 indicator로 하락하여 기각 |
| EXP-085 | clean fixed hotspot 34개 | 매우 높음 | 부분 | 없음 | 재현 가능한 A hotspot 복구 |
| EXP-093 | mutation type + position + hotspot | 매우 높음 | 부분 | 없음 | A family 조합, 동결 기준 일부 미달 |
| EXP-094 | Feature Spec v1 조합 | 매우 높음 | 중 | 없음 | A 코어와 채택된 log burden을 동결한 현재 기준 |

### 매핑에서 얻은 결론

1. 성능 상승의 주축은 A이며 EXP-094에서 동결됐습니다.
2. B는 여러 형태로 충분히 시도했지만, 현재 살아남은 것은 제한된 log burden입니다.
3. C는 완전 미착수는 아닙니다. EXP-012가 분석했고 EXP-021이 COSMIC 고정 그룹
   burden을 시험했지만 현재 기준보다 크게 낮았습니다.
4. pathway·hallmark와 PPI 요약은 아직 실행하지 않았습니다.
5. 문헌 기반 hotspot·pair는 외부 지식을 사용해도 사건·관계 피처이므로 주축을
   A로 분류합니다.

## 확정 실행 순서

1. 공통 runner와 feature/fold/class/probability assert 완성
2. 희소 선형 모델 공식 5-fold
3. LightGBM 공식 5-fold
4. 다양성·확률 품질 감사
5. 필요할 때만 CatBoost 공식 5-fold
6. 사전 고정 단순 blend
7. gate 통과 시 meta-level cross-fitted stacking 1개
8. 최종 후보 최대 2개를 다른 팀원이 `TRAINING_VERIFIED`
9. 예산이 남을 때만 B-1, 이후 규정 확인된 C-1을 v2로 평가
