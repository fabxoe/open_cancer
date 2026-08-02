#!/usr/bin/env python
"""Build the TCGA PanCanAtlas 10-pathway gene-mapping catalog (Issue #167).

Reads the externally licensed Sanchez-Vega et al. 2018 Table S3 workbook,
intersects it with the competition's 4,384-gene panel and the COSMIC
361-gene whitelist, and cross-validates its hotspot codons against the
team's adopted 34-position hotspot list. This is a reference-catalog task,
not a model experiment: it writes no EXPERIMENT_HISTORY.md entry.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from open_cancer.gene_pathway_catalog import (
    build_catalog_table,
    cross_validate_hotspots,
    load_pathway_rows,
    summarize_pathway_coverage,
)
from open_cancer.hashing import sha256_file
from open_cancer.hotspot_features import EXTENDED_HOTSPOTS
from open_cancer.paths import relative_posix

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
SOURCE_XLSX = ROOT / "data" / "external" / "tcga_pancanatlas_table_s3.xlsx"
COSMIC_WHITELIST_PATH = ROOT / "data" / "external" / "gene_whitelist_cosmic_v104.csv"
OUTPUT_CSV = ROOT / "data" / "external" / "gene_pathway_mapping.csv"
OUTPUT_DOC = ROOT / "docs" / "gene_pathway_catalog.md"


def load_panel_genes(train_path: Path) -> frozenset[str]:
    with train_path.open("r", encoding="utf-8", newline="") as file:
        header = next(csv.reader(file))
    return frozenset(header[2:])


def load_cosmic_whitelist_genes(path: Path) -> frozenset[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return frozenset(row["gene"] for row in reader)


def write_catalog_csv(path: Path, table: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "gene",
        "pathway",
        "og_tsg",
        "hotspot_positions",
        "in_panel",
        "in_cosmic_whitelist",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in table:
            writer.writerow(row)


def render_markdown(
    *,
    source_sha256: str,
    panel_gene_count: int,
    cosmic_whitelist_count: int,
    table: list[dict[str, object]],
    coverage: list[dict[str, object]],
    hotspot_comparison: dict[str, object],
) -> str:
    total_rows = len(table)
    distinct_genes = len({row["gene"] for row in table})
    genes_in_panel = {row["gene"] for row in table if row["in_panel"]}
    genes_in_multiple_pathways = {
        gene
        for gene in distinct_genes_set(table)
        if sum(1 for row in table if row["gene"] == gene) > 1
    }

    coverage_lines = "\n".join(
        f"| {row['pathway']} | {row['gene_count']} | {row['in_panel_count']} | "
        f"{row['panel_coverage_pct']:.1f}% | {row['og_count']} | {row['tsg_count']} | "
        f"{row['unknown_og_tsg_count']} | {row['in_cosmic_whitelist_count']} |"
        for row in coverage
    )

    match_lines = "\n".join(
        f"| {item['gene']} | {item['position']} | {item['team_reference_aa']} |"
        for item in hotspot_comparison["matches"]
    )
    position_unmatched_lines = "\n".join(
        f"| {item['gene']} | {item['position']} | {item['team_reference_aa']} |"
        for item in hotspot_comparison["position_unmatched"]
    )
    gene_absent_lines = "\n".join(
        f"| {item['gene']} | {item['position']} | {item['team_reference_aa']} |"
        for item in hotspot_comparison["gene_absent"]
    )

    return f"""# Gene → Pathway 매핑 카탈로그 (TCGA PanCanAtlas 10-pathway)

