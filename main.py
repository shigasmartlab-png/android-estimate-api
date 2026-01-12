from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime
import csv
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

RESERVATIONS_CSV = DATA_DIR / "reservations.csv"
HOLIDAYS_CSV = DATA_DIR / "holidays.csv"

# 初期化
if not RESERVATIONS_CSV.exists():
    with RESERVATIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "date", "time", "name", "phone",
            "menu", "memo", "created_at", "status"
        ])

if not HOLIDAYS_CSV.exists():
    with HOLIDAYS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "time"])

# 営業時間 9:00〜21:00（1時間刻み）
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00", "16:00",
    "17:00", "18:00", "19:00", "20:00",
    "21:00"
]

def read_reservations():
    with RESERVATIONS_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_reservations(rows):
    with RESERVATIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "date", "time", "name", "phone",
            "menu", "memo", "created_at", "status"
        ])
        writer.writeheader()
        writer.writerows(rows)

def read_holidays():
    with HOLIDAYS_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_holidays(rows):
    with HOLIDAYS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "time"])
        for r in rows:
            writer.writerow([r["date"], r["time"]])

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
    time: str

class HolidayRemove(BaseModel):
    date: str
    time: str

@app.get("/availability")
def get_availability(date: str):
    holidays = read_holidays()
    holiday_times = {h["time"] for h in holidays if h["date"] == date}

    rows = read_reservations()
    reserved_times = {
        r["time"]
        for r in rows
        if r["date"] == date and r["status"] == "reserved"
    }

    result = []
    for t in TIME_SLOTS:
        if t in holiday_times:
            status = "holiday"
        elif t in reserved_times:
            status = "reserved"
        else:
            status = "available"
        result.append({"time": t, "status": status})

    return {"date": date, "slots": result}

@app.post("/reserve")
def reserve(data: ReserveRequest):
    if data.time not in TIME_SLOTS:
        raise HTTPException(status_code=400, detail="不正な時間帯です。")

    holidays = read_holidays()
    if any(h["date"] == data.date and h["time"] == data.time for h in holidays):
        raise HTTPException(status_code=400, detail="この時間帯は休業です。")

    rows = read_reservations()
    for r in rows:
        if r["date"] == data.date and r["time"] == data.time and r["status"] == "reserved":
            raise HTTPException(status_code=400, detail="その時間帯は既に予約済みです。")

    rid = str(uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows.append({
        "id": rid, "date": data.date, "time": data.time,
        "name": data.name, "phone": data.phone,
        "menu": data.menu, "memo": data.memo or "",
        "created_at": now, "status": "reserved"
    })

    write_reservations(rows)
    return {"message": "予約を受け付けました。", "reservation_id": rid}

@app.post("/cancel")
def cancel(data: CancelRequest):
    rows = read_reservations()
    for r in rows:
        if r["id"] == data.reservation_id:
            r["status"] = "cancelled"
            write_reservations(rows)
            return {"message": "予約をキャンセルしました。"}
    raise HTTPException(status_code=404, detail="予約が見つかりません。")

@app.get("/list")
def list_reservations(date: str | None = None):
    rows = read_reservations()
    return {"reservations": [r for r in rows if not date or r["date"] == date]}

@app.get("/holidays")
def get_holidays():
    return {"holidays": read_holidays()}

@app.post("/holidays/add")
def add_holiday(data: HolidayAdd):
    holidays = read_holidays()
    if any(h["date"] == data.date and h["time"] == data.time for h in holidays):
        raise HTTPException(status_code=400, detail="すでに登録されています。")
    holidays.append({"date": data.date, "time": data.time})
    write_holidays(holidays)
    return {"message": "休み時間帯を追加しました。"}

@app.post("/holidays/remove")
def remove_holiday(data: HolidayRemove):
    holidays = read_holidays()
    holidays = [h for h in holidays if not (h["date"] == data.date and h["time"] == data.time)]
    write_holidays(holidays)
    return {"message": "休み時間帯を削除しました。"}
