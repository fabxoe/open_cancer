# EXP-605 저burden 클래스 한정 sample weight 리페어 (클래스 멤버십 기반)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-605 / #605 |
| 목적 | EXP-516(ARCHIVE)의 burden quantile 기준을 클래스 멤버십 기준으로 바꿔, EXP-516이 겪은 "표적이 아니었던 LUAD/BLCA/DLBC 붕괴"라는 collateral damage를 구조적으로 막을 수 있는지 검증 |
| 핵심 입력 | EXP-374와 동일한 feature set(stop 정규화 mutation type, Ensembl residue-position mask, pathway burden/composition, hotspot 34개) |
| 모델 | XGBoost, EXP-374와 동일한 하이퍼파라미터·checkpoint 정책 |
| 유일한 변경 | fold-train에서 train SUBCLASS가 8개 표적 클래스(KIRC, KIPAN, GBMLGG, SARC, PRAD, PCPG, THYM, LAML)인 샘플에 `balanced_sample_weight`를 1.2배 추가 곱함 |
| Local OOF Macro F1 | 0.4223194676 (EXP-374 대비 **-0.0044714592**, EXP-516 대비 +0.0001544630) |
| Public LB | 미제출 |
| 판단 | **ARCHIVE** — 게이트 미달, 원가설도 반증 |

## 원본 데이터와 입력

한 환자는 4,384개 유전자 각각에 대해 `WT`(변이 없음) 또는 변이 표기 문자열을 가진
행 하나로 표현된다. EXP-516은 이 행에서 파생한 "burden"(변이 유전자 수)의
fold-train 하위 25% quantile 샘플에 가중치를 줬지만, 이번 실험은 burden을 전혀
계산하지 않는다 — 대신 **train.csv에 이미 있는 `SUBCLASS` 라벨**만으로 가중치
대상을 정한다.

## 핵심 개념과 피처

- **표적 클래스 목록**: EXP-374 OOF 오답노트에서(EXP-516 실행 이전에 이미)
  확정된 8개 저burden/고오분류 클래스(KIRC, KIPAN, GBMLGG, SARC, PRAD, PCPG,
  THYM, LAML). 이번 실험 결과를 보고 고른 목록이 아니다.
- **fold-safe 가중치 배율**: `scripts/run_hotspot_xgb.py`의 기존
  `fold_sample_weight_multiplier` 훅(EXP-516이 이미 추가, 이번 실험은 재사용만
  함)이 매 fold마다 그 fold의 **train 라벨(`y_train`)만** 보고
  - `y_train`이 8개 표적 클래스 중 하나면 `1.2`, 아니면 `1.0`을 반환하고
  - 기존 `balanced_sample_weight`(class-frequency 보정)에 원소별로 곱한다.
  - burden quantile 경계 계산이 필요 없어 `load_train_mutated_gene_count()`
    같은 별도 fit 단계가 없다 — 순수하게 라벨 lookup이다.
- `open_cancer.constants.CLASS_LABELS`가 이미 알파벳순으로 정렬돼 있고
  `run_hotspot_xgb.py`의 `LabelEncoder().fit(list(CLASS_LABELS))`도 같은 순서를
  만들기 때문에, `CLASS_LABELS.index(name)`이 곧 `y_train`이 쓰는 정수 인덱스다
  (`scripts/run_exp605_class_scoped_sample_weight.py`의
  `resolve_target_class_indices()`).
- 다른 모든 feature, 모델 하이퍼파라미터, checkpoint 선택 정책
  (`macro_f1_validation`), seed, fold는 EXP-374·EXP-516과 완전히 동일하다.

## 모델이 학습하는 정보

모델 입력은 EXP-374와 동일한 sparse feature matrix, 타깃은 26개 `SUBCLASS`다.
유일한 차이는 `model.fit(..., sample_weight=...)`에 전달하는 가중치 벡터뿐이다.
실제로 적용된 배율은 resolved config의 `fold_sample_weight_multiplier`에
fold별로 기록돼 있다.

| fold | 1.2배 적용 샘플 수 | 평균 배율 |
|---:|---:|---:|
| 0 | 1,742 | 1.0702 |
| 1 | 1,741 | 1.0702 |
| 2 | 1,740 | 1.0701 |
| 3 | 1,742 | 1.0702 |
| 4 | 1,743 | 1.0703 |

fold-train의 약 35%(8개 클래스의 train 내 비중)가 1.2배를 받았다 — EXP-516의
"하위 25% quantile"(약 25%)보다 대상 비중이 더 크다는 점에 유의한다.

## 검증 방법

- `data/splits/stratified_5fold_seed42.csv` 공용 5-fold, seed 42.
- 가중치 대상은 fold의 `y_train` 라벨만으로 정해지므로 validation·test 정보가
  전혀 유입되지 않는다(quantile 경계처럼 별도 fit이 필요 없어 EXP-516보다도
  누수 경로가 단순하다).
