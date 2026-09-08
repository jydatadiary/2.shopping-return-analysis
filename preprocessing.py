"""쇼핑 주문 데이터의 반품 분석용 전처리.

원본 CSV는 수정하지 않습니다. 실행 결과는 data/processed와 reports에 저장됩니다.

실행:
    python preprocessing.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
RAW_PATH = BASE_DIR / "data" / "raw" / "clean_final_data.csv"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORT_DIR = BASE_DIR / "reports"
PROCESSED_PATH = PROCESSED_DIR / "return_analysis_data.csv"
INVALID_QUANTITY_PATH = REPORT_DIR / "excluded_invalid_quantity.csv"
SUMMARY_PATH = REPORT_DIR / "preprocessing_summary.md"

REQUIRED_COLUMNS = {
    "OrderID",
    "CustomerID",
    "OrderDate",
    "ProductID",
    "Quantity",
    "Discount",
    "PaymentMethod",
    "Status",
    "Age",
    "City",
    "SignupDate",
    "CustomerSegment",
    "ProductName",
    "Category",
    "UnitPrice",
    "Sales",
    "OrderValue",
}

DAY_NAME_KO = {
    "Monday": "월요일",
    "Tuesday": "화요일",
    "Wednesday": "수요일",
    "Thursday": "목요일",
    "Friday": "금요일",
    "Saturday": "토요일",
    "Sunday": "일요일",
}


def load_raw_data() -> pd.DataFrame:
    """원본 데이터를 읽고 필수 열을 확인합니다."""
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            "원본 CSV를 찾을 수 없습니다. 다음 위치를 확인하세요:\n"
            f"{RAW_PATH}"
        )

    raw_df = pd.read_csv(RAW_PATH)
    missing_columns = REQUIRED_COLUMNS - set(raw_df.columns)
    if missing_columns:
        raise ValueError(f"필수 열이 없습니다: {sorted(missing_columns)}")
    return raw_df


def preprocess(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """반품 분석 기준에 맞게 복사본을 전처리합니다."""
    df = raw_df.copy()
    audit: dict[str, int | float | bool] = {
        "raw_rows": len(df),
        "raw_columns": len(df.columns),
    }

    # 완전히 동일한 중복 행 제거
    audit["duplicate_rows"] = int(df.duplicated().sum())
    df = df.drop_duplicates().copy()

    # 날짜 변환: 원본 날짜는 유지하고 분석용 파생변수를 추가
    df["OrderDate"] = pd.to_datetime(df["OrderDate"], errors="coerce")
    df["SignupDate"] = pd.to_datetime(df["SignupDate"], errors="coerce")
    audit["invalid_order_dates"] = int(df["OrderDate"].isna().sum())
    audit["invalid_signup_dates"] = int(df["SignupDate"].isna().sum())
    audit["signup_after_order"] = int((df["SignupDate"] > df["OrderDate"]).sum())

    df["OrderYear"] = df["OrderDate"].dt.year.astype("Int64")
    df["OrderMonth"] = df["OrderDate"].dt.month.astype("Int64")
    df["OrderYearMonth"] = df["OrderDate"].dt.to_period("M").astype("string")
    df["OrderDayOfWeek"] = df["OrderDate"].dt.day_name().map(DAY_NAME_KO)

    # Sales와 OrderValue 중복 및 주문 금액 계산식 점검
    audit["sales_equals_order_value"] = bool(df["Sales"].equals(df["OrderValue"]))
    expected_value = (
        df["UnitPrice"] * df["Quantity"] * (1 - df["Discount"] / 100)
    )
    audit["order_value_within_rounding_rate"] = round(
        float(((df["OrderValue"] - expected_value).abs() <= 0.51).mean() * 100), 2
    )

    # 취소는 반품과 발생 과정이 다르므로 이번 분석에서 제외
    cancelled_count = int((df["Status"] == "Cancelled").sum())
    audit["excluded_cancelled"] = cancelled_count
    df = df[df["Status"].isin(["Completed", "Returned"])].copy()

    # 수량이 0 이하인 주문은 정상 구매로 보기 어려워 별도 저장 후 제외
    invalid_quantity = df[df["Quantity"] <= 0].copy()
    audit["excluded_invalid_quantity"] = len(invalid_quantity)
    df = df[df["Quantity"] > 0].copy()

    # 반품 여부: 1은 반품, 0은 정상 완료
    df["IsReturned"] = (df["Status"] == "Returned").astype(int)

    # 고객별 반복 주문 분석을 위해 CustomerID는 유지
    # ProductID는 ProductName과 1:1이고, Sales는 OrderValue와 중복
    # SignupDate는 주문일보다 늦은 값이 많아 이번 분석에서는 제외
    df = df.drop(columns=["ProductID", "Sales", "SignupDate"])

    preferred_order = [
        "OrderID",
        "CustomerID",
        "OrderDate",
        "OrderYear",
        "OrderMonth",
        "OrderYearMonth",
        "OrderDayOfWeek",
        "Status",
        "IsReturned",
        "ProductName",
        "Category",
        "UnitPrice",
        "Quantity",
        "Discount",
        "OrderValue",
        "PaymentMethod",
        "CustomerSegment",
        "Age",
        "City",
    ]
    remaining_columns = [c for c in df.columns if c not in preferred_order]
    df = df[preferred_order + remaining_columns]

    audit["processed_rows"] = len(df)
    audit["processed_columns"] = len(df.columns)
    audit["completed_rows"] = int((df["Status"] == "Completed").sum())
    audit["returned_rows"] = int((df["Status"] == "Returned").sum())
    audit["return_rate"] = round(float(df["IsReturned"].mean() * 100), 2)
    return df, invalid_quantity, audit


def build_summary(audit: dict) -> str:
    """전처리 과정과 기준을 Markdown으로 기록합니다."""
    return f"""# 전처리 요약

