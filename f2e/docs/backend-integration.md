# 前端與後端的串接（2026-09-12 已接通）

契約原件：`data/poc/03_介面規格.md`（S0–S5 正文凍結；**附錄 A/B/C** 於 2026-09-12 補定，回應本文件原本列的缺口）。
後端實作：`backend/`（FastAPI，stub adapters）；啟動與 API 細節見 `backend/README.md`。

## 已定義（正文）

- `POST /api/cases`：multipart `petition_image`、`disposition_image` → 202 `{ "case_id": "poc-001" }`。
- `GET /api/cases/{case_id}`：輪詢案件最新結果。
- S1 OCR、S2 案件摘要、S2.5 程序、S3 檢索、S4 草稿、S5 檢核的各階段內容欄位。

## 原本「尚未定義」的部分 → 現在的依據

| 原缺口 | 依據 |
|---|---|
| GET 最外層 envelope、未完成時的值 | **附錄 A**：`stages.S1…S5.{status,data,error,elapsed_ms}`；未完成 `data:null` |
| 目前階段與生命週期 enum | **附錄 A**：案件 `status` ∈ queued/running/done/error；階段 `status` ∈ pending/running/done/error/skipped；`current_stage` 進行中階段，done 時 null |
| 失敗原因、重試、輪詢間隔、逾時、取消 | **附錄 A**：階段失敗 → 該階段 `status:"error"` ＋ `error` 字串，整體 `error` 記第一個失敗階段；輪詢 1500 ms、status ∈ {done,error} 即停；逾時前端自訂（實作 300 s，bedrock 全鏈實測 116 s）；無取消端點，「停止」只停前端輪詢 |
| S4 citations 只有全域引用、無段落索引 | **附錄 B**：每筆 `{text, source, section, index}`，`section ∈ {facts, reasons, instruction}`，前端依 (section, index) 掛到段落（`src/data/demo.ts` 的 `buildView`） |
| S5 摘要與 `07_檢核.py` 輸出不同 | **附錄 C**：S5 ＝ 07 完整輸出 `{checks, score}` ＋ `summary`（原 S5 摘要，由後端從 checks 算出） |

## 前端實作位置

- `src/api.ts`：`getHealth()`、`createCase(petition, disposition, serviceDate?)`（選填 `service_date` 表單欄位）、`getCase(id)`；型別 `CaseEnvelope`、S1–S5；base URL 讀 `VITE_API_BASE_URL`（未設定＝`http://localhost:8000`；空字串＝同源，Docker/nginx 用）。
- `src/exportDraft.ts`／`draftPdf.ts`／`draftDocx.ts`：匯出吃目前 view 的草稿與表頭（案號＝case_id），不再固定 113-16。
- 第 6 步「正本比對檢核」由 `showDeveloperChecks`（demo.ts）控制顯示；後端仍會算 S5，進度條會等它完成。
- `src/data/demo.ts`：`stagesFrom(envelope | 舊 fixture)` → `buildView()`；任一階段未完成就顯示空白，不補假資料。
- `src/App.vue`：`runDemo()` = POST → 每 1.5 s GET → `progressFrom(env)` 推進 `ProcessingStatus` → done 時 `ready`。連不上後端或後端回 error 時顯示錯誤（`ProcessingStatus` 的 `error` prop），**不會退回 fixture**。頂部標籤依 `GET /api/health` 的 `adapter_mode` 顯示「示範資料（stub）」。
- 「載入示範案件」仍走本機 fixture（`src/data/pipeline.json`），是後端掛掉時的保底。

## fixture 怎麼來

`src/data/pipeline.json` 現在是**附錄 A envelope**，由後端 stub pipeline 產出：`cd backend && python -m app.fixture`。
`scripts/build-demo-fixture.py` 是舊工作包時期的產生器（舊形狀、教示法院為地院），已棄用；`demo.ts` 仍相容舊形狀，但請不要再用它重建。

## 工作包差異（已解決）

- 教示法院：`00`／`03` 原本寫臺灣新北地方法院行政訴訟庭，已修正為臺北高等行政法院（與 `04`／`06`／`09` 一致）；`f2e/data/poc` 與根目錄 `data/poc` 已同步為修正版，之後請以 `data/poc/` 為準，不要從舊副本重建。
- 檢核結果：stub 草稿（正本改寫）不帶 S3 為 30/30；帶 stub S3 為 30/31，唯一未通過是「引用判決皆在檢索結果內」——正本引的三篇簡字判決不在資料集，屬預期，S4 的 `gaps` 會列出。
- 草稿是正本改寫，不是模型生成品質測試；前端頁面與 `backend/README.md` 都有標示。