- checkpoint는 EXP-374·EXP-516과 동일하게 validation Macro F1 기준으로 선택한다
  (`checkpoint_selection: macro_f1_validation`).
- 저장 checkpoint로 재추론한 submission이 원본과 byte-level로 완전히 일치함을
  확인했다(`reproducibility/exp605_class_scoped_sample_weight/comparison.json`:
  submission SHA-256 일치, test 라벨 일치율 100%, 확률 최대 차이 `1.46e-7`) →
  `INFERENCE_VERIFIED`.

## 실제 결과

| 지표 | EXP-605 | EXP-374 | EXP-374 대비 | EXP-516 | EXP-516 대비 |
|---|---:|---:|---:|---:|---:|
| OOF Macro F1 | 0.4223194676 | 0.4267909268 | **-0.0044714592** | 0.4221650046 | +0.0001544630 |
| Fold 평균 | 0.4216653050 | 0.4266436967 | -0.0049783917 | 0.4220899681 | -0.0004246631 |
| Fold 표준편차 | 0.0106143692 | 0.0085032169 | **+0.0021111524** | 0.0095450428 | **+0.0010693264**(EXP-516보다도 악화) |
| Accuracy | 0.4123528463 | 0.4128366393 | -0.0004837930 | 0.4123528463 | 0.0000000000 |
| Log Loss | 1.8581582308 | 1.8440648317 | +0.0140933990 | 1.8675223589 | -0.0093641281(개선) |

Fold Macro F1은 `0.4130788120 / 0.4130249943 / 0.4210030633 / 0.4193294509 /
0.4418902046`였다(선택 iteration `216 / 160 / 156 / 109 / 149`).

### 사전 고정 게이트(Issue #605) 판정

| 게이트 조건 | 기준 | 실측 | 통과 여부 |
|---|---|---:|---|
| OOF Macro F1 개선 | ≥ +0.001 | -0.0044714592 | **실패** |
| Fold 표준편차 악화 | < +0.002 | +0.0021111524 | **실패**(EXP-516의 +0.0010418259보다도 악화) |
| 클래스별 F1 붕괴 | -0.05 미만 없어야 함 | DLBC -0.0939152683 | **실패** |
| Log Loss | 크게 악화되지 않아야 함(보조 지표) | +0.0140934 | 보조 참고, 단독 기각 사유 아님 |

세 가지 주요 게이트(주 지표, fold 안정성, 클래스 붕괴)가 모두 실패했다 — EXP-516보다
오히려 더 명확하게 미달이다. 사전에 선언한 대로 1.2배와 8개 클래스 목록은 이번
결과를 본 뒤 조정하지 않았다.

### DLBC/ACC F1 delta (필수 리포트 항목)

| 클래스 | EXP-374 | EXP-516 | EXP-605 | EXP-605 - EXP-374 | EXP-605 - EXP-516 |
|---|---:|---:|---:|---:|---:|
| DLBC | 0.4642857143 | 0.4137931034 | 0.3703703704 | **-0.0939152683** | **-0.0434227330** |
| ACC | 0.8656716418 | 0.8695652174(주1) | 0.8592592593 | -0.0064123825 | -0.0103059581 |

(주1) EXP-516 report 본문에는 ACC가 표 밖에서 다뤄지지 않았으나, 이번 검증을 위해
`reports/exp516_burden_weighted_sample_weight/metrics.json`에서 재확인한 값이다.

**DLBC는 EXP-374 대비 -0.094로 이 실험에서 가장 크게 무너진 클래스이며, EXP-516의
DLBC 하락(-0.050)보다도 거의 두 배 더 악화됐다.** DLBC를 8개 표적 목록에 넣지
않았음에도(클래스 멤버십 기준이라 DLBC 행은 직접 가중치를 받지 않는다) 이런
결과가 나온 것은, 클래스 멤버십 기준이 quantile 기준보다 오히려 DLBC에 더 나쁜
영향을 줬다는 뜻이다(아래 해석 참고). ACC는 두 실험 모두 소폭 하락했고 정도는
비슷하다.

### LUAD/BLCA/DLBC 안정성 확인 (EXP-516 collateral damage 재발 여부)

Issue #605의 설계 의도는 "8개 표적 클래스만 직접 가중치를 주면 LUAD/BLCA/DLBC는
목록에 없으므로 직접 영향을 받지 않을 것"이었다.

