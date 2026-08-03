# Hotspot 스크리닝 방법론 개선 — 샘플 변이부담(burden) 통제 단계 추가

> 새 모델 실험이나 점수를 만들지 않는 target-independent 방법론 점검
> 기록입니다. 실행 전 기각이므로 Experiment Issue와 EXP-ID를 만들지
> 않습니다. 실제 실험 결과의 단일 원본은
> [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)입니다.

## 배경

DominoEffect 스타일 panel-wide 스크리닝(hotspot-34 제외 잔여 4,384개
유전자 재발 빈도 조사, 240개 후보 발굴)에서 ACC 6개 유전자(LRIG1×2,
SOWAHC, CMPK2, PEX6, NFKB2, TM7SF2)가 100% ACC 집중으로 나왔다. ID
클러스터링(배치 아티팩트)은 아니었지만, carrier 57건의 평균
`mutated_gene_count`(변이 유전자 수, burden 프록시)가 non-carrier
15건보다 약 2배 높았다 — recurrence만 보고 "recurrence가 고변이
샘플에 쏠려있는지"를 검증하지 않은 스크리닝 방법론 자체의 맹점으로
판단했다([Issue #295](https://github.com/fabxoe/open_cancer/issues/295)).
이 문서는 240개 후보 전체에 이 체크를 소급 적용하고, 향후 재사용 가능한
표준 절차로 만든 결과다.

## 방법

`scripts/screen_hotspot_burden_confound.py`를 새로 구현했다. 두 개의
독립적인 체크를 후보별로 수행한다.

1. **Burden ratio**: 후보의 dominant 암종 내에서 carrier 평균
   `mutated_gene_count` / non-carrier 평균 — 암종별 baseline burden이
   크게 다르므로(예: UCEC/STES/SKCM/COAD 저 hypermutator 아형은 자연히
   높음) 전역이 아니라 dominant 암종 **내부**에서만 비교한다.
   `n_in_dominant_class`(dominant 암종 내 carrier 수)가 작으면(1~2건)
   단일 초고변이 샘플 하나가 비율을 왜곡할 수 있어 `>=5`인 경우만
   "reliable"로 취급한다.
2. **공유 carrier ID 클러스터**: 같은 dominant 암종 내에서 다른 후보와
   carrier 표본이 크게 겹치는지(Jaccard >= 0.3) 확인한다. 이 체크가
   실제로 더 결정적이었다 — SOWAHC/NFKB2는 burden ratio가 각각
   0.65/1.00로 개별로는 "clean"이었지만, 같은 ACC 샘플 군을 다른
   4개 유전자와 공유한다는 사실은 이 클러스터 체크에서만 드러났다.

두 체크 중 하나라도 걸리면 "제외 권고" 후보로 분류한다(reliable
artifact_suspect ∪ cluster 멤버).

## 결과 1 — 240개 후보 전체 burden ratio 분포

| 분류 | 기준 | 건수 |
|---|---|---:|
| `clean` | ratio < 1.4 | 97 |
| `mild_concern` | 1.4 ≤ ratio < 1.8 | 18 |
| `artifact_suspect` | ratio >= 1.8 | 125 |

`artifact_suspect` 중 `n_in_dominant_class >= 5`(reliable)인 경우는
51건이다. 나머지는 dominant 암종 내 carrier가 1~4건뿐이라 단일/소수
초고변이 샘플에 의한 왜곡일 가능성이 커 참고용으로만 남긴다.

## 결과 2 — 공유 ID 클러스터

Jaccard >= 0.3인 쌍 32개, 관련 후보 39건. ACC 클러스터가 원래 발견한
6개보다 훨씬 크다 — LRIG1(24,26)·CMPK2·PEX6·TM7SF2·THEM4·NOTCH2(5,19)·
PLEC(1321,2106,2113)·NFKB2·UQCRFS1(6,8)·OGFR(556,557) 등 최소 15개
gene-position이 서로 다른 조합으로 겹치는 ACC 샘플을 공유한다
(`UQCRFS1_6`↔`UQCRFS1_8` Jaccard 0.90이 최고). UCEC에도 더 작은
네트워크(RALA/SPARCL1/COL17A1/PEX2, APC/SMC4, ATP2C1/XPO1/MBOAT2/DCT
등)가 있고, SKCM은 대부분 2건짜리 약한 겹침이다.

## 결과 3 — 최종 제외 권고 (reliable burden ∪ cluster)

| dominant 암종 | 제외 권고 건수 |
|---|---:|
| STES | 24 |
| ACC | 23 |
| UCEC | 13 |
| SKCM | 11 |
| BRCA | 2 |
| BLCA | 1 |
| COAD | 1 |
| **합계** | **75 / 240 (31.3%)** |

STES(위·식도암)가 가장 큰 비중을 차지한 건 예상 밖이었다 — MSI-high
STES 아형이 UCEC/COAD처럼 hypermutator 특성을 가진다는 문헌과 부합한다.
75건을 빼면 165개 후보가 남는다. **이 필터는 "가짜다"를 증명하는 게
아니라 "이 패널의 recurrence 신호만으로는 신뢰할 수 없다"는 뜻이다** —
UCEC/STES/SKCM/COAD의 hypermutator 아형이 넓게 재발성을 만드는 건 그
자체로 알려진 실제 생물학이지, 데이터 손상이 아니다.

## 결과 4 — 대기열(NPM1/EGFR×2/NFE2L2/PIK3CA) 영향

세션에서 대기 중인 5개 문헌 후보를 같은 체크로 확인했다.

| 후보 | dominant 암종 | n | burden ratio | 판정 |
|---|---|---:|---:|---|
| NPM1 288 | LAML | 21 | 1.143 | clean |
| EGFR 289 | GBMLGG | 19 | 1.368 | clean |
| EGFR 598 | GBMLGG | 13 | 1.345 | clean |
| NFE2L2 79 | HNSC | 4 | 1.118 | clean |
| **PIK3CA 88** | **UCEC** | **10** | **3.218** | **artifact_suspect (reliable)** |

NPM1/EGFR×2/NFE2L2 4개는 모두 clean — 각각 잘 알려진 문헌 생물학(NPM1↔
AML, EGFR↔교모세포종)과 일치해 burden 아티팩트가 아니라는 심증이
강해졌다. **PIK3CA 88은 제외 권고 목록에 포함된다** — UCEC 내
carrier 평균 burden이 non-carrier의 3.2배로, 대기열에서 실제 착수
전 재확인이 필요하다는 신호다. (참고로 CTNNB1 D32/S33은 이미
[EXP-296](../exp296_ctnnb1_d32_s33_hotspot/README.md)에서 별도로
Vera 게이트·burden·배타성 검증을 마치고 실험까지 완료했다 — 이번 sweep
결과와 무관하게 D32/S33 자체는 이 목록에 없다.)

## 한계

- **인과관계 미확정**: burden ratio가 높다는 것은 "이 패널의
  recurrence 신호가 hypermutator 아형에 의해 부풀려졌을 가능성"을
  뜻할 뿐, 해당 위치가 실제 driver가 아니라고 증명하지는 않는다.
  문헌 근거가 강한 후보(PIK3CA 등)는 이 체크만으로 자동 배제하지
  말고 추가 검증(fold별 안정성, 문헌 대조)을 거쳐야 한다.
- **`n_in_dominant_class` 작은 경우의 노이즈**: `artifact_suspect`
  125건 중 51건만 `n>=5`로 reliable하다. 나머지 74건은 단일/소수
  샘플에 의한 극단치일 수 있어 참고용으로만 CSV에 남긴다.
- **원인 메커니즘이 burden만은 아님**: SOWAHC/NFKB2 사례처럼, 공유
  ID 클러스터에 속하면서도 개별 burden ratio는 낮은 경우가 있다 —
  "왜" 같은 샘플들이 여러 무관한 유전자에서 함께 재발하는지는 burden
  하나로 완전히 설명되지 않는다(다른 데이터 특성 가능성 배제 못함).

## 결론 — 표준 절차 추가

`scripts/screen_hotspot_burden_confound.py`를 향후 DominoEffect 스타일
스크리닝의 표준 다음 단계로 채택한다. 새 스크리닝 결과가 나오면
(1) burden ratio(암종 내부, `n_in_dominant_class` 함께 확인),
(2) 공유 carrier ID 클러스터를 항상 함께 확인하고, 두 체크 중 하나라도
걸리는 후보는 추가 문헌/생물학적 근거 없이는 hotspot 후보 목록에서
제외한다. ACC 관측은 "코호트 데이터 손상"이 아니라 "저·중간 TMB
암종에서 recurrence-only 스크리닝이 구조적으로 취약하다"는 방법론
이슈로 재정의해 기록을 종료한다.

## 재현과 관련 파일

- Issue: [#295](https://github.com/fabxoe/open_cancer/issues/295)
- 표준 절차 스크립트: `scripts/screen_hotspot_burden_confound.py`
- 원본 스크리닝(240개 후보 생성): `dominoeffect_screening.py`(RUN_MODE=explore,
  scratchpad 보관, 이번 문서의 입력)
- 전체 240건 결과: `reports/analysis/hotspot_screening_burden_control_results.csv`
- 공유 ID 클러스터 쌍: `reports/analysis/hotspot_screening_burden_control_clusters.csv`
- 관련: [EXP-296](../exp296_ctnnb1_d32_s33_hotspot/README.md) — 이번
  burden 체크 방법론이 처음 적용된 CTNNB1 D32/S33 사전검증(둘 다
  clean~mild, 제외 목록에 없음)
