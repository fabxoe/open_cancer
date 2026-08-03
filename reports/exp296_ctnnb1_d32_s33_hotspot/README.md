# EXP-296 CTNNB1 D32/S33 hotspot 확장 (phosphodegron 모티프 나머지 조각)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-296 / #296 |
| 목적 | 기존 hotspot-34의 CTNNB1 S37/S45와 같은 β-catenin phosphodegron 모티프의 나머지 두 위치(D32, S33)를 별도 컬럼으로 추가 |
| 핵심 입력 | EXP-094 Feature Spec v1 + `hotspot__CTNNB1_32` + `hotspot__CTNNB1_33` (2개 컬럼) |
| 모델 | XGBoost, EXP-094와 동일 하이퍼파라미터, official seed 42 단일 실행 + 3-seed stability check |
| Local OOF Macro F1 (seed 42, 공식) | 0.4172413559 (EXP-094 대비 `+0.0003547820`) |
| Public LB | 미제출 |
| 판단 | **기각(NOT ADOPTED)** — Macro F1 gate·fold-std gate·클래스별 F1 gate 3개 실패 |

## 배경

DominoEffect 스타일 panel-wide 스크리닝(#292 백로그, hotspot-34 제외 잔여
패널 재발 빈도 조사)에서 CTNNB1 D32/S33이 후보로 발굴됐다. 두 위치는
기존 hotspot-34에 이미 포함된 CTNNB1 S37/S45와 같은 β-catenin
N-terminal phosphodegron 모티프(GSK3β/CK1 인산화 클러스터, destruction
complex 분해 신호)의 나머지 조각이라 구조적으로 hotspot-34와 동일한
"단일 유전자 위치 정밀화" 패턴(POLE ED 파일럿 D/E와 같은 계열)이다.

## 사전 검증 (Issue #296 논의에서 완료)

- Vera 게이트 A(support≥10, p0≤0.997)/B(support≥5) 전부 5개 fold 통과,
  게이트 C(dominance≥0.8) 미발동(최대 0.53)