| 클래스 | EXP-374 | EXP-516 | EXP-605 | EXP-605 - EXP-374 | EXP-516 - EXP-374 |
|---|---:|---:|---:|---:|---:|
| LUAD | 0.3692307692 | 0.3051948052 | 0.3174603175 | **-0.0517704518** | -0.0640359640 |
| DLBC | 0.4642857143 | 0.4137931034 | 0.3703703704 | **-0.0939152683** | -0.0504926108 |
| BLCA | 0.4942528736 | 0.4444444444 | 0.4804469274 | -0.0138059462 | -0.0498084291 |

**결과는 설계 의도와 반대다.**

- **LUAD는 여전히 크게 하락했다**(-0.0518) — EXP-516(-0.0640)보다는 덜하지만
  방향과 규모 모두 "직접 안 건드리면 안전하다"는 가정과 어긋난다.
- **DLBC는 EXP-516보다 오히려 더 크게 무너졌다**(-0.0939 vs -0.0505) — 목록에서
  뺐는데도 collateral damage가 더 심해졌다.
- **BLCA만 EXP-516보다 개선됐다**(-0.0138 vs -0.0498) — 세 클래스 중 유일하게
  "직접 안 건드리면 안전하다"는 가정과 부분적으로 맞아떨어진 경우다.

즉 8개 표적 클래스를 LUAD/BLCA/DLBC와 분리한 것이 LUAD·DLBC의 collateral
damage를 막지 못했다. BLCA만 완화됐을 뿐 원래 목표(LUAD/BLCA/DLBC 모두 안정)는
달성하지 못했다.

### 8개 표적 클래스 결과 (원가설 직접 검증)

| 클래스 | EXP-374 | EXP-516 | EXP-605 | EXP-605-EXP-374 | EXP-605-EXP-516 | 방향(374 대비) |
|---|---:|---:|---:|---:|---:|---|
| SARC | 0.2422802850 | 0.2124713959 | 0.2624434389 | +0.0201631539 | +0.0499720431 | 개선 (EXP-516에서 악화 → EXP-605에서 완전히 반전) |
| KIPAN | 0.2214983713 | 0.2269183746 | 0.2250262881 | +0.0035279168 | -0.0018920865 | 개선 |
| PRAD | 0.3109843081 | 0.3096590909 | 0.3121387283 | +0.0011544202 | +0.0024796374 | 개선 |
| KIRC | 0.1759530792 | 0.1970154664 | 0.1764705882 | +0.0005175091 | -0.0205448782 | 개선(거의 0) |
| PCPG | 0.2987551867 | 0.2967741935 | 0.2983870968 | -0.0003680899 | +0.0016129032 | 악화(거의 0) |
| LAML | 0.5410958904 | 0.5591397849 | 0.5377049180 | -0.0033909724 | -0.0214348669 | 악화 |
| GBMLGG | 0.3197831978 | 0.3133512545 | 0.3046357616 | -0.0151474362 | -0.0087154930 | 악화 |
| THYM | 0.3146853147 | 0.3267973856 | 0.2896551724 | -0.0250301423 | -0.0371422132 | 악화 |

8개 중 4개(SARC, KIPAN, PRAD, KIRC)는 EXP-374 대비 개선, 4개(PCPG, LAML,
GBMLGG, THYM)는 악화 — EXP-516과 마찬가지로 정확히 절반씩이다. 다만 개별 클래스의
방향은 EXP-516과 크게 다르다: **SARC는 EXP-516에서 가장 크게 악화된 클래스
(-0.0298)였는데 EXP-605에서는 가장 크게 개선된 클래스(+0.0202)로 완전히
반전**됐고, 반대로 **THYM은 EXP-516에서 개선(+0.0121)이었는데 EXP-605에서는
악화(-0.0250)로 반전**됐다. 즉 가중치 기준을 바꾸면 표적 클래스 내부의
개선/악화 패턴 자체가 재배열될 뿐, "표적 클래스는 대체로 개선된다"는 안정적인
경향은 이번에도 나타나지 않았다.

## 해석과 한계

- **전체 지표는 EXP-516과 거의 같은 폭으로 악화**됐다(Macro F1 -0.0045 vs
  EXP-516의 -0.0046). fold 표준편차는 EXP-516보다도 더 나빠졌다
  (+0.0021 vs +0.0010, EXP-374 대비). Log Loss만 EXP-516보다 소폭 개선됐다.
- **원가설이 반증됐다.** "클래스 멤버십으로 대상을 좁히면 목록 밖의
  LUAD/BLCA/DLBC는 직접 영향을 받지 않아 안전할 것"이라는 설계 의도와 달리,
  LUAD는 여전히 크게 하락했고 DLBC는 EXP-516보다 더 크게 하락했다. BLCA만
  개선됐다.
