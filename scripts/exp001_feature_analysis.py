"""
EXP-001: COSMIC 보호 유전자(cosmic_protected_genes) 기반 Feature 보호 전략 분석

이슈: https://github.com/fabxoe/open_cancer/issues/12

data leakage 방지: 이 스크립트는 train.csv만 사용해서 변이율/통계를 계산한다.
test.csv는 결측치 패턴 확인(6번 항목)에만 사용하고, 어떠한 통계 계산(fit)에도
쓰지 않는다.

화이트리스트 파일: data/external/gene_whitelist_cosmic_subtype.csv
  컬럼: gene, in_COSMIC_CGC(bool), subtype_defining_marker(bool), mutation_rate_pct(float)
  - 340개 전부 in_COSMIC_CGC=True (COSMIC CGC 723개 ∩ 우리 4,384개 컬럼)
  - subtype_defining_marker=True: 특정 SUBCLASS를 구분짓는 대표 마커 유전자 (14개)
  - mutation_rate_pct: 화이트리스트 파일 자체에 이미 계산되어 있는 변이율(%).
    본 스크립트는 train.csv에서 직접 재계산한 값을 기준으로 쓰되, 두 값이
    일치하는지 검증 단계에서 대조한다.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ------------------------------------------------------------------
# 경로 설정 (레포 구조에 맞게 수정 필요)
# ------------------------------------------------------------------
TRAIN_PATH = Path("./data/raw/train.csv")
TEST_PATH = Path("./data/raw/test.csv")
COSMIC_LIST_PATH = Path("./data/external/gene_whitelist_cosmic_subtype.csv")

OUT_DIR = Path("./reports/EXP-001")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_cosmic_protected_genes() -> pd.DataFrame:
    """cosmic_protected_genes(gene_whitelist_cosmic_subtype.csv) 로드."""
    if not COSMIC_LIST_PATH.exists():
        raise FileNotFoundError(
            f"{COSMIC_LIST_PATH} 를 찾을 수 없습니다. "
            "COSMIC_LIST_PATH를 gene_whitelist_cosmic_subtype.csv 실제 경로로 수정하세요."
        )
    df = pd.read_csv(COSMIC_LIST_PATH)
    required_cols = {"gene", "in_COSMIC_CGC", "subtype_defining_marker", "mutation_rate_pct"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"화이트리스트 파일에 누락된 컬럼: {missing_cols}")
    return df


def main():
    train = pd.read_csv(TRAIN_PATH)
    test = pd.read_csv(TEST_PATH)

    gene_cols = [c for c in train.columns if c not in ("ID", "SUBCLASS")]
    assert len(gene_cols) == 4384, f"gene 컬럼 수가 예상과 다릅니다: {len(gene_cols)}"

    cosmic_df = load_cosmic_protected_genes()
    protected_set = set(cosmic_df["gene"]) & set(gene_cols)
    print(f"cosmic_protected_genes 교집합: {len(protected_set)}개 (파일 자체 행 수: {len(cosmic_df)})")
    if len(protected_set) != len(cosmic_df):
        print(
            "[WARNING] 화이트리스트 파일의 유전자 중 일부가 train 컬럼에 없습니다. "
            f"누락: {set(cosmic_df['gene']) - set(gene_cols)}"
        )

    # ------------------------------------------------------------------
    # 1) 전체 유전자 변이율 분포 (train만 사용, 직접 재계산)
    # ------------------------------------------------------------------
    mut_rate = (train[gene_cols] != "WT").mean().rename("mutation_rate")
    mut_rate_df = mut_rate.reset_index().rename(columns={"index": "gene"})
    mut_rate_df["is_cosmic_protected"] = mut_rate_df["gene"].isin(protected_set)
    mut_rate_df = mut_rate_df.merge(
        cosmic_df[["gene", "subtype_defining_marker", "mutation_rate_pct"]],
        on="gene", how="left"
    )
    mut_rate_df = mut_rate_df.sort_values("mutation_rate", ascending=False)
    mut_rate_df.to_csv(OUT_DIR / "mutation_rate_distribution.csv", index=False)

    print("\n=== 변이율 분포 요약 ===")
    print(mut_rate_df["mutation_rate"].describe())

    # 검증: 화이트리스트 파일에 이미 있던 mutation_rate_pct와 재계산값 대조
    check = mut_rate_df[mut_rate_df["is_cosmic_protected"]].copy()
    check["recomputed_pct"] = check["mutation_rate"] * 100
    mismatch = check[(check["recomputed_pct"] - check["mutation_rate_pct"]).abs() > 0.01]
    if len(mismatch) > 0:
        print(f"\n[WARNING] 화이트리스트 파일의 mutation_rate_pct와 재계산값이 다른 유전자 {len(mismatch)}개:")
        print(mismatch[["gene", "mutation_rate_pct", "recomputed_pct"]])
    else:
        print("\n화이트리스트 파일의 mutation_rate_pct와 train 재계산값 일치 확인 완료.")

    # ------------------------------------------------------------------
    # 2) cosmic_protected_genes vs 비화이트리스트 분포 비교
    # ------------------------------------------------------------------
    prot = mut_rate_df[mut_rate_df["is_cosmic_protected"]]["mutation_rate"]
    rest = mut_rate_df[~mut_rate_df["is_cosmic_protected"]]["mutation_rate"]

    summary = pd.DataFrame(
        {
            "group": ["cosmic_protected", "rest"],
            "n_genes": [len(prot), len(rest)],
            "mean_mutation_rate": [prot.mean(), rest.mean()],
            "median_mutation_rate": [prot.median(), rest.median()],
            "pct_below_1pct": [
                (prot < 0.01).mean() * 100 if len(prot) else np.nan,
                (rest < 0.01).mean() * 100 if len(rest) else np.nan,
            ],
            "pct_zero": [
                (prot == 0).mean() * 100 if len(prot) else np.nan,
                (rest == 0).mean() * 100 if len(rest) else np.nan,
            ],
        }
    )
    summary.to_csv(OUT_DIR / "whitelist_vs_rest_summary.csv", index=False)
    print("\n=== cosmic_protected vs rest 비교 ===")
    print(summary)

    # ------------------------------------------------------------------
    # 3) 화이트리스트 중 변이율 1% 미만 + subtype_defining_marker 매핑
    # ------------------------------------------------------------------
    low_mut_protected = mut_rate_df[
        mut_rate_df["is_cosmic_protected"] & (mut_rate_df["mutation_rate"] < 0.01)
    ].copy()
    low_mut_protected.to_csv(OUT_DIR / "whitelist_low_mutation.csv", index=False)
    print(f"\n화이트리스트 중 변이율 1% 미만: {len(low_mut_protected)}개")
    n_marker_in_low = low_mut_protected["subtype_defining_marker"].sum()
    print(f"  -> 그 중 subtype_defining_marker=True: {n_marker_in_low}개 "
          "(저변이율인데 특정 암종의 대표 마커인 경우 -> 보호 우선순위 최상위로 취급 권장)")

    # 화이트리스트인데 변이율이 아예 0%인 유전자 (train 기준 관측 자체가 없음)
    zero_mut_protected = mut_rate_df[
        mut_rate_df["is_cosmic_protected"] & (mut_rate_df["mutation_rate"] == 0)
    ]
    zero_mut_protected.to_csv(OUT_DIR / "whitelist_zero_mutation.csv", index=False)
    print(f"\n화이트리스트인데 train에서 변이율 0%(전부 WT): {len(zero_mut_protected)}개")
    if len(zero_mut_protected) > 0:
        print(zero_mut_protected[["gene", "subtype_defining_marker"]])
        print(
            "[NOTE] 이 유전자들은 '보호 규칙: 화이트리스트는 무조건 보호'를 그대로 적용하면 "
            "살아남지만, train에서 단 한 번도 관측되지 않아 feature로서 정보량이 사실상 없습니다. "
            "다만 test에서 발견될 가능성이 있으므로 임상적 중요도 근거로 유지할지, "
            "실질 정보량 근거로 제외할지는 팀 판단이 필요합니다 (완료 조건에 명시된 "
            "'근거를 남긴다'에 해당하는 항목)."
        )

    # ------------------------------------------------------------------
    # 4) 비화이트리스트인데 변이율 높은 유전자 (long gene bias 의심)
    # ------------------------------------------------------------------
    high_mut_nonwhitelist = mut_rate_df[
        (~mut_rate_df["is_cosmic_protected"]) & (mut_rate_df["mutation_rate"] > 0.03)
    ].sort_values("mutation_rate", ascending=False)
    high_mut_nonwhitelist.to_csv(OUT_DIR / "high_mutation_nonwhitelist.csv", index=False)
    print(f"\n비화이트리스트 고변이율(>3%) 유전자: {len(high_mut_nonwhitelist)}개")
    print(high_mut_nonwhitelist[["gene", "mutation_rate"]].head(15))
    print(
        "[TODO] 이 유전자들의 실제 단백질 길이(exon length)를 붙여서 "
        "변이율과의 상관관계를 확인하세요 (long gene bias 가설 검증). "
        "예: RYR2, SYNE1, PCLO, RYR1, SPTA1는 모두 알려진 초대형 유전자."
    )

    # ------------------------------------------------------------------
    # 5) 패널 부재 확인 (KRAS/NRAS/BAP1/PBRM1/SETD2)
    # ------------------------------------------------------------------
    missing_drivers = ["KRAS", "NRAS", "BAP1", "PBRM1", "SETD2"]
    absent = [g for g in missing_drivers if g not in gene_cols]
    print(f"\n패널에 없는 알려진 driver 유전자: {absent}")
    print(
        "[TODO] 이 유전자들이 driver로 알려진 암종(예: KRAS/NRAS-대장암/폐암, "
        "BAP1-신장암/중피종, PBRM1/SETD2-신장암)이 26개 SUBCLASS에 포함되는지 "
        "직접 확인하고, 해당 암종 예측 시 대체 신호(같은 pathway의 다른 유전자, 혹은 "
        "화이트리스트의 subtype_defining_marker 유전자 중 겹치는 암종)가 있는지 검토하세요."
    )

    # ------------------------------------------------------------------
    # 6) test 결측치 25개 컬럼과 화이트리스트 overlap 확인
    # ------------------------------------------------------------------
    test_missing = test[gene_cols].isnull().sum()
    test_missing = test_missing[test_missing > 0].sort_values(ascending=False)
    missing_report = test_missing.reset_index()
    missing_report.columns = ["gene", "missing_count"]
    missing_report["is_cosmic_protected"] = missing_report["gene"].isin(protected_set)
    missing_report.to_csv(OUT_DIR / "missing_value_report.csv", index=False)
    print(f"\ntest 결측 컬럼 {len(missing_report)}개 중 화이트리스트 포함: "
          f"{missing_report['is_cosmic_protected'].sum()}개")
    print(missing_report)

    # ------------------------------------------------------------------
    # 7) 보호 규칙 초안 적용 (임계값은 팀 논의 후 확정, 여기선 초안만)
    #    규칙: cosmic_protected_genes는 무조건 보호 / 그 외는 변이율 0%면 제거
    #    단, 화이트리스트이면서 변이율 0%인 경우는 별도 플래그(protect_review)로
    #    구분해서 팀 리뷰를 거치도록 함.
    # ------------------------------------------------------------------
    def decide(row):
        if row["is_cosmic_protected"]:
            if row["mutation_rate"] == 0:
                return "protect_review"  # 화이트리스트인데 관측 0 -> 리뷰 필요
            return "protect"
        return "drop" if row["mutation_rate"] == 0 else "keep"

    mut_rate_df["decision_draft"] = mut_rate_df.apply(decide, axis=1)
    mut_rate_df.to_csv(OUT_DIR / "protected_dropped_draft.csv", index=False)

    draft_counts = mut_rate_df["decision_draft"].value_counts()
    print("\n=== 보호 규칙 초안 적용 결과 (확정 전) ===")
    print(draft_counts)
    print(
        "\n[NEXT] 이 초안(protected_dropped_draft.csv)을 팀 리뷰 후 확정해서 "
        "protected_genes_final.csv / dropped_genes_final.csv로 분리 저장하고, "
        "EXPERIMENT_HISTORY.md에 EXP-001로 기록하세요. "
        "특히 'protect_review' 항목은 화이트리스트 근거만으로 자동 보호하지 말고 "
        "팀 논의를 거쳐 protect/drop 중 하나로 확정하세요."
    )


if __name__ == "__main__":
    main()