- burden 교란 체크: S33은 UCEC에서 carrier 평균 burden(20.9)이
  non-carrier(140.6)보다 오히려 **낮음** — 저-변이부담 CTNNB1-mutant
  UCEC 분자아형과 일치하는 진짜 생물학적 신호로 해석. D32는 UCEC/LIHC
  둘 다 carrier가 1.4~1.5배 높지만 ACC 아티팩트(2배, 최대 396)보다
  약하고 CTNNB1-HCC 연관성 자체가 이미 확립된 문헌 소견이라 우려 수준은
  아님(관련 방법론 이슈: [#295](https://github.com/fabxoe/open_cancer/issues/295))
- D32/S33/S37/S45 4개 위치는 표본이 완전히 배타적(교집합 0)이고 암종
  분포가 전부 달라(D32: UCEC/LIHC 혼재, S33: UCEC 45.8%, S37: UCEC 64%,
  **S45: ACC 33%로 나머지와 확연히 다름**) 병합 시 정보 손실
  위험(EXP-058 패턴)이 컸음 → 개별 컬럼 유지로 설계 확정

## 방법

`src/open_cancer/ctnnb1_hotspot_features.py`의 `Ctnnb1Family`를 새로
구현(Feature Factory family, `pole_ed_features.PoleEdFamily`와 동일한
구조)했다. 매칭은 `hotspot_features.py`의 기존 hotspot-34와 동일하게
position-level(참조 AA만 확인, alternate 무관)이며, `pole_ed_features.py`의
exact-triple 매칭과는 다르다 — S37/S45와 같은 매칭 규칙을 그대로 따른
것이다. 실행 전 `find_semantically_equivalent_features`로 두 신규 컬럼이
frozen v1(S37/S45 포함)의 기존 컬럼과 byte-identical하지 않음을 확인했다
(`semantic_equivalence_matches: {}`, 중복 없음 확정).

## 사전 표본 분포

| Feature | train 양성 건수 | 양성률 | fold별 분포 |
|---|---:|---:|---|
| `hotspot__CTNNB1_32` | 23 | 0.371% | `{0:3, 1:2, 2:4, 3:8, 4:6}` |
| `hotspot__CTNNB1_33` | 24 | 0.387% | `{0:5, 1:5, 2:4, 3:7, 4:3}` |

POLE hotspot5(EXP-181, fold 3에 1건뿐)와 달리 두 컬럼 모두 5개 fold에
전부 표본이 있어 seed 민감도 위험이 상대적으로 낮다.

## 결과 1 — 승격 기준 대조 (공식 seed 42 기준)

| 기준 | 결과 | 통과 |
|---|---:|---|
| Macro F1 +0.001 이상 | +0.0003547820 | ❌ |
| fold-std 악화 0.002 미만 | +0.0020876816 | ❌ |
| Log Loss 악화 없음 | -0.0012414574(개선) | ✅ |
| 전 클래스 F1 악화 없음 | LUAD -0.0472178289 | ❌ |

4개 기준 중 3개 실패로 **기각**한다. Log Loss만 개선됐을 뿐, Macro F1
개선폭(+0.00035)은 채택 임계값(0.001)의 3분의 1 수준에 불과하고, 가장
큰 악화는 D32/S33 어느 쪽과도 직접 연관이 없어 보이는 **LUAD
(-0.0472)**다 — 이 세션에서 반복 관찰된 "sparse feature 추가가 결정
경계를 넓게 흔들어 무관한 클래스에 collateral 손실을 낸다"는 패턴과
일치한다.

## 결과 2 — Watch class (UCEC/LIHC) 및 클래스별 상세

| 클래스 | F1 delta |
|---|---:|
| UCEC | +0.0003878839 |
| LIHC | -0.0032803097 |

사전검증에서 기대했던 "UCEC/LIHC 신호"는 실제로는 거의 flat했다 — UCEC는
사실상 무변화, LIHC는 오히려 소폭 하락. 반면 관련 없어 보이는 클래스들
(CESC +0.0379, PAAD +0.0245, ACC +0.0171, LAML +0.0148)에서 더 큰
움직임이 나타났는데, 표본 23~24건짜리 sparse 컬럼 2개 추가가 전체 결정
경계에 광범위하게 영향을 준 결과로 해석하는 것이 가장 합리적이며,
D32/S33의 "생물학적 타겟 클래스"가 실제로 개선됐다는 근거는 되지 않는다.

## 결과 3 — 3-seed 안정성 확인

| Seed | OOF Macro F1 |
|---|---:|
| **42 (공식 기록)** | 0.4172413559 |
| 1001 | 0.4147206692 |
| 1002 | 0.4165275758 |
| 1003 | 0.4197141208 |

4개 seed 평균 0.4169874553, 표준편차 0.0020643411 — 공식 seed 42는 이
분포의 중앙 근처에 있어(이상치 아님) EXP-181의 "seed 42만 뚜렷한
이상치" 문제는 재발하지 않았다. 다만 seed 1001의 fold-std(0.0131)가
공식 기록(0.0100)보다 커, baseline 대비 개선폭이 애초에 작은 상태에서
seed 변동만으로도 gate 재검토를 뒤집기 충분함을 확인했다 — 기각 판단을
더 확실하게 뒷받침한다.

## S37/S45와의 결합 판단 (재확인)

`find_semantically_equivalent_features`가 빈 dict를 반환해 D32/S33이
기존 v1 컬럼(S37/S45 포함)과 중복되지 않음을 코드 수준에서 재확인했다.
사전검증에서 이미 확인한 완전 배타적 표본과 서로 다른 암종 분포(특히
S45의 ACC 집중)를 종합하면, 4개 위치를 하나의 OR 플래그로 합치는 것은
정보 손실이 명백해 처음부터 시도하지 않았다(EXP-058 교훈 적용).

## 결론

D32/S33 각각의 사전검증(게이트, burden, 배타성)은 모두 통과했지만,
실제 모델에 투입한 결과 전체 Macro F1 개선폭이 gate 임계값에 크게
못 미치고 fold 안정성도 악화됐으며, 정작 목표했던 UCEC/LIHC는 거의
움직이지 않고 무관한 LUAD가 가장 크게 하락했다. **CTNNB1 phosphodegron
확장 트랙은 이 결과로 기각·종료한다.**

## 재현과 관련 파일

- Config: `configs/exp296_ctnnb1_d32_s33_hotspot.yaml`
- Resolved config: `reproducibility/exp296_ctnnb1_d32_s33_hotspot/config.resolved.yaml`
- Metrics: `reports/exp296_ctnnb1_d32_s33_hotspot/metrics.json`
- Verdict 상세(stability_check·semantic_equivalence_matches 포함): `reports/exp296_ctnnb1_d32_s33_hotspot/verdict.json`
- Feature 모듈: `src/open_cancer/ctnnb1_hotspot_features.py`
- 단위 테스트: `tests/test_ctnnb1_hotspot_features.py`
- Submission: `submissions/exp296_ctnnb1_d32_s33_hotspot.csv` (미제출, 로컬 보관)
- Reproduction status: `NOT_STARTED` (일반 Local 실험, 리더보드 미제출)
- 실행 시간: 4498.88초(약 75분, 공식 5-fold + 3-seed stability 총 20개 fold 학습)
