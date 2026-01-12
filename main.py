from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime
import csv
from pathlib import Path

app = FastAPI()

# CORS（どこからでもアクセス許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データフォルダ
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# CSVファイル
RESERVATIONS_CSV = DATA_DIR / "reservations.csv"
HOLIDAYS_CSV = DATA_DIR / "holidays.csv"

# 初期化：予約CSV
if not RESERVATIONS_CSV.exists():
    with RESERVATIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "date", "time", "name", "phone",
            "menu", "memo", "created_at", "status"
        ])

# 初期化：休みの日CSV
if not HOLIDAYS_CSV.exists():
    with HOLIDAYS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date"])

# 営業時間（予約枠）
TIME_SLOTS = [
    "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00",
    "16:00", "17:00"
]


# --------------------------
# CSV 読み書き関数
# --------------------------

def read_reservations():
    rows = []
    with RESERVATIONS_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def write_reservations(rows):
    with RESERVATIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "date", "time", "name", "phone",
            "menu", "memo", "created_at", "status"
        ])
        writer.writeheader()
        writer.writerows(rows)


def read_holidays():
    rows = []
    with HOLIDAYS_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row["date"])
    return rows


def write_holidays(dates):
    with HOLIDAYS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date"])
        for d in dates:
            writer.writerow([d])


# --------------------------
# リクエストモデル
# --------------------------

class ReserveRequest(BaseModel):
    date: str
    time: str
    name: str
    phone: str
    menu: str
    memo: str | None = ""


class CancelRequest(BaseModel):
    reservation_id: str


class HolidayAdd(BaseModel):
    date: str


class HolidayRemove(BaseModel):
    date: str


# --------------------------
# API：空き状況
# --------------------------

@app.get("/availability")
def get_availability(date: str):
    holidays = read_holidays()

    # ★ 休みの日なら全枠 unavailable
    if date in holidays:
        return {
            "date": date,
            "slots": [
                {"time": t, "status": "holiday"} for t in TIME_SLOTS
            ]
        }

    rows = read_reservations()

    reserved_times = {
        r["time"]
        for r in rows
        if r["date"] == date and r["status"] == "reserved"
    }

    result = []
    for t in TIME_SLOTS:
        result.append({
            "time": t,
            "status": "reserved" if t in reserved_times else "available"
        })

    return {"date": date, "slots": result}


# --------------------------
# API：予約
# --------------------------

@app.post("/reserve")
def reserve(data: ReserveRequest):
    if data.time not in TIME_SLOTS:
        raise HTTPException(status_code=400, detail="不正な時間帯です。")

    holidays = read_holidays()
    if data.date in holidays:
        raise HTTPException(status_code=400, detail="この日は休業日です。")

    rows = read_reservations()

    for r in rows:
        if (
            r["date"] == data.date and
            r["time"] == data.time and
            r["status"] == "reserved"
        ):
            raise HTTPException(status_code=400, detail="その時間帯は既に予約済みです。")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rid = str(uuid4())

    new_row = {
        "id": rid,
        "date": data.date,
        "time": data.time,
        "name": data.name,
        "phone": data.phone,
        "menu": data.menu,
        "memo": data.memo or "",
        "created_at": now,
        "status": "reserved",
    }

    rows.append(new_row)
    write_reservations(rows)

    return {"message": "予約を受け付けました。", "reservation_id": rid}


# --------------------------
# API：キャンセル
# --------------------------

@app.post("/cancel")
def cancel(data: CancelRequest):
    rows = read_reservations()
    found = False

    for r in rows:
        if r["id"] == data.reservation_id:
            if r["status"] == "cancelled":
                raise HTTPException(status_code=400, detail="すでにキャンセル済みです。")
            r["status"] = "cancelled"
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="予約が見つかりません。")

    write_reservations(rows)
    return {"message": "予約をキャンセルしました。"}


# --------------------------
# API：予約一覧（管理用）
# --------------------------

@app.get("/list")
def list_reservations(date: str | None = None):
    rows = read_reservations()
    if date:
        rows = [r for r in rows if r["date"] == date]
    return {"reservations": rows}


# --------------------------
# API：休みの日管理
# --------------------------

@app.get("/holidays")
def get_holidays():
    return {"holidays": read_holidays()}


@app.post("/holidays/add")
def add_holiday(data: HolidayAdd):
    holidays = read_holidays()
    if data.date in holidays:
        raise HTTPException(status_code=400, detail="すでに登録されています。")
    holidays.append(data.date)
    write_holidays(holidays)
    return {"message": "休みの日を追加しました。"}


@app.post("/holidays/remove")
def remove_holiday(data: HolidayRemove):
    holidays = read_holidays()
    if data.date not in holidays:
        raise HTTPException(status_code=404, detail="登録されていません。")
    holidays = [d for d in holidays if d != data.date]
    write_holidays(holidays)
    return {"message": "休みの日を削除しました。"}
