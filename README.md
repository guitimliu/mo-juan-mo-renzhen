# 莫捲莫認真｜訴願決定書草稿助理

新北市 AI 黑客松・法制局題目。承辦人上傳**訴願書＋原處分書**影像 → OCR → 案件擷取＋程序檢核 → 法規／判解／歷史決定書檢索 → 依模板生成決定書草稿 → 與正本比對的檢核表。
結論（駁回／撤銷／不受理）由程序規則決定，模型只負責撰寫理由；引用只認檢索結果，缺依據列為待補查；個資在 OCR 後立即以代號取代、對照表不出本機。

- 線上：https://drod66yo9d2zo.cloudfront.net/ （CloudFront → 彈性 IP → EC2 Docker Compose）
- 影片（5 分鐘）：https://youtu.be/pfJ2o0RFwcM ；簡報：線上站 `/slides/`
- 驗證案例：113 年第 16 號違反洗錢防制法事件（訴願駁回），bedrock 模式實測 S5 檢核 29/31、全鏈約 100–120 秒

## 專案結構

```text
f2e/        Vue 3 + Vite + TypeScript 前端：案件工作台、我的案件列表、草稿編輯／版本／還原、PDF／Word 匯出
backend/    FastAPI 後端：六階段管線（S1 OCR → S2 擷取 → S2.5 程序檢核 → S3 檢索 → S4 生成 → S5 檢核）、規則引擎、
            個資取代、WebSocket 即時進度、PostgreSQL 持久層；ADAPTER=stub（離線）或 bedrock（四段接 AWS）
slides/     Slidev 簡報（含架構圖）
video/      6 分鐘影片產線：Playwright 錄 Demo、Gemini TTS 旁白（聽寫回驗）、Remotion 合成、ElevenLabs 配樂、SRT／章節側檔、封面
docs/       AWS 架構圖（draw.io／PNG／SVG）、26,607 篇訴願決定書量化／質性分析、儲存層設計
data/poc/   工作包（凍結契約 03_介面規格.md、模板、few-shot、檢核器）
data/       statutes.json（法條 2,214 條）、precedents.json、petitions.jsonl（主辦方 101 件）、
            law_index.json（案型→高頻條文索引）、decisions_slim.jsonl.gz（新北市法制局 2004–2026 訴願決定書 26,607 篇精簡索引）
```

## 一鍵啟動（Docker Compose）

```bash
cp .env.example .env          # stub 模式留預設即可；要接 Bedrock 填 ADAPTER=bedrock 與 AWS 憑證；要登入頁填 AUTH_USERNAME／AUTH_PASSWORD
docker compose up --build     # 前端 http://localhost:8080（/api → backend、/slides/ → 簡報，由 nginx 反向代理）；後端另開 8000 供 curl
```

服務：`frontend`（nginx＋Vue）、`backend`（uvicorn，含 healthcheck）、`db`（PostgreSQL 16，volume `pgdata`）、`slides`。

- 案件、上傳影像、六階段結果、承辦人草稿版本都存在 `db`；後端重啟後「我的案件」仍在。`DATABASE_URL` 設空字串＝純記憶體。
- `backend/Dockerfile` 把 `data/`（含 `law_index.json`、`decisions_slim.jsonl.gz`）一起包進去（`DATA_DIR=/app/data`）。
- `f2e/Dockerfile`：node 22 建 `dist/` → nginx（`f2e/nginx.conf`：`/api/` → `backend:8000`、`/slides/` → `slides:80`，上傳上限 25 MB，WebSocket 已加 Upgrade 標頭）。
- 埠被占用就在 `.env` 改 `FRONTEND_PORT`／`BACKEND_PORT`；DB 密碼 `POSTGRES_PASSWORD`。
- 部署更新：`git pull origin main && docker compose up -d --build`。Bedrock 憑證若是主辦方臨時 token，過期後換 `.env` 三個 `AWS_*` 再 `docker compose up -d --force-recreate backend`。

## 本機開發（兩個終端）

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000        # 不設 DATABASE_URL＝純記憶體；測試：pytest -q（135 項）
```

```bash
cd f2e && npm install && cp .env.example .env && npm run dev
```

瀏覽器開 http://localhost:5173 →（有設帳密則先登入）→ 新建案件 → 「一鍵 Demo（載入並分析）」或自己選兩張圖 → 「開始分析」。
完成後可在側欄「案件列表」回到同一案件；草稿頁「編輯草稿 → 儲存版本」，版本下拉可還原 AI 原稿；法源頁顯示同案型歷史決定書的裁決分布。

- 後端說明、API（含草稿版本 API）、規則引擎、Bedrock 模式、Knowledge Base、持久層：[backend/README.md](backend/README.md)
- 前端說明：[f2e/README.md](f2e/README.md)；前後端契約：[f2e/docs/backend-integration.md](f2e/docs/backend-integration.md)
- **stub 模式輸出＝工作包正本改寫，不是 AI 生成**；demo 時請照實說明。bedrock 模式才是真的 Claude 生成。

## 資料與檢索

- Knowledge Base `ZOMMOWFOT2`（Bedrock，Titan Text Embeddings v2 → S3 Vectors）：主辦方 141 篇（法規／判解／函釋／決定書）＋新北市法制局網站 26,607 篇訴願決定書（官方同意抓取，`backend/tools/crawl_ntpc_appeals.py`）。
- S3 檢索除向量檢索外，依案由從 `data/law_index.json` 補同案型歷史高頻條文，並回傳同案型裁決分布（`history`）；本案自己的決定書會被排除。
- 分析報告：[docs/ntpc_appeals_analysis.md](docs/ntpc_appeals_analysis.md)（量化）、[docs/ntpc_appeals_qualitative.md](docs/ntpc_appeals_qualitative.md)（駁回論證骨架、撤銷理由分類、77 條分流）。
- AWS 架構：[docs/aws-architecture.md](docs/aws-architecture.md)。

## 簡報與影片

- 簡報：隨 `docker compose up --build` 一起起（http://localhost:8080/slides/ ）；本機在 `slides/` 執行 `npm ci && npm run dev`。詳見 [slides/README.md](slides/README.md)。
- 影片：產線與重製流程見 [video/README.md](video/README.md)；成品側檔（標題／描述／章節時間軸／SRT 字幕）在 `video/out/`，封面在 `video/thumb/`。

## 團隊與交接

分工、進度與待辦見 [HANDOFF.md](HANDOFF.md)。
