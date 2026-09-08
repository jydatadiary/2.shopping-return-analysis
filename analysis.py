"""전처리된 쇼핑 주문 데이터의 반품률 표와 시각화를 생성합니다.

먼저 preprocessing.py를 실행한 뒤 다음 명령으로 실행합니다.
    python analysis.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "processed" / "return_analysis_data.csv"
TABLE_DIR = BASE_DIR / "outputs" / "tables"
CHART_DIR = BASE_DIR / "outputs" / "charts"
SUMMARY_PATH = BASE_DIR / "outputs" / "analysis_summary.md"

# 최종 조합 순위에는 주문이 100건 이상인 집단만 포함합니다.
MIN_COMBINATION_ORDERS = 100
MIN_PRODUCT_ORDERS = 100
MIN_PRODUCT_DISCOUNT_ORDERS = 100
MIN_NOTEBOOK_AGE_QUANTITY_ORDERS = 30

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
sns.set_theme(style="whitegrid", font="Malgun Gothic")


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            "전처리 데이터가 없습니다. 먼저 python preprocessing.py를 실행하세요.\n"
            f"필요한 파일: {DATA_PATH}"
        )
    df = pd.read_csv(DATA_PATH, parse_dates=["OrderDate"])
    required = {
        "Status", "IsReturned", "ProductName", "Category", "Discount",
        "Quantity", "OrderValue", "Age", "CustomerSegment",
        "PaymentMethod", "OrderYearMonth",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"분석에 필요한 열이 없습니다: {sorted(missing)}")
    return df


def return_rate_table(df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    table = (
        df.dropna(subset=group_columns)
        .groupby(group_columns, observed=True)
        .agg(
            주문수=("IsReturned", "size"),
            반품수=("IsReturned", "sum"),
            반품률=("IsReturned", "mean"),
        )
        .reset_index()
    )
    table["완료수"] = table["주문수"] - table["반품수"]
    table["반품률(%)"] = (table["반품률"] * 100).round(2)
    return table.sort_values(
        ["반품률", "주문수"], ascending=[False, False]
    ).reset_index(drop=True)


def save_rate_chart(
    table: pd.DataFrame,
    category: str,
    title: str,
    filename: str,
    color: str = "#4C78A8",
    top_n: int | None = None,
) -> None:
    plot_df = table.head(top_n).copy() if top_n else table.copy()
    plot_df = plot_df.sort_values("반품률(%)", ascending=True)
    plot_df["표시명"] = plot_df[category].astype(str)

    height = max(5.5, len(plot_df) * 0.55)
    fig, ax = plt.subplots(figsize=(11, height))
    sns.barplot(data=plot_df, x="반품률(%)", y="표시명", color=color, ax=ax)
    ax.set_title(title, fontsize=16, pad=14)
    ax.set_xlabel("반품률 (%)")
    ax.set_ylabel("")
    max_rate = max(float(plot_df["반품률(%)"].max()), 1)
    ax.set_xlim(0, max_rate * 1.28)

    for patch, (_, row) in zip(ax.patches, plot_df.iterrows()):
        ax.text(
            patch.get_width() + max_rate * 0.02,
            patch.get_y() + patch.get_height() / 2,
            f"{row['반품률(%)']:.2f}% ({int(row['반품수'])}/{int(row['주문수'])}건)",
            va="center",
            fontsize=9,
        )

    fig.tight_layout()
    fig.savefig(CHART_DIR / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def analyze_overall_status(df: pd.DataFrame) -> pd.DataFrame:
    table = (
        df["Status"].value_counts()
        .rename_axis("상태")
        .reset_index(name="주문수")
    )
    table["비율(%)"] = (table["주문수"] / len(df) * 100).round(2)
    table.to_csv(TABLE_DIR / "00_전체_완료_반품_비율.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    sns.barplot(data=table, x="상태", y="비율(%)", hue="상태", legend=False,
                palette={"Completed": "#59A14F", "Returned": "#E15759"}, ax=ax)
    ax.set(title="전체 완료·반품 비율", xlabel="", ylabel="비율 (%)", ylim=(0, 105))
    for patch, (_, row) in zip(ax.patches, table.iterrows()):
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            patch.get_height() + 2,
            f"{row['비율(%)']:.2f}%\n({int(row['주문수']):,}건)",
            ha="center",
        )
    fig.tight_layout()
    fig.savefig(CHART_DIR / "00_전체_완료_반품_비율.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return table


def analyze_product_counts(df: pd.DataFrame) -> pd.DataFrame:
    table = (
        df[df["IsReturned"] == 1]
        .groupby("ProductName", observed=True)
        .size()
        .reset_index(name="반품수")
        .sort_values("반품수", ascending=False)
        .reset_index(drop=True)
    )
    table.to_csv(TABLE_DIR / "01_상품별_반품건수.csv", index=False, encoding="utf-8-sig")
    top10 = table.head(10).sort_values("반품수", ascending=True)

    fig, ax = plt.subplots(figsize=(11, 7))
    sns.barplot(data=top10, x="반품수", y="ProductName", color="#E15759", ax=ax)
    ax.set(title="상품별 반품 건수 TOP 10", xlabel="반품 건수", ylabel="")
    for patch in ax.patches:
        ax.text(patch.get_width() + 2, patch.get_y() + patch.get_height() / 2,
                f"{int(patch.get_width())}건", va="center")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "01_상품별_반품건수_TOP10.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return table


def analyze_product_rates(df: pd.DataFrame) -> pd.DataFrame:
    table = return_rate_table(df, ["ProductName"])
    table = table[table["주문수"] >= MIN_PRODUCT_ORDERS].reset_index(drop=True)
    table.to_csv(TABLE_DIR / "02_상품별_반품률.csv", index=False, encoding="utf-8-sig")
    save_rate_chart(table, "ProductName", "상품별 반품률 TOP 10",
                    "02_상품별_반품률_TOP10.png", "#F28E2B", top_n=10)
    return table


def analyze_simple_rates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    analyses = [
        ("Category", "03_카테고리별_반품률", "카테고리별 반품률", "#4C78A8"),
        ("DiscountLabel", "04_할인율별_반품률", "할인율별 반품률", "#F28E2B"),
        ("QuantityLabel", "05_주문수량별_반품률", "주문 수량별 반품률", "#76B7B2"),
        ("OrderValueGroup", "06_주문금액구간별_반품률", "주문 금액 구간별 반품률", "#B279A2"),
        ("AgeGroup", "07_연령대별_반품률", "연령대별 반품률", "#59A14F"),
        ("CustomerSegment", "08_고객등급별_반품률", "고객 등급별 반품률", "#EDC948"),
        ("PaymentMethod", "09_결제수단별_반품률", "결제수단별 반품률", "#9C755F"),
    ]
    results: dict[str, pd.DataFrame] = {}
    for column, filename, title, color in analyses:
        table = return_rate_table(df, [column])
        table.to_csv(TABLE_DIR / f"{filename}.csv", index=False, encoding="utf-8-sig")
        save_rate_chart(table, column, title, f"{filename}.png", color)
        results[column] = table
    return results


def analyze_monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    table = return_rate_table(df, ["OrderYearMonth"]).sort_values("OrderYearMonth")
    table.to_csv(TABLE_DIR / "10_월별_반품률_추이.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(14, 6))
    sns.lineplot(data=table, x="OrderYearMonth", y="반품률(%)", marker="o",
                 color="#4C78A8", linewidth=2, ax=ax)
    ax.set_title("월별 반품률 추이", fontsize=16, pad=14)
    ax.set_xlabel("주문 연월")
    ax.set_ylabel("반품률 (%)")
    ax.tick_params(axis="x", rotation=60)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "10_월별_반품률_추이.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return table


def analyze_combinations(df: pd.DataFrame) -> pd.DataFrame:
    columns = ["ProductName", "DiscountLabel", "QuantityLabel", "CustomerSegment"]
    table = return_rate_table(df, columns)
    table = table[table["주문수"] >= MIN_COMBINATION_ORDERS].reset_index(drop=True)
    table.to_csv(TABLE_DIR / "11_최종_조합별_반품률.csv", index=False, encoding="utf-8-sig")

    top10 = table.head(10).copy()
    if top10.empty:
        return table
    top10["조건"] = (
        top10["ProductName"].astype(str)
        + " / 할인 " + top10["DiscountLabel"].astype(str)
        + " / " + top10["QuantityLabel"].astype(str)
        + " / " + top10["CustomerSegment"].astype(str)
    )
    save_rate_chart(top10, "조건",
                    f"상품·할인율·수량·고객 등급 조합별 반품률 TOP 10\n"
                    f"조건별 주문 {MIN_COMBINATION_ORDERS}건 이상",
                    "11_최종_조합별_반품률_TOP10.png", "#E15759")
    return table


def analyze_discount_focus(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """할인율 효과를 상품별로 나누고 상품 구성 차이를 보정해 확인합니다."""
    discount_order = sorted(df["Discount"].dropna().unique())
    product_order = sorted(df["ProductName"].dropna().unique())

    # 1) 상품 × 할인율 반품률 히트맵
    product_discount = return_rate_table(df, ["ProductName", "Discount"])
    product_discount["표시대상"] = (
        product_discount["주문수"] >= MIN_PRODUCT_DISCOUNT_ORDERS
    )
    product_discount.to_csv(
        TABLE_DIR / "12_상품_할인율별_반품률.csv", index=False, encoding="utf-8-sig"
    )
    heatmap_data = (
        product_discount[product_discount["표시대상"]]
        .pivot(index="ProductName", columns="Discount", values="반품률(%)")
        .reindex(index=product_order, columns=discount_order)
    )
    heatmap_data.columns = [f"{value:g}%" for value in heatmap_data.columns]

    fig, ax = plt.subplots(figsize=(11, 10))
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt=".2f",
        cmap="YlOrRd",
        linewidths=0.5,
        cbar_kws={"label": "반품률 (%)"},
        ax=ax,
    )
    ax.set_title(
        f"상품 × 할인율 반품률\n상품·할인율별 주문 {MIN_PRODUCT_DISCOUNT_ORDERS}건 이상",
        fontsize=16,
        pad=14,
    )
    ax.set_xlabel("할인율")
    ax.set_ylabel("상품")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "12_상품_할인율_반품률_히트맵.png", dpi=180,
                bbox_inches="tight")
    plt.close(fig)

    # 2) 상품별 10% 할인 반품률과 해당 상품 전체 반품률의 차이
    product_overall = return_rate_table(df, ["ProductName"])[
        ["ProductName", "주문수", "반품수", "반품률", "반품률(%)"]
    ].rename(columns={
        "주문수": "상품전체_주문수",
        "반품수": "상품전체_반품수",
        "반품률": "상품전체_반품률",
        "반품률(%)": "상품전체_반품률(%)",
    })
    ten_percent = product_discount[product_discount["Discount"] == 10][
        ["ProductName", "주문수", "반품수", "반품률", "반품률(%)"]
    ].rename(columns={
        "주문수": "10%할인_주문수",
        "반품수": "10%할인_반품수",
        "반품률": "10%할인_반품률",
        "반품률(%)": "10%할인_반품률(%)",
    })
    ten_difference = product_overall.merge(ten_percent, on="ProductName", how="inner")
    ten_difference = ten_difference[
        ten_difference["10%할인_주문수"] >= MIN_PRODUCT_DISCOUNT_ORDERS
    ].copy()
    ten_difference["차이(%p)"] = (
        ten_difference["10%할인_반품률(%)"]
        - ten_difference["상품전체_반품률(%)"]
    ).round(2)
    ten_difference = ten_difference.sort_values("차이(%p)", ascending=False)
    ten_difference.to_csv(
        TABLE_DIR / "13_상품별_10퍼센트할인_반품률차이.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plot_difference = ten_difference.sort_values("차이(%p)")
    colors = ["#E15759" if value > 0 else "#4C78A8"
              for value in plot_difference["차이(%p)"]]
    fig, ax = plt.subplots(figsize=(11, 9))
    bars = ax.barh(plot_difference["ProductName"], plot_difference["차이(%p)"],
                   color=colors)
    ax.axvline(0, color="#333333", linewidth=1)
    ax.set_title("상품별 10% 할인 반품률에서 상품 전체 반품률을 뺀 차이",
                 fontsize=16, pad=14)
    ax.set_xlabel("반품률 차이 (%p)")
    ax.set_ylabel("")
    offset = max(abs(plot_difference["차이(%p)"]).max() * 0.03, 0.02)
    for bar, value in zip(bars, plot_difference["차이(%p)"]):
        ax.text(
            value + (offset if value >= 0 else -offset),
            bar.get_y() + bar.get_height() / 2,
            f"{value:+.2f}%p",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9,
        )
    ax.margins(x=0.13)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "13_상품별_10퍼센트할인_반품률차이.png", dpi=180,
                bbox_inches="tight")
    plt.close(fig)

    # 3) 단순 반품률과 상품 구성을 전체 주문 비중으로 통일한 보정 반품률
    raw_discount = return_rate_table(df, ["Discount"])[
        ["Discount", "주문수", "반품수", "반품률", "반품률(%)"]
    ].rename(columns={"반품률": "단순반품률", "반품률(%)": "단순반품률(%)"})
    product_weights = (
        df["ProductName"].value_counts(normalize=True).rename("상품가중치").reset_index()
    )
    valid_rates = product_discount[
        product_discount["주문수"] >= MIN_PRODUCT_DISCOUNT_ORDERS
    ].merge(product_weights, on="ProductName", how="left")
    valid_rates["가중반품률"] = valid_rates["반품률"] * valid_rates["상품가중치"]
    adjusted = (
        valid_rates.groupby("Discount", as_index=False)
        .agg(가중반품률합=("가중반품률", "sum"), 사용가중치=("상품가중치", "sum"))
    )
    adjusted["상품구성보정반품률"] = adjusted["가중반품률합"] / adjusted["사용가중치"]
    comparison = raw_discount.merge(
        adjusted[["Discount", "상품구성보정반품률", "사용가중치"]],
        on="Discount",
        how="left",
    )
    comparison["상품구성보정반품률(%)"] = (
        comparison["상품구성보정반품률"] * 100
    ).round(2)
    comparison["차이(%p)"] = (
        comparison["상품구성보정반품률(%)"] - comparison["단순반품률(%)"]
    ).round(2)
    comparison = comparison.sort_values("Discount")
    comparison.to_csv(
        TABLE_DIR / "14_할인율별_단순_상품구성보정_반품률.csv",
        index=False,
        encoding="utf-8-sig",
    )

    long_comparison = comparison.melt(
        id_vars="Discount",
        value_vars=["단순반품률(%)", "상품구성보정반품률(%)"],
        var_name="계산방식",
        value_name="반품률(%)",
    )
    long_comparison["계산방식"] = long_comparison["계산방식"].map({
        "단순반품률(%)": "단순 반품률",
        "상품구성보정반품률(%)": "상품 구성 보정 반품률",
    })
    long_comparison["할인율"] = long_comparison["Discount"].map(lambda x: f"{x:g}%")
    fig, ax = plt.subplots(figsize=(11, 6.5))
    sns.barplot(
        data=long_comparison,
        x="할인율",
        y="반품률(%)",
        hue="계산방식",
        palette=["#4C78A8", "#F28E2B"],
        ax=ax,
    )
    ax.set_title("할인율별 단순 반품률과 상품 구성 보정 반품률", fontsize=16, pad=14)
    ax.set_xlabel("할인율")
    ax.set_ylabel("반품률 (%)")
    ax.set_ylim(0, long_comparison["반품률(%)"].max() * 1.25)
    for container in ax.containers:
        ax.bar_label(container, fmt="%.2f%%", padding=3, fontsize=8)
    ax.legend(title="")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "14_할인율별_단순_상품구성보정_반품률.png", dpi=180,
                bbox_inches="tight")
    plt.close(fig)

    return {
        "product_discount": product_discount,
        "ten_difference": ten_difference,
        "adjusted_comparison": comparison,
    }


def analyze_notebook_focus(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """공책(Notebook)의 연령대와 구매 수량별 반품 패턴을 분석합니다."""
    notebook = df[df["ProductName"] == "Notebook"].copy()
    age_order = ["18~29세", "30대", "40대", "50대", "60세 이상"]
    notebook["QuantityGroup"] = notebook["Quantity"].map(
        lambda value: "1개" if value == 1 else ("2개" if value == 2 else "3개 이상")
    )
    quantity_order = ["1개", "2개", "3개 이상"]

    # 1) 연령대별 Notebook 주문·반품 건수
    age_rates = return_rate_table(notebook, ["AgeGroup"])
    age_rates.to_csv(
        TABLE_DIR / "15_Notebook_연령대별_반품률.csv",
        index=False,
        encoding="utf-8-sig",
    )
    plot_age = age_rates.set_index("AgeGroup").reindex(age_order).reset_index()
    count_long = plot_age.melt(
        id_vars="AgeGroup",
        value_vars=["완료수", "반품수"],
        var_name="상태",
        value_name="건수",
    )
    fig, ax = plt.subplots(figsize=(11, 6.5))
    sns.barplot(
        data=count_long, x="AgeGroup", y="건수", hue="상태",
        order=age_order, hue_order=["완료수", "반품수"],
        palette={"완료수": "#4C78A8", "반품수": "#E15759"},
        ax=ax,
    )
    ax.set_title("공책(Notebook) 구매자의 연령대별 완료·반품 건수", fontsize=16, pad=14)
    ax.set_xlabel("연령대")
    ax.set_ylabel("주문 건수")
    ax.legend(title="")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "15_Notebook_연령대별_완료_반품건수.png", dpi=180,
                bbox_inches="tight")
    plt.close(fig)

    # 2) 연령대별 반품률
    fig, ax = plt.subplots(figsize=(11, 6.5))
    bars = ax.bar(plot_age["AgeGroup"], plot_age["반품률(%)"], color="#59A14F")
    notebook_rate = notebook["IsReturned"].mean() * 100
    ax.axhline(notebook_rate, color="#555555", linestyle="--", linewidth=1.5,
               label=f"공책 전체 평균 {notebook_rate:.2f}%")
    ax.set_title("공책(Notebook) 구매자의 연령대별 반품률", fontsize=16, pad=14)
    ax.set_xlabel("연령대")
    ax.set_ylabel("반품률 (%)")
    ax.set_ylim(0, max(plot_age["반품률(%)"].max(), notebook_rate) * 1.35)
    for bar, (_, row) in zip(bars, plot_age.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.08,
                f"{row['반품률(%)']:.2f}%\n({int(row['반품수'])}/{int(row['주문수'])}건)",
                ha="center", va="bottom", fontsize=9)
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHART_DIR / "16_Notebook_연령대별_반품률.png", dpi=180,
                bbox_inches="tight")
    plt.close(fig)

    # 3) 연령대 × 구매수량(1개·2개·3개 이상) 반품률
    age_quantity = return_rate_table(notebook, ["AgeGroup", "QuantityGroup"])
    age_quantity["표시대상"] = (
        age_quantity["주문수"] >= MIN_NOTEBOOK_AGE_QUANTITY_ORDERS
    )
    age_quantity.to_csv(
        TABLE_DIR / "17_Notebook_연령대_수량별_반품률.csv",
        index=False,
        encoding="utf-8-sig",
    )
    heatmap = (
        age_quantity[age_quantity["표시대상"]]
        .pivot(index="AgeGroup", columns="QuantityGroup", values="반품률(%)")
        .reindex(index=age_order, columns=quantity_order)
    )
    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(
        heatmap, annot=True, fmt=".2f", cmap="YlOrRd", linewidths=0.7,
        cbar_kws={"label": "반품률 (%)"}, ax=ax,
    )
    ax.set_title(
        "공책(Notebook) 연령대 × 구매수량별 반품률\n"
        f"조합별 주문 {MIN_NOTEBOOK_AGE_QUANTITY_ORDERS}건 이상",
        fontsize=16, pad=14,
    )
    ax.set_xlabel("구매 수량")
    ax.set_ylabel("연령대")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "17_Notebook_연령대_수량별_반품률_히트맵.png",
                dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 4) 연령대 × 할인율 반품률
    age_discount = return_rate_table(notebook, ["AgeGroup", "Discount"])
    age_discount["표시대상"] = (
        age_discount["주문수"] >= MIN_NOTEBOOK_AGE_QUANTITY_ORDERS
    )
    age_discount.to_csv(
        TABLE_DIR / "18_Notebook_연령대_할인율별_반품률.csv",
        index=False,
        encoding="utf-8-sig",
    )
    discount_order = sorted(notebook["Discount"].dropna().unique())
    discount_heatmap = (
        age_discount[age_discount["표시대상"]]
        .pivot(index="AgeGroup", columns="Discount", values="반품률(%)")
        .reindex(index=age_order, columns=discount_order)
    )
    discount_heatmap.columns = [f"{value:g}%" for value in discount_heatmap.columns]
    fig, ax = plt.subplots(figsize=(11, 7))
    sns.heatmap(
        discount_heatmap, annot=True, fmt=".2f", cmap="YlOrRd", linewidths=0.7,
        cbar_kws={"label": "반품률 (%)"}, ax=ax,
    )
    ax.set_title(
        "공책(Notebook) 연령대 × 할인율별 반품률\n"
        f"조합별 주문 {MIN_NOTEBOOK_AGE_QUANTITY_ORDERS}건 이상",
        fontsize=16, pad=14,
    )
    ax.set_xlabel("할인율")
    ax.set_ylabel("연령대")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "18_Notebook_연령대_할인율별_반품률_히트맵.png",
                dpi=180, bbox_inches="tight")
    plt.close(fig)

    return {
        "age_rates": age_rates,
        "age_quantity": age_quantity,
        "age_discount": age_discount,
    }


def add_analysis_groups(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["DiscountLabel"] = result["Discount"].map(lambda value: f"{value:g}%")
    result["QuantityLabel"] = result["Quantity"].map(lambda value: f"{int(value)}개")
    result["OrderValueGroup"] = pd.cut(
        result["OrderValue"],
        bins=[0, 20, 50, 100, 200, float("inf")],
        labels=["20 이하", "20 초과~50 이하", "50 초과~100 이하",
                "100 초과~200 이하", "200 초과"],
        include_lowest=True,
    )
    result["AgeGroup"] = pd.cut(
        result["Age"],
        bins=[17, 29, 39, 49, 59, float("inf")],
        labels=["18~29세", "30대", "40대", "50대", "60세 이상"],
        include_lowest=True,
    )
    return result


def create_summary(
    df: pd.DataFrame,
    product_counts: pd.DataFrame,
    product_rates: pd.DataFrame,
    simple_rates: dict[str, pd.DataFrame],
    combinations: pd.DataFrame,
) -> None:
    highest_count = product_counts.iloc[0]
    highest_product_rate = product_rates.iloc[0]
    highest_category = simple_rates["Category"].iloc[0]
    lines = [
        "# 반품 분석 요약", "",
        f"- 분석 주문: {len(df):,}건",
        f"- 반품 주문: {int(df['IsReturned'].sum()):,}건",
        f"- 전체 관찰 반품률: {df['IsReturned'].mean() * 100:.2f}%", "",
        "## 주요 결과", "",
        f"- 반품 건수가 가장 많은 상품은 `{highest_count['ProductName']}`이며 "
        f"반품은 {int(highest_count['반품수']):,}건입니다.",
        f"- 최소 {MIN_PRODUCT_ORDERS}건 이상 판매된 상품 중 반품률이 가장 높은 상품은 "
        f"`{highest_product_rate['ProductName']}`이며 반품률은 "
        f"{highest_product_rate['반품률(%)']:.2f}%입니다 "
        f"({int(highest_product_rate['반품수'])}/{int(highest_product_rate['주문수'])}건).",
        f"- 반품률이 가장 높은 카테고리는 `{highest_category['Category']}`이며 "
        f"반품률은 {highest_category['반품률(%)']:.2f}%입니다.", "",
        "## 최종 조합 결과", "",
    ]
    if combinations.empty:
        lines.append(f"주문 {MIN_COMBINATION_ORDERS}건 이상인 조합이 없습니다.")
    else:
        best = combinations.iloc[0]
        lines.append(
            f"주문 {MIN_COMBINATION_ORDERS}건 이상인 집단을 비교한 결과, "
            f"`{best['ProductName']}`·할인 `{best['DiscountLabel']}`·"
            f"수량 `{best['QuantityLabel']}`·고객 등급 `{best['CustomerSegment']}` "
            f"조합에서 가장 높은 반품률 {best['반품률(%)']:.2f}%가 관찰됐습니다 "
            f"({int(best['반품수'])}/{int(best['주문수'])}건)."
        )
    lines += [
        "", "## 해석 시 주의", "",
        "이 결과는 주문 조건과 반품 사이에서 관찰된 연관성을 나타냅니다. "
        "데이터에 반품 사유가 없으므로 특정 조건이 반품의 직접적인 원인이라고 "
        "단정할 수 없습니다.",
    ]
    summary = "\n".join(lines)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\n표 저장 위치: {TABLE_DIR}")
    print(f"그래프 저장 위치: {CHART_DIR}")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    df = add_analysis_groups(load_data())

    analyze_overall_status(df)
    product_counts = analyze_product_counts(df)
    product_rates = analyze_product_rates(df)
    simple_rates = analyze_simple_rates(df)
    analyze_monthly_trend(df)
    combinations = analyze_combinations(df)
    analyze_discount_focus(df)
    analyze_notebook_focus(df)
    create_summary(df, product_counts, product_rates, simple_rates, combinations)


if __name__ == "__main__":
    main()