## 원본 보존

- 원본 파일: `data/raw/clean_final_data.csv`
- 원본 행: {audit['raw_rows']:,}개
- 원본 열: {audit['raw_columns']:,}개
- 원본 CSV는 수정하지 않고 복사본에서 전처리했습니다.

## 처리 내용

- 완전 중복 행 {audit['duplicate_rows']:,}개를 제거했습니다.
- 취소 주문 {audit['excluded_cancelled']:,}개를 반품 분석에서 제외했습니다.
- 수량이 0 이하인 주문 {audit['excluded_invalid_quantity']:,}개를 별도 보관 후 제외했습니다.
- `Status = Returned`이면 `IsReturned = 1`, 정상 완료이면 0으로 변환했습니다.
- `OrderDate`는 유지하고 연도·월·연월·요일 변수를 추가했습니다.
- `ProductID`는 상품명과 중복되어 분석용 데이터에서 제외했습니다.
- `Sales`는 `OrderValue`와 완전히 같은 값인지 확인 후 제외했습니다.
- `SignupDate`는 주문일보다 늦은 행이 {audit['signup_after_order']:,}개여서 제외했습니다.
- 반복 주문 고객 분석 가능성을 위해 `CustomerID`는 유지했습니다.

## 데이터 품질 점검

- 해석하지 못한 주문일: {audit['invalid_order_dates']:,}개
- 해석하지 못한 가입일: {audit['invalid_signup_dates']:,}개
- `Sales`와 `OrderValue` 완전 일치: {audit['sales_equals_order_value']}
- 주문 금액 계산식과 반올림 오차 이내 일치: {audit['order_value_within_rounding_rate']:.2f}%

## 전처리 결과

- 분석 대상 행: {audit['processed_rows']:,}개
- 정상 완료: {audit['completed_rows']:,}개
- 반품: {audit['returned_rows']:,}개
- 관찰 반품률: {audit['return_rate']:.2f}%

`Cancelled`는 상품 수령 후 반품과 발생 과정이 다르므로 이번 분석에서 제외했습니다. 이 반품률은 완료와 반품 주문만을 분모로 계산한 관찰 비율입니다.
"""


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    raw_df = load_raw_data()
    processed_df, invalid_quantity, audit = preprocess(raw_df)

    processed_df.to_csv(PROCESSED_PATH, index=False, encoding="utf-8-sig")
    invalid_quantity.to_csv(
        INVALID_QUANTITY_PATH, index=False, encoding="utf-8-sig"
    )
    summary = build_summary(audit)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    print(summary)
    print(f"\n전처리 데이터: {PROCESSED_PATH}")
    print(f"전처리 보고서: {SUMMARY_PATH}")


def run_start_button() -> None:
    """버튼 클릭 시 전처리를 실행하고 결과를 메시지로 보여줍니다."""
    try:
        main()
    except Exception as exc:
        messagebox.showerror("전처리 오류", f"작업 중 오류가 발생했습니다.\n\n{exc}")
        return

    messagebox.showinfo(
        "전처리 완료",
        "반품 분석용 전처리가 완료되었습니다.\n"
        f"결과 파일: {PROCESSED_PATH}\n"
        f"요약 보고서: {SUMMARY_PATH}",
    )


def launch_gui() -> None:
    """시작 버튼이 있는 간단한 GUI를 엽니다."""
    root = tk.Tk()
    root.title("쇼핑 반품 분석")
    root.geometry("320x170")
    root.resizable(False, False)

    label = tk.Label(
        root,
        text="반품 분석 전처리를 시작합니다.",
        font=("Malgun Gothic", 12),
        pady=18,
    )
    label.pack()

    button = tk.Button(
        root,
        text="시작",
        width=16,
        height=2,
        font=("Malgun Gothic", 11, "bold"),
        command=run_start_button,
    )
    button.pack(pady=10)

    root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="쇼핑 반품 분석 전처리 도구")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="시작 버튼이 있는 그래픽 창을 엽니다.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.gui:
        launch_gui()
    else:
        main()
