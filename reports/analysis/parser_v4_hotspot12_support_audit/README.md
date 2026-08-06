# Parser-v4 Hotspot-12 fold support 감사

> Task Issue: [#632](https://github.com/fabxoe/open_cancer/issues/632)
>
> 이 문서는 모델 점수를 만들지 않은 target-independent support audit입니다.

## 질문

Parser v4가 확정한 missense residue 사건에서, 다음 사전 고정 규칙을 outer-train만으로 안정적으로 학습할 수 있는가?

- 유전자별 고유 `patient × residue position` 사건 5개 이상
- 폭 12 residue
- 대표 창이 전체 eligible 사건의 40% 이상 포함
- 유전자당 대표 창 1개

## 데이터와 누수 방지

- train: 6,201행, 유전자 4,384개
- split: canonical stratified 5-fold, seed 42
- 각 fold의 outer-train 4,960~4,961행만 창 선택에 사용
- target, validation, test 분포와 Public LB 미사용
- isoform·중복 token의 빈도 팽창을 막기 위해 patient-gene-position 단위 중복 제거
- unresolved·not-applicable·position-ineligible 사건 제외

정확한 입력·split·feature hash와 fold별 창은 [`audit.json`](audit.json)에 기록했습니다.

## 결과

| fold | 후보 유전자 | Hotspot-12 통과 유전자 | eligible missense support |
|---:|---:|---:|---:|
| 0 | 3,974 | 241 | 128,320 |
| 1 | 3,941 | 228 | 126,152 |
| 2 | 3,975 | 240 | 126,611 |
| 3 | 4,000 | 223 | 133,777 |
| 4 | 3,967 | 234 | 129,180 |

- fold pairwise selected-gene Jaccard 평균: `0.3236954807`
- 5개 fold 모두에서 통과한 유전자: 35개
- 5개 fold 모두에서 같은 정확한 창까지 유지된 유전자: 16개

## 해석

규칙을 적용할 support는 충분합니다. 매 fold에서 223~241개 유전자가 통과하므로 빈 feature family가 되지 않습니다.

다만 전체 선택 집합의 Jaccard 0.324는 높은 안정성이 아닙니다. 이 결과를 “고정된 생물학적 hotspot catalog가 발견됐다”고 해석하면 안 됩니다. 표본이 달라지면 support 경계 근처의 희귀 유전자가 드나드는 **fold-local 통계 피처**입니다.

35개 유전자는 모든 fold에서 재선택됐고 16개는 창 경계도 동일하므로 반복 가능한 핵심 신호도 일부 존재합니다. 공식 실험에서는 이 16개만 사후 선별하지 않고, 사전에 고정한 규칙을 각 outer-train에 그대로 적용합니다. 안정 유전자 목록을 보고 선택 범위를 바꾸면 같은 OOF를 사용한 간접 최적화가 되기 때문입니다.

## EXP-563과의 차이

EXP-563은 50-aa bin 분포의 평균 HHI·entropy 등 연속형 4개를 사용했습니다. 이번 family는 각 fold에서 학습된 폭 12 창에 환자 사건이 들어오는지를 유전자별 indicator와 3개 sample 요약으로 표현합니다.

따라서 EXP-563의 성능 하락은 Hotspot-12 기각 근거가 아닙니다. 반대로 이번 support 감사만으로 성능 향상을 주장할 수도 없습니다. 공식 canonical 5-fold가 필요합니다.

## 판단

`PROCEED_WITH_CAUTION`

- support gate 통과
- fold-safe transformer 구현 진행
- 별도 Experiment Issue에서 EXP-527 대비 단일변수 공식 비교
- Public 결과를 보고 5/40%/12 규칙을 변경하지 않음

