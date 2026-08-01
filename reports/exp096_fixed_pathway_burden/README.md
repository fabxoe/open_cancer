# EXP-096 fixed pathway burden 단독 검증

## 결론

동결된 EXP-094 Feature Spec v1에 문헌으로 고정한 10개 canonical cancer
pathway별 `mutated_gene_count`와 `lof_gene_count` 20개를 추가했습니다. 공식 공용
5-fold OOF Macro F1은 **0.4181153080**으로 EXP-094보다 `+0.0012287341`
높아졌습니다. Fold 표준편차 악화는 `+0.0016078656`으로 사전 한도 `0.002`
미만이고 Log Loss는 `-0.0030031204` 개선되어 **v2-performance 후보로
채택합니다**.

## gene membership과 규정 준수

팀 리더는 주최측으로부터 공개 문헌의 고정 pathway gene membership을 사용하고,
환자별 값은 대회 CSV에서만 계산하는 방식이 허용된다는 답변을 받았습니다. 허용
기록은 [Issue #96 댓글](https://github.com/fabxoe/open_cancer/issues/96#issuecomment-5151028180)에
고정했습니다.

Sanchez-Vega et al., Cell 2018의 10개 canonical pathway를 사용하되 사람이 임의로
대표 유전자를 고르지 않았습니다. PathwayMapper 고정 커밋의 10개 template에서
`NODE_TYPE=GENE`인 모든 고유 node를 추출하고, 실행 시 대회 4,384개 gene column과
교집합을 취했습니다.

- 원 논문: <https://doi.org/10.1016/j.cell.2018.03.035>
- PathwayMapper commit: `7d29965de6ac8d0c6ec18c383f6dff8a48d562e7`
- 원본 SHA-256: `a625675d03fa314eb27f3ab731524de13621a35aecd8edb7c67878f2d89ae07a`
- 정제 knowledge SHA-256: `fa263a35bf0d7614be373bcdb6b69399e618513359eb7e6c5f334b0e9244132f`
- 전체 source node와 실제 패널 교집합:
  `reports/exp096_fixed_pathway_burden/pathway_membership.json`

SUBCLASS, train 빈도, validation, test 또는 Public LB로 pathway나 유전자를
선택하지 않았습니다. 외부 환자 데이터·환자별 값·임베딩·연속 weight도 사용하지
않았습니다.

## 피처 정의

다음 10개 pathway마다 두 값을 계산했습니다.

- Cell cycle, Hippo, MYC, NOTCH, NRF2
- PI3K, RTK–RAS, TGF-β, TP53, WNT
- `mutated_gene_count`: 해당 pathway에서 하나 이상의 변이가 있는 유전자 수
- `lof_gene_count`: nonsense 또는 frameshift가 하나 이상 있는 유전자 수

`complex` token은 근거 없이 LoF로 취급하지 않았습니다. boolean, token count,
hotspot count와 functional-role 피처는 이번 단독 ablation에서 제외했습니다.

## 결과

| 항목 | EXP-096 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4181153080 | 0.4168865739 | +0.0012287341 |
| fold 평균 | 0.4180414254 | 0.4162108011 | +0.0018306243 |
| fold 표준편차 | 0.0094921177 | 0.0078842521 | +0.0016078656 |
| Accuracy | 0.4078374456 | 0.4071923883 | +0.0006450572 |
| Log Loss | 1.8369342089 | 1.8399373293 | -0.0030031204 |

| Fold | Macro F1 | Best iteration |
|---:|---:|---:|
| 0 | 0.4086499982 | 182 |
| 1 | 0.4181643608 | 207 |
| 2 | 0.4140262094 | 287 |
| 3 | 0.4133268480 | 220 |
| 4 | 0.4360397106 | 229 |

26개 클래스 중 13개가 개선되고 13개가 하락했습니다. 큰 개선은 PAAD
`+0.0341`, ACC `+0.0278`, CESC `+0.0272`, LAML `+0.0178`, THYM
`+0.0157`였고, 큰 하락은 LIHC `-0.0301`, BLCA `-0.0287`, TGCT
`-0.0243`, UCEC `-0.0136`였습니다. 따라서 전체 성능 후보로 채택하되 후속
union·blend에서 이 클래스들의 회복 여부를 확인해야 합니다.

## 다양성 관찰

| 비교 항목 | 값 |
|---|---:|
| EXP-094 OOF 예측 라벨 일치율 | 0.8948556684 |
| EXP-094 정답/오답 상태 일치율 | 0.9554910498 |
| EXP-094 전체 OOF 확률 상관 | 0.9888422031 |
| EXP-106 전체 OOF 확률 상관 | 0.9867741886 |
| EXP-107 전체 OOF 확률 상관 | 0.9760170866 |
| EXP-109 전체 OOF 확률 상관 | 0.9795107804 |
| EXP-110 전체 OOF 확률 상관 | 0.9466932242 |

EXP-094와 상당히 비슷하지만 예측 라벨 약 10.51%가 달라졌고 성능 자체도
개선됐습니다. 독립적인 diversity 모델보다는 **v2-performance의 핵심 C family**로
우선 사용하고, EXP-110처럼 더 독립적인 약한 모델과의 결합은 별도 OOF 감사에서
판단합니다.

## 재현성과 산출물

- Issue: [#96](https://github.com/fabxoe/open_cancer/issues/96)
- 실행 소스 commit: `296c39fe9259fd4ee93bd8158aeaecec0c891545`
- resolved config: `reproducibility/exp096_fixed_pathway_burden/config.resolved.yaml`
- metrics: `reports/exp096_fixed_pathway_burden/metrics.json`
- membership manifest: `reports/exp096_fixed_pathway_burden/pathway_membership.json`
- submission: `submissions/exp096_fixed_pathway_burden.csv`
- submission SHA-256: `0d6bdaacec8c9853bc44c3d00fa6eec04f4e0b5b2fd583971e4057a2beefaf0d`
- 재현 상태: `INFERENCE_VERIFIED`
- 제출 재생성: byte-level SHA-256 일치
- test 라벨 일치율: 100%
- test 확률 최대 절대 오차: `2.976837154555767e-08`
- Public LB: 미제출

## 다음 결정

- fixed pathway burden 20개를 Feature Spec v2-performance 후보로 채택합니다.
- functional-role burden은 이번 결과에 섞지 않았으며 별도 Issue가 있어야 합니다.
- A/B/C 단독 실험 결과를 모아 v2-performance와 v2-diversity를 동결하는 포트폴리오
  감사 단계로 이동합니다.
