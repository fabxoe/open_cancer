# NPM1 288(exon-12 frameshift, "NPM1c") hotspot 사전 검증

> 새 모델 실험이나 점수를 만들지 않는 target-independent 사전 검증
> 기록입니다. 실행 전 기각/승인 판단이므로 이 문서 자체는 Experiment
> Issue와 EXP-ID를 만들지 않습니다. 실제 실험 결과의 단일 원본은
> [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)입니다.

## 배경

DominoEffect 스타일 panel-wide 스크리닝(240개 후보) 대기열 중 하나인
NPM1 288을 [#295](hotspot_screening_burden_control.md) 이후 표준이 된
5단계 절차(Vera 게이트 → burden 교란 → 암종 분포 → semantic
equivalence → 3-seed 안정성)로 검증했다.

## 위치 정의: reference-AA 표기 불일치

원본 스크리닝은 `reference_aa="WQ"`로 21건을 기록했지만, 실제 raw
NPM1 컬럼에는 같은 position 288의 frameshift가 두 가지 토큰으로
나뉘어 있다: `W288fs`(1건), `WQ288fs`(21건). 두 토큰은 ID가 전혀
겹치지 않고 둘 다 LAML 전용이다 — 같은 사건(NPM1 exon-12 frameshift,
"NPM1c", AML의 대표 driver)을 참조 서열 표기 길이만 다르게 기록한
것으로 판단해, **`hotspot__NPM1_288`을 "position 288의 frameshift"로
정의(참조 AA 무관, 22건)**했다. hotspot-34/POLE/CTNNB1이 쓰는 엄격한
단일-참조 매칭 규칙에서 벗어난 유일한 예외이며, 향후 표준 매칭
로직에 이런 이중 표기 케이스를 어떻게 반영할지는 별도 논의가
필요하다.

## Step 1 — Vera 게이트: Gate C 발동(예외 적용)

| fold | support_train | p0_train | dominant_class | dominance | Gate A | Gate B | Gate C(차단) |
|---:|---:|---:|---|---:|:---:|:---:|:---:|
| 0 | 17 | 0.9966 | LAML | 1.0 | ✅ | ✅ | 🚫 |
| 1 | 18 | 0.9964 | LAML | 1.0 | ✅ | ✅ | 🚫 |
| 2 | 21 | 0.9958 | LAML | 1.0 | ✅ | ✅ | 🚫 |
| 3 | 17 | 0.9966 | LAML | 1.0 | ✅ | ✅ | 🚫 |
| 4 | 15 | 0.9970 | LAML | 1.0 | ✅ | ✅ | 🚫 |

Gate A/B는 전부 통과하지만 5개 fold 전부 dominance가 정확히 1.0이라
Gate C(≥0.8, 발동 시 차단)가 처음으로 실제 발동한 케이스다.

### 예외 적용 근거

Gate C는 원래 [#233](https://github.com/fabxoe/open_cancer/issues/233)/[#276](https://github.com/fabxoe/open_cancer/issues/276)(post-hoc
class-wise decision offset)의 탐색 안정성을 위해 설계됐다. 이 세션이
축적한 실증 데이터는 **raw sparse feature의 위험이 dominance와 무관함**을
보여준다 — EXP-170/173(Cell Cycle any-nonsilent/LoF-TSG)은 dominance
0.11~0.18로 Gate C 근처도 가지 않았는데 DLBC F1을 붕괴시켰고, 반대로
POLE D(EXP-181)는 dominance 0.57~0.69로 훨씬 높았는데도 안전했다.
dominance 하나로 NPM1을 기계적으로 차단하는 것은 이 발견과 모순된다.

오히려 dominance=1.0은 "위험 신호"가 아니라 **"생물학적으로 정확한
신호"**일 가능성이 높다 — NPM1c(exon-12 frameshift)는 문헌상 AML의
pathognomonic marker(거의 확정적 진단 마커)이며, 데이터가 그 사실을
정확히 재현한 것으로 해석한다. Step 2~4(burden clean, 오염 없음, 중복
없음) 전부 통과가 이 해석을 뒷받침한다.

**결론: Gate C를 이 케이스에 한해 예외로 적용하고 Step 5(3-seed 안정성
체크)로 진행한다.** 이번 예외를 계기로 Gate C를 raw hotspot feature
사전검증에도 그대로 적용할지, offset 전용으로 스코프를 좁힐지는
[#254](https://github.com/fabxoe/open_cancer/issues/254)(게이팅 기준
재검토)에 참고 사례로 별도 추가해 논의한다.

## Step 2 — burden 교란: 통과(clean)

- union(22건) 기준 LAML 내부: carrier(n=22) 평균 burden 3.45 vs
  non-carrier(n=136) 평균 3.00, ratio 1.154 → `clean`
- `screen_hotspot_burden_confound.py`(WQ 단독 정의, n=21) 기준으로도
  ratio 1.143 → `clean`, 두 정의 모두 동일 결론
- **LAML은 26개 암종 중 burden 평균 순위 1위(가장 낮음)** — 애초
  우려(ACC/STES보다도 위험군일 수 있음)는 타당했지만, 실제로는 burden
  아티팩트 패턴이 나타나지 않았다. NPM1c가 normal-karyotype AML에서
  단독으로 발생하는 초기·단일 driver라는 문헌과 일치한다(hypermutator
  배경이 필요 없는 돌연변이).

## Step 3 — 암종 분포: 통과

carrier 22건 전부 LAML(100%), 다른 암종 오염 없음.

## Step 4 — 중복 확인: 통과

- `find_semantically_equivalent_features` → `{}`(기존 v1 4,419개
  컬럼 중 어느 것과도 byte-identical하지 않음)
- NPM1은 기존 `CO_MUTATION_PAIRS`(IDH1/IDH2, APC/CTNNB1, PIK3CA/PTEN)에
  없어 co-mutation 축과도 무관

## Step 5 — 3-seed 안정성 체크: LAML은 안정적, 전체 Macro F1은 불안정

공식 seed 42 + stability seed 1001/1002/1003, 4개 seed 전부 EXP-094
Feature Spec v1 + `hotspot__NPM1_288`(train 22건, test 9건) 학습.

| seed | OOF Macro F1 | delta vs EXP-094 | fold-std delta | LAML F1 delta | worst class(delta) |
|---|---:|---:|---:|---:|---|
| **42(공식)** | 0.4136385682 | **-0.0032480056** | -0.000039 | +0.019782 | DLBC(-0.044025) |
| 1001 | 0.4171585351 | +0.0002719612 | +0.003887 | +0.012886 | BLCA(-0.024862) |
| 1002 | 0.4178158047 | +0.0009292309 | +0.002825 | +0.010080 | DLBC(-0.031205) |
| 1003 | 0.4168779041 | -0.0000086698 | +0.000188 | +0.006291 | BLCA(-0.036723) |

4-seed 평균 OOF 0.4163727030, 표준편차 0.0016148371.

**LAML 방향성은 안정적이다** — 4개 seed 전부 LAML F1이 양의 방향으로
개선된다(+0.0063~+0.0198). 다만 크기는 seed 42가 가장 크고(0.0198)
이후 seed로 갈수록 줄어드는 경향이 있어, 공식 seed가 LAML 관점에서는
다소 유리한 편이었을 가능성이 있다.

**전체 Macro F1은 개선을 보장하지 못한다** — 공식 seed 42는 오히려
**-0.0032 악화**되고, stability seed 3개도 채택 gate(+0.001) 근처거나
못 미친다(1001 +0.0003, 1002 +0.0009, 1003 -0.00001). 4-seed 평균은
약 -0.0005로 사실상 순손실에 가깝다. Fold 표준편차도 공식 seed만
소폭 개선(-0.00004)이고 stability 3개는 전부 악화(+0.0019~+0.0039).

원인은 이 세션에서 반복 확인된 패턴과 동일하다 — LAML 자체는 개선되지만
**무관한 클래스가 collateral 손실**을 입는다. 공식 seed 42 기준 최악은
DLBC(-0.0440), 이어서 LUAD(-0.0216)·BLCA(-0.0161) 등 다수 클래스가
동반 하락한다(seed별 worst class 자체도 DLBC/BLCA로 흔들려 특정
클래스가 아니라 넓게 퍼진 노이즈로 보인다).

### 승격 기준 판정 (사용자 사전 합의 2개 조건)

| 조건 | 결과 |
|---|---|
| 1. dominance=1.0(LAML 전용 신호)이 seed 전반에 안정적으로 재현 | ✅ 4개 seed 전부 LAML F1 양의 방향 |
| 2. Macro F1/fold-std가 실제로 개선 | ❌ 공식 seed 악화(-0.0032), stability 3개도 gate 미달·fold-std 악화 |

**조건 2가 충족되지 않아 Experiment Issue로 승격하지 않는다.** Gate C
예외(Step 1)는 "위험 신호가 아니다"를 뒷받침했을 뿐 "개선된다"를
보장하지 않는다는 사전 우려가 실제로 재현됐다 — LAML 자체는 문헌과
일치하게 안정적으로 좋아지지만, 그 이득이 다른 클래스(주로 DLBC)의
collateral 손실로 상쇄돼 전체 Macro F1은 공식 기록 기준 오히려
악화된다. NPM1 288 트랙은 여기서 종료한다.

## 재현성

Step 1~4는 `scripts/npm1_288_precheck.py`(전부 이 저장소의
train.csv/canonical split/frozen v1 spec에서 직접 재계산, 실행마다
결정론적). Step 5는 `scripts/npm1_288_stability_check.py`(4-seed 모델
학습, EXP-094와 동일 하이퍼파라미터)이며 요약 결과는
`reports/analysis/npm1_288_precheck_data/npm1_288_stability_results.json`에
커밋했다(seed별 fold Macro F1·per-class delta 전체 포함). #251 PR 리뷰에서
요구된 것과 같은 기준으로, raw OOF까지는 커밋하지 않았지만 스크립트
재실행으로 동일한 결과를 재생성할 수 있다.

## 관련

- Issue: [#329](https://github.com/fabxoe/open_cancer/issues/329)
- [#295 hotspot 스크리닝 burden 교란 방법론](hotspot_screening_burden_control.md) — 이 문서가 따르는 5단계 표준 절차의 출처
- [EXP-296 CTNNB1 D32/S33](../exp296_ctnnb1_d32_s33_hotspot/README.md) — 같은 5단계 절차의 이전 적용 사례(기각)
- [#254 게이팅 기준 재검토](https://github.com/fabxoe/open_cancer/issues/254) — Gate C 예외 사례 참고 자료 추가 예정
