# EXP-653 isolated MMR gene (MLH1/MSH2/PMS2) proxy on EXP-527

## 결론

EXP-527(class-cosine leave-one-out XGBoost)을 고정 부모로 두고, EXP-302에서
KRAS/NRAS/BRAF와 한 panel로 묶여 통째로 기각됐던 MMR 유전자
(MLH1/MSH2/MSH6/PMS2) observable marker proxy를 격리해 단독으로 추가했다.
4,384개 실제 패널에는 MSH6가 없어 MLH1/MSH2/PMS2 3개만 실제 사용됐다(전체
train 기준 any_mutated 183명, any_lof 37명 양성).

OOF Macro F1은 `0.4480393463`로 부모보다 `+0.0011670756` 개선돼 채택
gate(`≥0.001`)를 근소하게 통과했고, Log Loss는 `-0.1934038401`로 크게
개선됐다. 그러나 **LGG `-0.1304`, KIRC `-0.1071`가 사전 고정 `-0.05` 붕괴
기준을 크게 위반**했다. 이 저장소에서 KIPAN/KIRC·GBMLGG/LGG 계보 혼동은
관련 없어 보이는 feature 추가에서도 반복적으로 재현된 실패 축이다
(EXP-639 LGG `-0.1123`/KIRC `-0.0512`, EXP-645 LGG `-0.1235`/KIRC `-0.0550`
등). Macro F1 gate 통과 여부와 무관하게 클래스 붕괴 기준에 따라
**`ARCHIVE`**한다.

## 버그 수정 이력

최초 실행(source commit `c7eaf87`)은 semantic-equivalence 검사를 이미
parent와 병합된 행렬에 대해 parent 자신을 reference로 호출하는 구현 버그로
parent의 feature 대부분(약 89개 중 다수)이 자기 자신과 중복 판정돼
삭제됐다. 그 결과(OOF `0.4181`, EXP-527 대비 `-0.029`, CESC·PAAD·SKCM 등
MMR과 무관한 클래스까지 광범위 붕괴)는 History에 기록하지 않고 산출물을
삭제했다. 수정(source commit `7157700`)은 병합 전 MMR 후보 4개 열만 별도로
검사하도록 바꿨고, 단위 테스트로 진짜 중복만 제거됨을 확인했다. 이 문서의
결과는 수정된 버전의 재실행이다.

## 실험 계약

- Issue/브랜치: #653 / `issue-653-mmr-gene-proxy-exp527`
- 부모: EXP-527
- canonical stratified 5-fold, seed 42, 26개 클래스 순서 고정
- 부모의 parser·isoform mask·class-cosine·XGBoost 설정 고정
- 유일한 변경: `knowledge/mmr_gene_proxy_v1.json`(MLH1/MSH2/MSH6/PMS2 단일
  panel)을 사용한 stateless observable marker proxy 4개
  (`any_mutated`, `any_nonsynonymous`, `any_lof`, `multi_gene_mutated`) 추가
- fold-safe semantic equivalence 검사에서 중복 열 0개(4개 전부 생존,
  fold별 feature 수 88/89 → 92/93으로 정확히 +4)
- SUBCLASS·test 분포·Public LB는 panel 정의에 사용하지 않음

## 결과

| 지표 | EXP-653 | EXP-527 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4480393463 | 0.4468722707 | +0.0011670756 |
| Fold 평균 | 0.4472114039 | 0.4469900880 | +0.0002213159 |
| Fold 표준편차 | 0.0060823323 | 0.0063793185 | -0.0002969862 |
| Accuracy | 0.4318658281 | 0.4339622642 | -0.0020964361 |
| Log Loss | 1.8340848684 | 2.0274887085 | -0.1934038401 |

Fold Macro F1은 `0.4370364 / 0.4480151 / 0.4546644 / 0.4447493 /
0.4515918`이다.

클래스별 최대 하락은 **LGG `-0.1304`(0.4889→0.3585), KIRC
`-0.1071`(0.2813→0.1741)**로 사전 고정 `-0.05` 붕괴 기준을 위반했다. 다음은
PAAD `-0.0204`, THCA `-0.0142`로 기준 이내다. 최대 개선은 TGCT `+0.0448`,
BRCA `+0.0431`, BLCA `+0.0364`다.

## Test 영향

EXP-527 대비 2,546개 test 행 전부에서 확률이 바뀌었고, argmax는
`325/2,546`행(12.8%)에서 바뀌었다. 평균 절대 확률 차이는
`0.0155228842`, 최대 차이는 `0.35890805`, 전체 확률 상관은 `0.98389`다.

## 재현성

- Config: `configs/exp653_mmr_gene_proxy_exp527.yaml`
- Runner: `scripts/run_exp653_mmr_gene_proxy_exp527.py`
- Metrics: `reports/exp653_mmr_gene_proxy_exp527/metrics.json`
- OOF: `oof/exp653_mmr_gene_proxy_exp527.csv`
- test 확률: `preds/exp653_mmr_gene_proxy_exp527_test_proba.csv`
- submission: `submissions/exp653_mmr_gene_proxy_exp527.csv`
- submission SHA-256:
  `faa1f03f9de4d0590afd2ca422bf64804f88ea92f53de7cf85a194f82a1df4b7`
- 재현 상태: `INFERENCE_VERIFIED`
- checkpoint 재추론: submission byte-level 일치, test 라벨 100%, 확률 최대
  차이 `1.49e-7`

## 판단과 다음 행동

- Macro F1 gate는 근소하게 통과했지만 LGG·KIRC 붕괴가 사전 고정 기준을
  크게 초과해 **`ARCHIVE`**한다. Log Loss 개선이 크더라도 클래스 붕괴
  기준을 사후에 완화하지 않는다.
- MMR panel 자체가 KIPAN/KIRC·GBMLGG/LGG 계보 혼동을 유발하는 구체적
  메커니즘은 확인하지 않았다(신장/교세포종 계열과 생물학적 직접 연관은
  없어 보임) — 저장소의 다른 무관한 feature 추가들과 마찬가지로 XGBoost
  분할 경쟁에서 이 축이 유독 불안정하다는 반복 관찰과 일치한다.
- EXP-527을 대체하지 않는다.
- 이 결과를 근거로 MMR·observable marker panel 계열 feature를 추가로
  탐색하지 않는다.