- **원인 추정 — 가중치 재분배의 zero-sum 성격.** `balanced_sample_weight`에
  곱하는 배율을 8개 클래스(fold-train의 약 35%)에만 적용해도, 이 클래스들의
  총 가중치 합이 커지는 만큼 손실 함수 안에서 나머지 65%(DLBC·LUAD·BLCA 포함)가
  차지하는 **상대적** 비중은 자동으로 줄어든다. "이 클래스는 직접 가중치를
  주지 않는다"는 설계가 곧 "이 클래스의 학습이 영향을 받지 않는다"를 보장하지
  않는다 — 8개 클래스 쪽 gradient 기여가 커지면 나머지 18개 클래스 사이의
  상대적 경쟁 구도가 바뀌고, 그중 DLBC·LUAD가 특히 취약했던 것으로 보인다.
  이는 다른 트랙(EXP-604, 확률 재정규화)에서 관찰된 "값 자체를 안 건드려도
  다중 클래스 경쟁 구도 전체가 함께 움직인다"는 문제와 같은 계열의 현상이다 —
  가중치 공간이든 확률 공간이든, 한 부분집합만 조정해도 나머지 전체가 상대적으로
  재배치되는 zero-sum 구조를 완전히 피하기는 어렵다.
- **DLBC는 팀 메모에 이미 기록된 대로 fold별 F1 표준편차가 큰(약 0.04) 소수
  클래스(train 38개)라, 가중치 재분배에 특히 민감하게 반응했을 가능성이 있다.**
  두 실험(EXP-516, EXP-605) 모두 DLBC가 가장 크게 하락한 클래스 중 하나였다는
  점은 이 민감성이 일회성이 아니라 반복되는 패턴일 가능성을 시사한다.
- **8개 표적 클래스 자체도 일관되게 개선되지 않았다.** 절반은 개선, 절반은
  악화라는 결과가 EXP-516과 동일하게 반복됐고, 개별 클래스의 방향은 크게
  달라졌다(SARC·THYM 반전). burden quantile이든 클래스 멤버십이든, 균일한
  고정 배율 하나로는 저burden/고오분류 클래스 그룹 전체를 일관되게 끌어올리지
  못했다.

## 다음 실험 후보

- 균일 고정 배율 대신 클래스별로 다른 배율을 주는 방향은, 이번 실험처럼
  8개 클래스 중 절반이 반대 방향으로 움직이는 패턴이 두 번 반복됐으므로
  우선순위를 낮춘다. 클래스별 개별 배율을 시도한다면 zero-sum 부작용을
  통제하기 위해 전체 가중치 합을 원래 `balanced_sample_weight`와 동일하게
  정규화하는 방식(예: 8개 클래스에 준 만큼 나머지 18개에서 미세 보정)을
  같은 Issue에서 통제 비교해야 한다.
- DLBC가 EXP-516·EXP-605 모두에서 가장 취약했던 점을 고려하면, "학습 가중치"
  축 전체보다는 DLBC 전용의 별도 안정화(예: 클래스별 seed 반복, DLBC 제외
  가중치 실험)를 별도 Issue로 분리해 검토할 수 있다.
- 학습 가중치 재분배 자체가 zero-sum 구조라는 점이 두 실험에서 반복 확인됐으므로,
  "학습 가중치" 축은 새 Issue에서 명시적으로 zero-sum 완화 장치를 설계하지
  않는 한 우선순위를 낮춘다.

## 재현과 관련 파일

- Config: `configs/exp605_class_scoped_sample_weight.yaml`
- Resolved config: `reproducibility/exp605_class_scoped_sample_weight/config.resolved.yaml`
- Runner: `scripts/run_exp605_class_scoped_sample_weight.py`
- 공용 훅: `scripts/run_hotspot_xgb.py`의 `fold_sample_weight_multiplier` 파라미터
  (EXP-516이 추가, 이번 실험은 콜백 로직만 교체해 재사용; 기본값 `None`이면
  기존 모든 실험과 동일하게 동작 — `uv run pytest -q`로 회귀 확인)
- Metrics: `reports/exp605_class_scoped_sample_weight/metrics.json`
- OOF: `oof/exp605_class_scoped_sample_weight.csv`
- test 확률: `preds/exp605_class_scoped_sample_weight_test_proba.csv`
- submission: `submissions/exp605_class_scoped_sample_weight.csv`
- submission SHA-256: `3d04f11160af7ad3b6e7c55aa9eb77c7cc54ca0967baf35bca8103da1da0edb8`
- Source commit: `cc96de4bd84cd9272a4d1645d653f591389af75c`
- Reproduction status: `INFERENCE_VERIFIED`
  (`reproducibility/exp605_class_scoped_sample_weight/comparison.json`:
  submission SHA-256 일치, test 라벨 일치율 100%, 확률 최대 차이 `1.46e-7`)
- Public LB: 미제출 (게이트 미달로 제출하지 않음)
