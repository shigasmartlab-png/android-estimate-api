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
        writer.writerow(["date"])

TIME_SLOTS = [
    "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00",
    "16:00", "17:00"
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
        return [row["date"] for row in csv.DictReader(f)]

def write_holidays(dates):
    with HOLIDAYS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date"])
        for d in dates:
            writer.writerow([d])

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

@app.get("/availability")
def get_availability(date: str):
    if date in read_holidays():
        return {
            "date": date,
            "slots": [{"time": t, "status": "holiday"} for t in TIME_SLOTS]
        }

    reserved = {
        r["time"] for r in read_reservations()
        if r["date"] == date and r["status"] == "reserved"
    }

    return {
        "date": date,
        "slots": [
            {"time": t, "status": "reserved" if t in reserved else "available"}
            for t in TIME_SLOTS
        ]
    }

@app.post("/reserve")
def reserve(data: ReserveRequest):
    if data.time not in TIME_SLOTS:
        raise HTTPException(status_code=400, detail="不正な時間帯です。")
    if data.date in read_holidays():
        raise HTTPException(status_code=400, detail="この日は休業日です。")

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
            if r["status"] == "cancelled":
                raise HTTPException(status_code=400, detail="すでにキャンセル済みです。")
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
    write_holidays([d for d in holidays if d != data.date])
    return {"message": "休みの日を削除しました。"}
