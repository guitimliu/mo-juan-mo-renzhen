# mo-juan-mo-renzhen

訴願 POC：輸入民眾訴願書＋原處分書影像 → OCR → 案件擷取＋程序檢核 → 檢索 → 決定書草稿 → 與正本比對的檢核表。
單一案例 POC：113-16 違反洗錢防制法事件・訴願駁回。

## 專案結構

```text
f2e/        Vue 3 + Vite + TypeScript 前端（E）
backend/    FastAPI 後端；adapters 目前為 stub，之後換 Bedrock（D）
data/poc/   工作包（唯一真相來源同步自 hackathon/data/poc；03_介面規格.md 為凍結契約）
data/       statutes.json、precedents.json（從主辦方 PDF 切出）、petitions.jsonl（101 件歷史決定書）
```

## 一鍵啟動（Docker Compose）

```bash
cp .env.example .env          # stub 模式留預設即可；要接 Bedrock 再填 ADAPTER=bedrock 與 AWS 憑證
docker compose up --build     # 前端 http://localhost:8080（/api 由 nginx 反向代理到 backend）；後端另外開 8000 供 curl
```

- `backend/Dockerfile`：python:3.12-slim + uvicorn，把 `data/` 一起包進去（`DATA_DIR=/app/data`），有 healthcheck。
- `f2e/Dockerfile`：node 22 建 `dist/` → nginx（`f2e/nginx.conf`：`/api/` → `backend:8000`，上傳上限 25 MB）。前端 build 時 `VITE_API_BASE_URL` 留空＝同源呼叫。
- 埠被占用就在 `.env` 改 `FRONTEND_PORT`／`BACKEND_PORT`。

## 本機開發（兩個終端）

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd f2e && npm install && cp .env.example .env && npm run dev
```

瀏覽器開 http://localhost:5173 → 新建案件 → 選兩張圖 → 「開始分析（送後端）」。
後端掛掉時按「載入示範案件」看本機 fixture（保底）。

- 後端說明、API、規則引擎、接 Bedrock 要改哪裡：[backend/README.md](backend/README.md)
- 前端說明：[f2e/README.md](f2e/README.md)；前後端契約補定：[f2e/docs/backend-integration.md](f2e/docs/backend-integration.md)
- **stub 模式輸出＝工作包正本改寫，不是 AI 生成**；demo 時請照實說明。
