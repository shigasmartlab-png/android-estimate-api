from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番はフロントURLに絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======== ここだけ iPhone / Android で切り替える =========
PRICES_CSV = "data/android_prices.csv"   # Android 用
# PRICES_CSV = "data/prices.csv"  # iPhone 用
# ==========================================================
OPTIONS_CSV = "data/options.csv"


def safe_float(v):
    try:
        if isinstance(v, str):
            v = v.replace(",", "").strip()
        return float(v)
    except:
        return None


@app.get("/models")
def get_models():
    try:
        df = pd.read_csv(PRICES_CSV, usecols=["機種"])
        models = sorted(df["機種"].unique().tolist())
        return {"models": models}
    except Exception as e:
        return {"error": str(e), "models": []}


@app.get("/repairs")
def get_repairs(model: str):
    """
    status:
      - available
      - unsupported
      - soldout
    """
    try:
        df = pd.read_csv(PRICES_CSV, usecols=["機種", "故障内容", "原価"])

        rows = df[df["機種"] == model]

        repairs = []
        for _, r in rows.iterrows():
            raw = str(r["原価"]).strip()

            if raw == "未対応":
                status = "unsupported"
            elif raw == "SOLD OUT":
                status = "soldout"
            else:
                status = "available"

            repairs.append({
                "name": r["故障内容"],
                "status": status
            })

        return {"repairs": repairs}

    except Exception as e:
        return {"error": str(e), "repairs": []}


@app.get("/options")
def get_options():
    try:
        df = pd.read_csv(OPTIONS_CSV)
        return {"options": df.to_dict(orient="records")}
    except Exception as e:
        return {"error": str(e), "options": []}


@app.get("/estimate")
def estimate(model: str, repair_type: str, options: str = ""):
    try:
        REQUIRED_COLUMNS = ["機種", "故障内容", "原価", "送料", "利益率"]
        prices_df = pd.read_csv(PRICES_CSV, usecols=REQUIRED_COLUMNS)
        options_df = pd.read_csv(OPTIONS_CSV)

        row = prices_df[
            (prices_df["機種"] == model) &
            (prices_df["故障内容"] == repair_type)
        ]

        if row.empty:
            return {"error": "該当する修理が見つかりません"}

        row = row.iloc[0]

        raw = str(row["原価"]).strip()
        if raw == "未対応":
            return {"error": "未対応"}
        if raw == "SOLD OUT":
            return {"error": "SOLD OUT"}

        cost = safe_float(row["原価"])
        shipping = safe_float(row["送料"])
        profit_rate = safe_float(row["利益率"])

        if None in [cost, shipping, profit_rate]:
            return {"error": "未対応"}

        # ★ 原価が 10,000円超なら利益率を 50% に強制
        if cost > 10000:
            profit_rate = 0.5

        if profit_rate >= 1:
            return {"error": "利益率が1以上のため計算できません"}

        base_price = (cost + shipping) / (1 - profit_rate)
        base_price = int(base_price)

        total_option_price = 0
        selected_options = []

        if options:
            option_list = [opt.strip() for opt in options.split(",")]

            for opt in option_list:
                match = options_df[options_df["オプション名"] == opt]
                if not match.empty:
                    price = int(match.iloc[0]["料金"])
                    total_option_price += price
                    selected_options.append({
                        "name": opt,
                        "price": price
                    })

        total = base_price + total_option_price

        return {
            "model": model,
            "repair_type": repair_type,
            "base_price": base_price,
            "options": selected_options,
            "total": total
        }

    except Exception as e:
        return {"error": str(e)}
