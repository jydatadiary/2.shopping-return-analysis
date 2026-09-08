# 쇼핑 주문 반품 분석

원본 CSV를 수정하지 않고 Python 코드에서 반품 분석용 데이터를 만드는 프로젝트입니다.

## 실행

VS Code에서 이 폴더를 연 뒤 터미널에 입력합니다.

```powershell
python -m pip install -r requirements.txt
python preprocessing.py
python analysis.py
```

## 폴더 구성

```text
shopping-return-analysis/
├── preprocessing.py
├── analysis.py
├── requirements.txt
├── data/
│   ├── raw/
│   │   └── clean_final_data.csv
│   └── processed/
│       └── return_analysis_data.csv
├── reports/
│   ├── preprocessing_summary.md
│   └── excluded_invalid_quantity.csv
└── outputs/
    ├── tables/              # 분석 결과 CSV 표
    ├── charts/              # 분석 결과 PNG 그래프
    └── analysis_summary.md  # 자동 분석 요약
```

## 전처리 기준

- 원본 CSV는 수정하지 않습니다.
- 취소 주문은 반품과 구분하여 분석에서 제외합니다.
- 수량이 0 이하인 주문은 별도 파일에 보관하고 제외합니다.
- 주문 날짜에서 연도, 월, 연월, 요일을 생성합니다.
- `Returned`를 1, `Completed`를 0으로 변환한 `IsReturned`를 생성합니다.
- `ProductID`, 중복된 `Sales`, 날짜 오류가 많은 `SignupDate`는 분석 데이터에서 제외합니다.
- 반복 구매 고객 분석을 위해 `CustomerID`는 유지합니다.

## 시각화 분석

`analysis.py`는 전체 완료·반품 비율과 상품·카테고리·할인율·수량·주문 금액·연령대·고객 등급·결제수단·월별 반품률을 생성합니다. 최종 분석에서는 상품, 할인율, 주문 수량, 고객 등급을 조합하고 주문이 100건 이상인 집단만 비교합니다.

할인율 심화 분석으로 다음 자료도 생성합니다.

- 상품 × 할인율 반품률 히트맵
- 상품별 10% 할인 반품률과 해당 상품 전체 반품률의 차이
- 할인율별 단순 반품률과 상품 구성 보정 반품률 비교

상품·할인율별 표본이 100건 미만이면 히트맵에서 빈칸으로 표시합니다.

공책을 뜻하는 `Notebook`은 다음 세 가지로 추가 분석합니다.

- 연령대별 완료·반품 건수
- 연령대별 반품률
- 연령대와 구매수량(1개·2개·3개 이상) 조합별 반품률
- 연령대와 할인율 조합별 반품률

이 데이터의 고객 나이는 18~65세이므로 아동 구매 행동은 분석할 수 없습니다.

Notebook 심화 분석은 가격과 주문량이 비교적 가까운 `USB-C Cable`,
`HDMI Cable`, `Phone Case`를 비교군으로 사용합니다. 전체 반품률, 할인율별
반품률, Notebook의 할인율·수량 조합, 월별 반품률 비교 자료를 생성합니다.
