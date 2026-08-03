# DLBC 타겟 hotspot/구조 클러스터 feature 사전 검증

> 새 모델 실험이나 점수를 만들지 않는 target-independent 사전 검증
> 기록입니다. 실행 전 기각/보류이므로 Experiment Issue와 EXP-ID를
> 만들지 않습니다. 실제 실험 결과의 단일 원본은
> [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)입니다.

## 배경

Vera Health 권고: DLBCL은 단일 유전자 hotspot보다 (a) TP53의 구조/기능
부위(DNA-binding domain vs Zn2+ coordinating residue) 클러스터 구분,
(b) BCR/TLR signaling 축 유전자(PTPN6/SHP1, LYN, PRKCB, TLR2) + 히스톤
유전자의 반복 변이가 더 신뢰도 높은 신호로 문헌에 제시된다는 제안.
PIK3CA 도메인 분리 사전 검증(#241)과 같은 패턴(패널 매칭 → 기존 feature
상태 → 관련성 확인)을 적용했다.

## 1) 패널 매칭

TP53, PTPN6, LYN, PRKCB, TLR2 전부 4,384개 패널에 있다. 히스톤
유전자군은 문헌의 구 명명법(`HIST1H1E`, `HIST1H1C`, `HIST1H1B`,
`HIST1H1D`, `HIST1H1T`, `H1F0`)이 패널에 전혀 없다 — 패널은 신 HGNC
심볼을 쓴다. 패턴 검색(`HIST/H1-/H2A/H2B/H3/H4`)으로 실제 매치된 11개:
`H1-0, H1-2, H1-6, H2AC25, H2AJ, H2AX, H2AZ1, H2AZ2, H2BC12, H2BC3,
H4C3`. 문헌에서 DLBCL 히스톤 hotspot으로 가장 자주 인용되는
`HIST1H1E`(신 명명법 `H1-4`)는 패널에 없고, 정준 H3 유전자는 패널에
하나도 없다.

## 2) TP53 기존 feature 상태 + Zn 잔기 사실 확인

`EXTENDED_HOTSPOTS`(base v1)의 TP53은 개별 컬럼 5개(DBD/Zn 클러스터
구분 없이 각자 독립): `175(R), 245(G), 248(R), 273(R), 282(R)` — 전부
DNA-binding domain(94-289) 범위 안.

Vera가 제시한 Zn2+ coordinating 잔기를 실제 관측 reference AA와
대조했다:

| 위치 | Vera 주장 reference | 실제 관측 | train 건수 | 판정 |
|---|---|---|---:|---|
| 176 | C | C | 31 | 일치, 신규 position |
| 238 | C | C | 22 | 일치, 신규 position |
| 179 | H | H | 45 | 일치, 신규 position |
| 242 | C | C | 16 | 일치, 신규 position |
| 245 | C | **G** | 42 | **불일치** — 이미 `hotspot__TP53_245`(G245)로 등록된 DNA-contact 잔기이며 zinc 배위와 무관. Vera 원 데이터 오류로 확인, 미채택 |

## 3) DLBC 관련성

유전자 수준(어떤 변이든) DLBC(38건) 비율 vs 코호트 비율:

| 유전자 | DLBC 양성(38건 중) | DLBC 비율 | 코호트 비율 | enrichment | train 전체 양성 |
|---|---:|---:|---:|---:|---:|
| PTPN6 | 3 | 7.89% | 0.61% | 12.9배 | 38 |
| LYN | 1 | 2.63% | 0.92% | 2.9배 | 57 |
| PRKCB | 2 | 5.26% | 1.94% | 2.7배 | 120 |
| TLR2 | 1 | 2.63% | 1.24% | 2.1배 | 77 |
| TP53 | 3 | 7.89% | 28.54% | 0.28배(결핍) | 1770 |
| 히스톤 11종 전부 | 0 | 0% | 0% | N/A | 0 |

fold별 게이트(support_train≥10 & p0≤0.997, support_train≥5)는
PTPN6/LYN/PRKCB/TLR2/TP53 전부 5개 fold 통과. 히스톤 11종은 train 전체
양성이 0건이라 자동 미달.

## 결론 (세 방향 전부 보류)

### 히스톤 — 착수 불가

패널 내 신호가 0건이다. 문헌이 지목하는 유전자(`HIST1H1E` 등)가 애초에
패널 밖이라는 게 근본 원인으로 보인다.

### BCR/TLR 축(PTPN6/LYN/PRKCB/TLR2) — 보류

게이트는 5개 fold 전부 통과하지만, DLBC 근거가 유전자당 1~3건뿐이라
enrichment 배율(2.1~12.9배)이 통계적으로 매우 불안정하다. 현재 조사 중인
DLBC perturbation 이슈(#238, 플랫폼 간 비결정성 조사와 연동된 sparse
binary feature DLBC 민감도 트랙)와 같은 종류의 불안정성을 반복할 위험이
있다고 판단해 보류한다.

재검토 조건: n_jobs=1 진단 결론 확정 이후 + 착수 시 4-seed 안정성
체크(POLE D `#181` 패턴) 필수.

### TP53 Zn-클러스터(176/179/238/242) — 범위 밖으로 재분류

신규 position 자체는 유효하다(참조 AA 일치, 각 16~45건 관측). 다만
TP53은 DLBC에서 오히려 변이율이 낮아(7.89% vs 코호트 28.54%) "DLBC
타겟" 신호가 아니다. 이 후보의 실제 질문은 "TP53이 변이된 다양한
암종(코호트의 28.5%)을 서로 구분하는 데 도움이 되는가"이며, 이번
DLBC 타겟 트랙의 범위 밖이다. 245는 Vera 원 데이터 오류로 확인돼
어느 경우든 미채택.

## 관련

- [PIK3CA helical/kinase 도메인 사전 검증](pik3ca_domain_hotspot_precheck.md)
  (#241) — 같은 사전 검증 패턴
- [sparse binary feature DLBC 민감도 관찰](sparse_binary_feature_dlbc_sensitivity.md)
  — BCR/TLR 축 보류 판단의 근거가 된 기존 관찰
- [EXP-181](../exp181_pole_hotspot5/README.md) — 4-seed 안정성 체크 패턴의 원본
