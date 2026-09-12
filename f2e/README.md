# mo-f2e

訴願 POC 的 E 項目：Demo 前端。使用 Vue 3、Vite、TypeScript 與 npm。

## 本機開發

建議使用 Node.js 24 LTS。

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

依終端顯示的本機網址開啟頁面。`.env` 的 `VITE_API_BASE_URL` 指向後端（預設 `http://localhost:8000`；後端啟動見 `../backend/README.md`）。「開始分析（送後端）」走 `POST/GET /api/cases`；「載入示範案件」走本機 fixture（後端掛掉時的保底）。

```powershell
npm run build
npm run preview
```

`build` 會先執行 TypeScript 檢查，再產生 `dist/`。

Docker：`f2e/Dockerfile` 多階段建 `dist/` 後交給 nginx（`nginx.conf` 把 `/api/` 代理到 `backend:8000`）；build arg `VITE_API_BASE_URL` 留空＝同源。整套用根目錄 `docker compose up --build`。

「送達日期（選填）」欄位會以 `service_date` 一起 POST 給後端，覆蓋 OCR 擷取的送達日（程序檢核以此計算 30 日）。

## E 項目範圍

依據 [訴願 POC 作戰計畫](https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296?via=auto_preview)：

1. 上傳訴願書與處分書影像。
2. OCR 原圖與辨識文字對照。
3. 程序檢核燈號。
4. 法條、判解與相似案例。
5. 決定書草稿：主文、事實、理由、教示，各段可展開引用。
6. 檢核表。

依團隊的 `data/poc/03_介面規格.md`（含附錄 A/B/C）串接 `backend/` 的 `POST /api/cases` 與 `GET /api/cases/{id}`，以每 1.5 秒輪詢取得進度。不做登入、資料庫或 WebSocket。

## 已實作的 Demo

首頁預設開啟 113-16 示範案件（本機 fixture）的決定書草稿，可由流程列切換全部六個區塊。選兩張圖片按「開始分析（送後端）」則六個區塊改由後端 API 逐階段填入。

- 文件上傳：支援 JPG、PNG、WebP，本機預覽，單檔上限 10 MB。
- 後端分析：POST 影像 → 輪詢 envelope → 六步進度隨 `stages.*.status` 推進，各區塊資料到了就能點；後端連不上顯示錯誤，不退回假資料。
- OCR 對照：切換訴願書與原處分書，顯示後端 S1 文字（stub 模式為工作包模擬文件）。
- 程序檢核：顯示後端規則引擎（S2.5）的燈號；無法判定的項目標「待人工確認」。
- 法源檢索：依據法條、判解、相似案篩選。
- 決定書：主文、事實、理由、教示與可展開的引用來源。
- 正本比對檢核：人工審閱勾選及純文字草稿下載。
- 桌面與手機版響應式排版。

### Demo 操作

1. 開啟首頁，查看決定書草稿，點選段落引用查看右側來源（附錄 B 段落映射）。
2. 切換「法源檢索」測試篩選，切換「正本比對檢核」勾選審閱後下載。
3. 「新建案件」→ 選兩張圖 → 「開始分析（送後端）」，stub 模式約 9 秒內依序顯示六步進度，完成後按「查看 OCR 對照」。處理中可停止輪詢、保留文件並重新開始。
4. 頂部標籤依 `GET /api/health` 顯示後端模式（示範資料（stub）／後端未連線）。
5. 隨時按「載入示範案件」回復初始展示狀態。

後端目前為 stub 模式：影像會送到本機後端但不辨識，S1/S3 為工作包內容、S4 草稿為正本改寫（非 AI 生成）、S2.5 程序檢核與 S5 檢核表則是後端真的算出來的。不上雲、不儲存；重新整理會重置狀態。

### 程式位置

- `src/App.vue`：六階段畫面與互動狀態；`runDemo()` 走後端 API。
- `src/api.ts`：後端 API 客戶端與 envelope 型別。
- `src/data/demo.ts`：`stagesFrom()`＋`buildView()` 把 envelope（或 fixture）轉為畫面資料。
- `src/data/pipeline.json`：保底 fixture（附錄 A envelope，由 `backend: python -m app.fixture` 產出，30/31）。
- `src/components/ProcessingStatus.vue`：六步處理、等待時間、停止、重試、完成 UX。
- `scripts/build-demo-fixture.py`：舊 fixture 產生器，已棄用（改用後端 `python -m app.fixture`）。
- `src/components/AppIcon.vue`：SVG 圖示。
- `src/style.css`：版型、主題及響應式樣式。

字型使用 Google Fonts 的 Noto Sans TC 與 Noto Serif TC，無網路時回退至系統中文字型。已收錄團隊 `data/poc/03_介面規格.md`（含附錄 A/B/C）；串接細節見 `docs/backend-integration.md`。
