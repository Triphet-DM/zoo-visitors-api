# Zoo Visitors API (ปีงบประมาณ 2569)

FastAPI ให้บริการสถิติผู้เข้าชมสวนสัตว์ ปีงบประมาณ 2569 จาก Data.go.th
(dataset `zoo-visitors2569`, resource `0ecc96cf-d914-42a1-b184-dbbd013c3c9c`)

- `GET /api/zoo-visitors` — รายการสถิติรายเดือน (กรองได้ด้วย `?zoo=` และ `?category=`)
- `GET /api/zoo-visitors/summary` — ยอดรวมแยกตามสวนสัตว์
- `GET /api/zoo-visitors/categories` — คำอธิบายประเภทผู้เข้าชม (เรียกสดจาก Data.go.th CKAN API)
- `GET /docs` — Swagger UI

## Run
```n pip install -r requirements.txt
 uvicorn main:app --host 0.0.0.0 --port 8000
```n