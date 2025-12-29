from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番ではフロントのURLを指定すると安全
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Android 用 CSV
PRICES_CSV = "data/android_prices.csv"
OPTIONS_CSV = "data/options.csv"  # Androidにもオプションを使うなら同様に用意


def safe_float(v):
  try:
    # "4,152" のようなカンマ付きも想定しておく
    if isinstance(v, str):
      v = v.replace(",", "")
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
  try:
    df = pd.read_csv(PRICES_CSV, usecols=["機種", "故障内容"])
    repairs = df[df["機種"] == model]["故障内容"].unique().tolist()
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

    # 未対応 / SOLD OUT を含む行は未対応扱い
    if any(str(v) in ["未対応", "SOLD OUT"] for v in row.values):
      return {"error": "UNSUPPORTED"}

    cost = safe_float(row["原価"])
    shipping = safe_float(row["送料"])
    profit_rate = safe_float(row["利益率"])

    if None in [cost, shipping, profit_rate]:
      return {"error": "UNSUPPORTED"}

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
