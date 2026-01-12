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

# CSVファイルのパス
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "reservations.csv"

# 初期化：CSVがなければヘッダーを作成
if not CSV_PATH.exists():
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "date", "time", "name", "phone",
            "menu", "memo", "created_at", "status"
        ])

# 営業時間中の予約枠（必要に応じて変更）
TIME_SLOTS = [
    "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00",
    "16:00", "17:00"
]


class ReserveRequest(BaseModel):
    date: str   # "2025-02-10"
    time: str   # "14:00"
    name: str
    phone: str
    menu: str
    memo: str | None = ""


class CancelRequest(BaseModel):
    reservation_id: str


def read_reservations():
    rows = []
    with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def write_reservations(rows):
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "date", "time", "name", "phone",
            "menu", "memo", "created_at", "status"
        ])
        writer.writeheader()
        writer.writerows(rows)


@app.get("/availability")
def get_availability(date: str):
    """
    指定日の空き状況を返す
    """
    rows = read_reservations()

    # その日の「予約済み」枠だけ抽出
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


@app.post("/reserve")
def reserve(data: ReserveRequest):
    """
    予約登録
    """
    # 時間枠バリデーション
    if data.time not in TIME_SLOTS:
        raise HTTPException(status_code=400, detail="不正な時間帯です。")

    rows = read_reservations()

    # すでに予約が入っているか確認（キャンセル済みは無視）
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

    return {
        "message": "予約を受け付けました。",
        "reservation_id": rid
    }


@app.post("/cancel")
def cancel(data: CancelRequest):
    """
    予約キャンセル（論理削除：statusをcancelledに変更）
    """
    rows = read_reservations()
    found = False

    for r in rows:
        if r["id"] == data.reservation_id:
            if r["status"] == "cancelled":
                raise HTTPException(status_code=400, detail="すでにキャンセル済みの予約です。")
            r["status"] = "cancelled"
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="予約が見つかりません。")

    write_reservations(rows)
    return {"message": "予約をキャンセルしました。"}


@app.get("/list")
def list_reservations(date: str | None = None):
    """
    管理用：予約一覧（必要なら管理画面から使う）
    """
    rows = read_reservations()
    if date:
        rows = [r for r in rows if r["date"] == date]
    return {"reservations": rows}
