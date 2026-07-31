# EXP-052 Feature Factory + Hotspot 연관 유전자 Co-mutation

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-052 / #52 |
| 부모 실험 | EXP-047 |
| 유일한 모델 입력 변경 | 문헌 근거 유전자 쌍 3개의 co-mutation indicator 3개 + 총 개수 1개 |
| 모델 | XGBoost, EXP-047과 동일 설정 |
| 전체 피처 수 | 35,088 |
| Local OOF Macro F1 | 0.4095069739 |
| Public LB | 미제출 |
| 판단 | fold 변동성 뚜렷한 개선, OOF는 소폭 개선 — 추가 pair 확장 검토 |

## 무엇을 추가했나

Feature Factory에 **family 7(co-mutation)**을 새로 구현했다(`docs/FEATURE_FACTORY.md`
로드맵). EXP-031(#31)에서 검증한 hotspot 관련 유전자들 중, 문헌에 잘 알려진
관계를 가진 3개 쌍을 고정 목록으로 등록했다.

| 유전자 쌍 | 관계 | 근거 |
|---|---|---|
| IDH1 / IDH2 | 상호배타성 | 저등급교종(LGG/GBMLGG)에서 두 유전자가 거의 동시에 변이되지 않음 |
| APC / CTNNB1 | 상호배타성 | 같은 Wnt 경로를 이중으로 망가뜨리는 게 중복이라 대장암에서 상호배타적 |
| PIK3CA / PTEN | 동시발생 | 같은 PI3K 경로를 이중으로 활성화하는 패턴으로 보고됨 |

각 쌍마다 "두 유전자 모두 변이됨(위치 무관, gene-level presence)" indicator
1개와, 전체 환자 단위로 "몇 개 쌍이 동시에 해당되는가"를 나타내는 총합
피처 1개를 추가했다(4개 신규 피처). **쌍 목록은 이 데이터의 빈도로 학습하거나
fold마다 다시 선정하지 않고, 외부 문헌 지식으로 고정**했다 — EXP-031의
COSMIC 재집계(attempt 1·2)와 2heej의 log-burden류 파생변수(EXP-029/043/045)가
공통으로 보여준 "재집계는 어렵다"는 교훈에 따라, 데이터 기반 pair 마이닝
대신 개별 유전자 컬럼에 없는 정보(유전자 간 관계)를 외부 지식으로만
주입했다.

## Feature Factory 검증

| 검증 | 결과 |
|---|---|
| co_mutation family OFF 시 기존 EXP-047 feature names | 동일(가산적 확장만 발생) |
| EXP-052 train shape | `(6201, 35088)` |
| EXP-052 test shape | `(2546, 35088)` |
| Feature Spec SHA-256 | `7f151405a1f167ef2c627c93d2207ac7a8ae37ecb0e50103ffc9ce056d7a9793` |

쌍별 관측 빈도(전체 8,747명 중):

| 피처 | train | test |
|---|---:|---:|
| `sample__comut_IDH1_IDH2` | 3 | 2 |
| `sample__comut_APC_CTNNB1` | 33 | 44 |
| `sample__comut_PIK3CA_PTEN` | 102 | 51 |
| `sample__comut_pair_total_count`(합) | 138 | 97 |

**해석 주의**: IDH1/IDH2는 문헌상 "거의 항상" 상호배타적이라고 알려져 있는데
실제로는 train 3건·test 2건에서 동시 관측됐다. 매우 드문 수치(전체의
0.06% 미만)라 알려진 예외적 co-mutation 사례와 부합하는 정도로 보이며,
"상호배타성" 전제 자체를 무효화하지는 않는다. APC/CTNNB1도 고전적으로는
대장암에서 상호배타적이라고 알려졌지만 train 33건·test 44건으로 완전
배타적이지는 않았다 — 이는 이 상호배타성 지식이 원래 **대장암 한
암종**에서 확립된 관계인데, 이 데이터셋은 26개 암종 전체에 동일하게
적용했기 때문일 가능성이 높다(다른 암종에서는 두 유전자가 독립적으로
작동할 수 있음). 이 한계는 다음 실험에서 암종별 조건부 관계로 세분화할
근거가 된다.

## 내부 검증 결과

공용 `data/splits/stratified_5fold_seed42.csv`와 EXP-047의 XGBoost 설정을
그대로 사용했다.

| 항목 | EXP-047 | EXP-052 | 차이 |
|---|---:|---:|---:|
| 전체 OOF Macro F1 | 0.4088132438 | 0.4095069739 | +0.0006937301 |
| fold 표준편차 | 0.0085063656 | 0.0052610612 | -0.0032453044 |
| Accuracy | 0.4031607805 | 0.4039671021 | +0.0008063216 |
| Log Loss | 1.8519974947 | 1.8544446230 | +0.0024471283 |

fold별 Macro F1: 0.4106308554, 0.4136261798, 0.4002611603,
0.4051305971, 0.4138423476 (fold 평균 0.4086982280).

전체 OOF 개선폭은 크지 않지만(+0.0007), **fold 표준편차가 뚜렷하게
줄었다**(0.0085 → 0.0053, 약 38% 감소) — 5개 fold 점수가 이전보다 훨씬
고르게 나왔다는 뜻이다. 클래스별로는 26개 중 17개가 개선(PAAD +0.0405,
LUAD +0.0309, CESC +0.0146, TGCT +0.0137, PRAD +0.0134, STES +0.0124)되고
9개가 하락(BLCA -0.0425, ACC -0.0174, PCPG -0.0141, OV -0.0117, SKCM
-0.0101)했다. 개선된 클래스 수가 더 많고 하락한 쪽도 대부분 이미 높은
점수(ACC 0.84, SKCM 0.74)에서의 소폭 하락이라 전체적으로는 안정성 위주의
개선으로 해석한다.

## 재현 상태

`run_experiment` 공용 러너가 실행 직후 checkpoint 추론을 자동 재현
검증했다.

- 원본과 재생성 submission SHA-256: `37388d81943108529126010664a0b3e9dfc313d14c871bb065eb0c4d3c5456ae`
- test 라벨 일치율: 100%
- test 확률 최대 절대 차이: `2.9735565232336114e-08`
- 허용 범위: `atol=1e-6`, `rtol=1e-6`
- 결과: `INFERENCE_VERIFIED`

Public leaderboard에는 제출하지 않았다.

## 다음 실험 후보

1. **암종별 조건부 관계로 세분화**: APC/CTNNB1처럼 원래 특정 암종(대장암)에서만
   성립하는 관계를 전체 26개 암종에 동일 적용하지 말고, 관련 암종군에서만
   활성화하는 조건부 피처 검토.
2. 추가 문헌 근거 쌍 확장(예: TP53/PIK3CA 등 낮은 확신도 쌍은 우선 보류).
3. fold 표준편차 개선이 일관되게 재현되는지 다른 seed·다른 모델 설정에서도
   확인.
4. 로컬에서 명확한 개선이 확인된 뒤에만 리더보드 제출(제출 횟수 제한 고려).

## 관련 파일

- Config: `configs/exp052_hotspot_cooccurrence.yaml`
- Resolved config: `reproducibility/exp052_hotspot_cooccurrence/config.resolved.yaml`
- Metrics: `reports/exp052_hotspot_cooccurrence/metrics.json`
- Submission: `submissions/exp052_hotspot_cooccurrence.csv` (미제출)
- Reproduction: `reproducibility/exp052_hotspot_cooccurrence/`
- Factory 운영 안내: `docs/FEATURE_FACTORY.md`