> 이 문서는 카탈로그 생성 작업(Issue #167)의 산출물이며 모델 실험이 아니다.
> `EXPERIMENT_HISTORY.md` 대상이 아니다.

## 출처와 라이선스

- 인용: Sanchez-Vega F, et al. "Oncogenic Signaling Pathways in The Cancer
  Genome Atlas." Cell. 2018;173(2):321-337. doi:10.1016/j.cell.2018.03.035,
  Supplementary Table S3.
- 원본 파일: `data/external/tcga_pancanatlas_table_s3.xlsx`
  (SHA-256 `{source_sha256}`) — 라이선스(CC BY-NC-ND 4.0, 팀 확인)상 원본과
  파생 CSV 모두 이 repo에 커밋하지 않는다 (`data/external/`는 전체
  `.gitignore` 처리됨).
- 보조 참고 파일: `data/external/gene_whitelist_cosmic_v104.csv`
  (COSMIC CGC v104 교집합, {cosmic_whitelist_count}개 유전자) — pathway
  membership 소스가 아니라 교집합 참고 플래그로만 사용.
- 파생 CSV: `data/external/gene_pathway_mapping.csv` (컬럼: gene, pathway,
  og_tsg, hotspot_positions, in_panel, in_cosmic_whitelist) — 커밋 금지.

## 카탈로그 규모

- pathway 시트 10개에서 추출한 (gene, pathway) 행: {total_rows}개
- 고유 유전자 수: {distinct_genes}개
- 이 중 학습 패널(4,384개 유전자 컬럼)에 존재: {len(genes_in_panel)}개
- 패널 전체 유전자 수(참고): {panel_gene_count}개
- 여러 pathway에 동시에 속한 유전자: {len(genes_in_multiple_pathways)}개
  (다중 라벨이므로 행 수 > 고유 유전자 수)

## Pathway별 커버율

| Pathway | 총 유전자 | 패널 내 유전자 | 패널 커버율 | OG | TSG | Unknown | COSMIC whitelist 교집합 |
|---|---:|---:|---:|---:|---:|---:|---:|
{coverage_lines}

패널 커버율 편차가 크므로(가장 낮은 pathway는 패널에 거의 없는 유전자로만
구성될 수 있음), pathway-level aggregation feature를 설계할 때 이 표를
우선순위 판단 근거로 사용한다(#156 로드맵 "암종별 유전자 연관 집계" 항목).

## 34-position hotspot 대조 (팀 채택 리스트 vs Table S3)

비교 대상: `src/open_cancer/hotspot_features.py`의 `EXTENDED_HOTSPOTS`
(EXP-031→069→094에서 동결된 34개 (gene, position, reference_aa) 리스트).
Table S3의 `Hotspots (AA #)` 컬럼에서 숫자 위치만 파싱해 (gene, position)
쌍으로 비교했다(참조 아미노산 문자는 이 카탈로그에서 재검증하지 않음).

- 전체 34개 중 일치: {hotspot_comparison['matched_count']}개
- 유전자는 pathway에 있지만 그 position은 Table S3 hotspot 목록에 없음:
  {hotspot_comparison['position_unmatched_count']}개
- 유전자 자체가 10개 pathway 중 어디에도 없음(이 논문의 oncogenic signaling
  pathway 분류 범위 밖): {hotspot_comparison['gene_absent_count']}개

### 일치한 위치

| Gene | Position | 팀 reference AA |
|---|---:|---|
{match_lines if match_lines else '| (없음) | | |'}

### 유전자는 있지만 position이 다른 경우

| Gene | Position | 팀 reference AA |
|---|---:|---|
{position_unmatched_lines if position_unmatched_lines else '| (없음) | | |'}

### 유전자 자체가 10개 pathway 밖

| Gene | Position | 팀 reference AA |
|---|---:|---|
{gene_absent_lines if gene_absent_lines else '| (없음) | | |'}

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
"""


def distinct_genes_set(table: list[dict[str, object]]) -> set[str]:
    return {row["gene"] for row in table}


def main() -> None:
    panel_genes = load_panel_genes(TRAIN_PATH)
    cosmic_whitelist_genes = load_cosmic_whitelist_genes(COSMIC_WHITELIST_PATH)
    rows = load_pathway_rows(SOURCE_XLSX)
    table = build_catalog_table(rows, panel_genes, cosmic_whitelist_genes)
    coverage = summarize_pathway_coverage(table)
    hotspot_comparison = cross_validate_hotspots(table, EXTENDED_HOTSPOTS)

    write_catalog_csv(OUTPUT_CSV, table)
    source_sha256 = sha256_file(SOURCE_XLSX)
    markdown = render_markdown(
        source_sha256=source_sha256,
        panel_gene_count=len(panel_genes),
        cosmic_whitelist_count=len(cosmic_whitelist_genes),
        table=table,
        coverage=coverage,
        hotspot_comparison=hotspot_comparison,
    )
    OUTPUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DOC.write_text(markdown, encoding="utf-8")

    print(
        json.dumps(
            {
                "rows": len(table),
                "distinct_genes": len(distinct_genes_set(table)),
                "coverage": coverage,
                "hotspot_comparison": {
                    "matched_count": hotspot_comparison["matched_count"],
                    "position_unmatched_count": hotspot_comparison["position_unmatched_count"],
                    "gene_absent_count": hotspot_comparison["gene_absent_count"],
                },
                "output_csv": relative_posix(OUTPUT_CSV, ROOT),
                "output_doc": relative_posix(OUTPUT_DOC, ROOT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
