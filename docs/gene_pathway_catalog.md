# Gene → Pathway 매핑 카탈로그 (TCGA PanCanAtlas 10-pathway)

> 이 문서는 카탈로그 생성 작업(Issue #167)의 산출물이며 모델 실험이 아니다.
> `EXPERIMENT_HISTORY.md` 대상이 아니다.

## 출처와 라이선스

- 인용: Sanchez-Vega F, et al. "Oncogenic Signaling Pathways in The Cancer
  Genome Atlas." Cell. 2018;173(2):321-337. doi:10.1016/j.cell.2018.03.035,
  Supplementary Table S3.
- 원본 파일: `data/external/tcga_pancanatlas_table_s3.xlsx`
  (SHA-256 `df722435b7c069b9225c9e4bbef7ab812385bd5e8ab7c415837cde5f2838c640`) — 라이선스(CC BY-NC-ND 4.0, 팀 확인)상 원본과
  파생 CSV 모두 이 repo에 커밋하지 않는다 (`data/external/`는 전체
  `.gitignore` 처리됨).
- 보조 참고 파일: `data/external/gene_whitelist_cosmic_v104.csv`
  (COSMIC CGC v104 교집합, 361개 유전자) — pathway
  membership 소스가 아니라 교집합 참고 플래그로만 사용.
- 파생 CSV: `data/external/gene_pathway_mapping.csv` (컬럼: gene, pathway,
  og_tsg, hotspot_positions, in_panel, in_cosmic_whitelist) — 커밋 금지.

## 카탈로그 규모

- pathway 시트 10개에서 추출한 (gene, pathway) 행: 335개
- 고유 유전자 수: 334개
- 이 중 학습 패널(4,384개 유전자 컬럼)에 존재: 184개
- 패널 전체 유전자 수(참고): 4384개
- 여러 pathway에 동시에 속한 유전자: 1개
  (다중 라벨이므로 행 수 > 고유 유전자 수)

## Pathway별 커버율

| Pathway | 총 유전자 | 패널 내 유전자 | 패널 커버율 | OG | TSG | Unknown | COSMIC whitelist 교집합 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cell Cycle | 15 | 15 | 100.0% | 9 | 6 | 0 | 11 |
| HIPPO | 38 | 14 | 36.8% | 10 | 27 | 1 | 4 |
| MYC | 13 | 6 | 46.2% | 5 | 5 | 3 | 2 |
| NOTCH | 71 | 42 | 59.2% | 4 | 26 | 41 | 7 |
| NRF2 | 3 | 2 | 66.7% | 1 | 2 | 0 | 2 |
| PI3K | 29 | 19 | 65.5% | 18 | 10 | 1 | 11 |
| TGF-Beta | 7 | 6 | 85.7% | 0 | 7 | 0 | 6 |
| RTK RAS | 85 | 44 | 51.8% | 37 | 5 | 43 | 25 |
| TP53 | 6 | 4 | 66.7% | 3 | 3 | 0 | 3 |
| WNT | 68 | 32 | 47.1% | 40 | 24 | 4 | 8 |

패널 커버율 편차가 크므로(가장 낮은 pathway는 패널에 거의 없는 유전자로만
구성될 수 있음), pathway-level aggregation feature를 설계할 때 이 표를
우선순위 판단 근거로 사용한다(#156 로드맵 "암종별 유전자 연관 집계" 항목).

## 34-position hotspot 대조 (팀 채택 리스트 vs Table S3)

비교 대상: `src/open_cancer/hotspot_features.py`의 `EXTENDED_HOTSPOTS`
(EXP-031→069→094에서 동결된 34개 (gene, position, reference_aa) 리스트).
Table S3의 `Hotspots (AA #)` 컬럼에서 숫자 위치만 파싱해 (gene, position)
쌍으로 비교했다(참조 아미노산 문자는 이 카탈로그에서 재검증하지 않음).

- 전체 34개 중 일치: 25개
- 유전자는 pathway에 있지만 그 position은 Table S3 hotspot 목록에 없음:
  2개
- 유전자 자체가 10개 pathway 중 어디에도 없음(이 논문의 oncogenic signaling
  pathway 분류 범위 밖): 7개

### 일치한 위치

| Gene | Position | 팀 reference AA |
|---|---:|---|
| BRAF | 600 | V |
| CTNNB1 | 37 | S |
| CTNNB1 | 45 | S |
| EGFR | 790 | T |
| EGFR | 858 | L |
| HRAS | 12 | G |
| HRAS | 13 | G |
| HRAS | 61 | Q |
| PIK3CA | 545 | E |
| PIK3CA | 1047 | H |
| TP53 | 175 | R |
| TP53 | 245 | G |
| TP53 | 248 | R |
| TP53 | 273 | R |
| TP53 | 282 | R |
| PIK3CA | 542 | E |
| PIK3CA | 546 | Q |
| PIK3CA | 345 | N |
| PTEN | 130 | R |
| PTEN | 233 | R |
| FBXW7 | 505 | R |
| AKT1 | 17 | E |
| KIT | 816 | D |
| FGFR3 | 249 | S |
| RAC1 | 29 | P |

### 유전자는 있지만 position이 다른 경우

| Gene | Position | 팀 reference AA |
|---|---:|---|
| APC | 1450 | R |
| APC | 876 | R |

### 유전자 자체가 10개 pathway 밖

| Gene | Position | 팀 reference AA |
|---|---:|---|
| GNAS | 201 | R |
| IDH1 | 132 | R |
| IDH2 | 140 | R |
| IDH2 | 172 | R |
| U2AF1 | 34 | S |
| POLE | 286 | P |
| POLE | 411 | V |

**해석**: EXP-160(residue-position negative control)에서 `max_residue_position`이
gene×mutation-type 소속을 넘어서는 실제 신호를 담고 있다는 결론이 이미
확인됐다. 위 표에서 팀 hotspot과 Table S3 문헌 hotspot이 겹치는 위치(25개)는
그 신호가 독립적인 문헌 출처와도 부합한다는 교차 검증 근거가 된다.
"유전자는 있지만 position이 다른" 경우(APC 876/1450)는 실제 Table S3 원본 셀을
확인한 결과(`Q1429, Q1367, ...` 등 14개, 팀 목록과 겹치지 않음) Table S3가
APC의 완전히 다른 missense 위치 집합을 hotspot으로 채택하고 있어, 이 논문
자체가 팀이 채택한 R876/R1450(문헌상 nonsense mutation cluster region으로
추정)을 hotspot으로 다루지 않는 것으로 보인다. 다만 이는 두 소스의 채택 기준
차이를 관찰한 것일 뿐, 어느 쪽이 더 정확한지 이 카탈로그만으로 판정하지
않는다. "유전자 자체가 pathway 밖"인 경우(GNAS, IDH1, IDH2, U2AF1, POLE)는
애초에 이 10-pathway 프레임워크가 다루지 않는 유전자(대사·스플라이싱 등)라서
비교 대상이 아니다. 두 경우 모두 negative-control 후속 이슈로 자동 승격하지
않는다.

## 재현

```bash
uv run python scripts/build_gene_pathway_catalog.py
```

입력 파일이 로컬 `data/external/`에 없으면 라이선스 정책상 팀 공유 채널로
원본을 받아 배치해야 한다(`data/external/tcga_pancanatlas_table_s3.meta.json`
참고, 이 파일도 커밋되지 않음).
