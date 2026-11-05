"""ข้อ 5: FastAPI ให้บริการสถิติผู้เข้าชมสวนสัตว์ ปีงบประมาณ 2569 (ข้อมูลจริงจาก Data.go.th)

รัน:  uvicorn main:app --host 0.0.0.0 --port 8000
"""
from pathlib import Path

import openpyxl
import requests
from fastapi import FastAPI, HTTPException, Query

# ---------- แหล่งข้อมูล (ตามโจทย์) ----------
DATASET_ID = "970c2632-1669-44aa-80c5-2c20cb2295e4"
RESOURCE_ID = "0ecc96cf-d914-42a1-b184-dbbd013c3c9c"
SOURCE = {
    "publisher": "องค์การสวนสัตว์แห่งประเทศไทย ในพระบรมราชูปถัมภ์",
    "portal": "Data.go.th",
    "dataset": "zoo-visitors2569 (รายงานสถิติจำนวนผู้เข้าชมสวนสัตว์ ปีงบประมาณ 2569)",
    "dataset_url": "https://data.go.th/dataset/zoo-visitors2569",
    "resource_id": RESOURCE_ID,
    "resource_url": (
        f"https://data.go.th/dataset/{DATASET_ID}/resource/{RESOURCE_ID}"
        "/download/-.-..69.xlsx"
    ),
}
FISCAL_YEAR = 2569
CKAN_API = "https://data.go.th/api/3/action/datastore_search"
XLSX_PATH = Path(__file__).parent / "data" / "zoo_visitors_2569.xlsx"


def download_xlsx() -> None:
    """ดาวน์โหลดไฟล์ทรัพยากรจริงจาก Data.go.th (ถ้ายังไม่มีในเครื่อง)"""
    XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(SOURCE["resource_url"], timeout=30)
    r.raise_for_status()
    XLSX_PATH.write_bytes(r.content)


def load_records() -> tuple[list[str], list[dict]]:
    """อ่านไฟล์ XLSX -> (รายชื่อเดือน, รายการสถิติ)"""
    if not XLSX_PATH.exists():
        download_xlsx()
    ws = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    # คอลัมน์ 0=รายการ 1=สวนสัตว์ 2=ปีงบประมาณ 3..=เดือน (ตัดคอลัมน์ว่างท้ายตาราง)
    months = [str(h).strip() for h in header[3:] if h is not None]

    records = []
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        values = row[3 : 3 + len(months)]
        # ช่องว่าง = ยังไม่มีรายงาน -> null (ไม่เดาเป็น 0)
        monthly = {m: (int(v) if isinstance(v, (int, float)) else None) for m, v in zip(months, values)}
        reported = [v for v in monthly.values() if v is not None]
        records.append({
            "category": str(row[0]).strip(),
            "zoo": str(row[1]).strip(),
            "fiscal_year": int(row[2]),
            "monthly": monthly,
            "total_reported": sum(reported),
        })
    return months, records


MONTHS, RECORDS = load_records()

app = FastAPI(
    title="Zoo Visitors API - ปีงบประมาณ 2569",
    description="RESTful API สถิติผู้เข้าชมสวนสัตว์ ปีงบประมาณ 2569 จาก Data.go.th (resource "
    + RESOURCE_ID + ")",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "Zoo Visitors API (FY 2569)",
        "endpoints": ["/api/zoo-visitors", "/api/zoo-visitors/summary",
                      "/api/zoo-visitors/categories", "/docs"],
        "source": SOURCE,
    }


@app.get("/api/zoo-visitors")
def zoo_visitors(
    zoo: str | None = Query(None, description="กรองตามชื่อสวนสัตว์ (บางส่วนของชื่อก็ได้) เช่น เชียงใหม่"),
    category: str | None = Query(None, description="กรองตามประเภทผู้เข้าชม เช่น ผู้ใหญ่"),
):
    """รายการสถิติผู้เข้าชมรายเดือน แยกตามสวนสัตว์และประเภทผู้เข้าชม"""
    data = RECORDS
    if zoo:
        data = [r for r in data if zoo in r["zoo"]]
    if category:
        data = [r for r in data if category == r["category"]]
    if not data:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลตามเงื่อนไขที่ระบุ")
    return {
        "source": SOURCE,
        "fiscal_year": FISCAL_YEAR,
        "months": MONTHS,
        "note": "ค่า null = ยังไม่มีรายงานของเดือนนั้นในไฟล์ต้นทาง",
        "count": len(data),
        "data": data,
    }


@app.get("/api/zoo-visitors/summary")
def summary():
    """ยอดรวมผู้เข้าชม (ทุกประเภท) ของแต่ละสวนสัตว์ คำนวณจากข้อมูลจริง"""
    totals: dict[str, int] = {}
    for r in RECORDS:
        totals[r["zoo"]] = totals.get(r["zoo"], 0) + r["total_reported"]
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "source": SOURCE,
        "fiscal_year": FISCAL_YEAR,
        "months_covered": MONTHS,
        "data": [{"zoo": z, "total_visitors": t} for z, t in ranked],
        "grand_total": sum(totals.values()),
    }


@app.get("/api/zoo-visitors/categories")
def categories():
    """คำอธิบายประเภทผู้เข้าชม — เรียกสดจาก Data.go.th CKAN API (datastore_search)"""
    try:
        r = requests.get(CKAN_API, params={"resource_id": RESOURCE_ID, "limit": 100}, timeout=15)
        r.raise_for_status()
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"เรียก Data.go.th API ไม่สำเร็จ: {e}")
    return {
        "source": {**SOURCE, "api": CKAN_API},
        "fiscal_year": FISCAL_YEAR,
        "count": len(body["result"]["records"]),
        "data": [{"category": x.get("รายการ"), "description": x.get("คำอธิบาย")}
                 for x in body["result"]["records"]],
    }
