# mo-f2e

訴願 POC 的 E 項目：Demo 前端。使用 Vue 3、Vite、TypeScript 與 npm。

## 本機開發

建議使用 Node.js 24 LTS。

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

依終端顯示的本機網址開啟頁面。`.env` 預留後端 API 網址，目前全部使用本機假資料，尚未串接 API。

```powershell
npm run build
npm run preview
```

`build` 會先執行 TypeScript 檢查，再產生 `dist/`。

## E 項目範圍

依據 [訴願 POC 作戰計畫](https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296?via=auto_preview)：

1. 上傳訴願書與處分書影像。
2. OCR 原圖與辨識文字對照。
3. 程序檢核燈號。
4. 法條、判解與相似案例。
5. 決定書草稿：主文、事實、理由、教示，各段可展開引用。
6. 檢核表。

先依團隊的 `data/poc/03_介面規格.md` 假 JSON 開發，再串接 D 的 `POST /cases` 與 `GET /cases/{id}`，以輪詢取得進度。不做登入、資料庫或 WebSocket。

## 已實作的假資料 Demo

首頁預設開啟 113-16 示範案件的決定書草稿，可由流程列切換全部六個區塊。

- 文件上傳：支援 JPG、PNG、WebP，本機預覽，單檔上限 10 MB。
- 模擬分析：顯示階段進度，完成後進入 OCR 對照。
- OCR 對照：切換訴願書與原處分書，顯示固定假辨識結果。
- 程序檢核：顯示通過及人工確認的模擬燈號。
- 法源檢索：依據法條、判解、相似案篩選。
- 決定書：主文、事實、理由、教示與可展開的引用來源。
- 正本比對檢核：人工審閱勾選及純文字草稿下載。
- 桌面與手機版響應式排版。

### Demo 操作

1. 開啟首頁，查看決定書草稿，點選引用查看右側模擬來源。
2. 切換「法源檢索」測試篩選，切換「正本比對檢核」勾選審閱後下載。
3. 在「文件上傳」點選「開始模擬分析」，約 12 秒內依序顯示六步進度，完成後按「查看 OCR 對照」。處理中可停止、保留文件並重新開始。
4. 「新建案件」會清除本機選檔；選取兩份影像後可再次模擬分析。
5. 隨時按「載入示範案件」回復初始展示狀態。

輸入與檢索為展示假資料；草稿由團隊提供的正本轉製，檢核報告為預先計算結果。此 Demo 不會上傳文件、實際辨識圖片或執行法律判斷。重新整理會重置狀態。上傳的圖片僅供原圖預覽，模擬分析結果不會根據圖片改變。

### 程式位置

- `src/App.vue`：六階段畫面與互動狀態。
- `src/data/demo.ts`：將階段資料轉為畫面資料。
- `src/data/pipeline.json`：依工作包產生的固定 fixture 與 29/31 檢核報告。
- `src/components/ProcessingStatus.vue`：六步處理、等待時間、停止、重試、完成 UX。
- `scripts/build-demo-fixture.py`：從 `data/poc` 重建 fixture（Python 3，僅使用標準函式庫）。
- `src/components/AppIcon.vue`：SVG 圖示。
- `src/style.css`：版型、主題及響應式樣式。

字型使用 Google Fonts 的 Noto Sans TC 與 Noto Serif TC，無網路時回退至系統中文字型。已收錄團隊 `data/poc/03_介面規格.md`；GET 最外層狀態與每段引用映射尚未定義，見 `docs/backend-integration.md`。
