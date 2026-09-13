# HANDOFF — 給下一個 session

更新：2026-09-12 16:10。上一個 session 完成資料盤點、案例選定、五人分工、A 角色工作包；**本 session（hackathon-c8）完成 `backend/`（stub 管線）並把 E 的前端接上真 API；平行 session（aws-test-95）同時把 `bedrock.py` 四段（OCR／Extract／Retrieval／Generate）接上 AWS（KB `ZOMMOWFOT2`）**。
團隊 repo：https://github.com/guitimliu/mo-juan-mo-renzhen，**PR #2 已於 2026-09-12 20:54 合併進 main（`daeeca2`）**；`backend` 分支保留，之後改動 pull 後在 backend 繼續或直接對 main 開 PR；EC2 部署 checkout main。本機 clone 在 `mo-juan-mo-renzhen/`。
**現況：WebSocket 即時進度（子步驟＋S4 草稿串流，輪詢改備援）已加；個資前處理（取代法，S1 後姓名→甲○○、證號／電話／地址／生日遮罩，S4 還原姓名，對照表不出本機）已加；帳密登入（`AUTH_USERNAME`／`AUTH_PASSWORD`，不設＝免登入）與前端「一鍵 Demo」已加；模型預設 Sonnet 5、可用環境變數設定、帳戶不可用自動降級 4.6；`ADAPTER=bedrock` 端到端已通，Generate 實測 S5 29/31（剩 2 分是正本才有的 LINE 對話內容，輸入文件沒有）；`docker compose up --build` 可一鍵起前後端（§2.5）。** 已合併 E 的前端 v2（main）：送達日期欄位、PDF／Word 匯出、隱藏第 6 步。

---

## 1. 現況（已完成，不要重做）

> 這份是 repo 內副本。表中 `tools/parse_petitions.py`、`data/report.html`、`questions.html`、`plan.html`、`extracted/` 在 hackathon 工作目錄（未入 repo）；repo 內只有 `data/poc/`、`data/*.json`、`data/petitions.jsonl`、`backend/`、`f2e/`。§2.0 的絕對路徑是本機的。

| 項目 | 位置 | 狀態 |
|---|---|---|
| 141 份 PDF 解析、101 件決定書結構化 | `data/petitions.jsonl`、`tools/parse_petitions.py` | 完成 |
| 資料盤點、提問清冊、作戰計畫（含架構圖） | `data/report.html`、`questions.html`、`plan.html` + PDF | 完成 |
| 案例 113-16 正本 | `data/poc/00_標準答案_113-16_原決定書.md` | 完成 |
| 模擬訴願書、模擬書面告誡（文字稿） | `data/poc/01_`、`02_` | 完成；尚未手寫／列印拍照 |
| 各階段 JSON 契約 S0–S5 | `data/poc/03_介面規格.md` | **凍結** |
| 決定書模板（駁回／撤銷／不受理） | `data/poc/04_決定書模板.json` | 完成 |
| few-shot（113-15、114-15） | `data/poc/05_few_shot.json` | 完成 |
| 標準答案引用清單＋五個論理要點 | `data/poc/06_標準答案_引用清單.json` | 完成 |
| 檢核器（30 項；正本 30/30、弱草稿 9/30） | `data/poc/07_檢核.py` | 完成，可 import |
| demo 腳本、生成 system prompt | `data/poc/08_`、`09_` | 完成 |
| 前端 | repo `f2e/`（E 負責） | **已接真 API**：`src/api.ts`（POST/GET/health）、`App.vue` 資料流改輪詢 envelope、`demo.ts` 改 `stagesFrom()+buildView()`；版型未動。「載入示範案件」仍走 fixture 保底；後端掛掉顯示錯誤不退回假資料 |
| GET envelope、段落引用映射、S5 形狀 | `data/poc/03_介面規格.md` 附錄 A/B/C | 已補定；後端與前端皆照此實作 |
| 00／03 教示法院修正 | `data/poc/00_`、`03_` | 已修正；**repo 的 `f2e/data/poc/` 與根目錄 `data/poc/` 已同步為修正版** |
| 後端 | repo `backend/` | **完成（stub 模式）**：FastAPI + 四個 stub adapters + 真的 `rules.py`（30 日含休息日順延、寄存送達、77(3)/(8)、96 條瑕疵）+ `checker.py` 包裝 + pytest 全綠。`bedrock.py`：四段皆已接 AWS（aws-test-95 做的），Generate 實測 S5 29/31（S2→S5 約 77 s，citations 11 筆全 grounded）。細節見 `backend/README.md` |
| 法條／判解查表 | repo `data/statutes.json`（全量 2,214 條）、`data/precedents.json` | 由 `backend/tools/extract_*.py` 從主辦方 PDF 切出；stub 只用其中 洗防法 22、訴願法 79、行政罰法 7 與三篇判解（最高行 108 判 531、109 上 780、北高行 114 簡上 13） |
| Knowledge Base | AWS `ZOMMOWFOT2`（語料 `s3://mo-juan-mo-renzhen-kb-text`，由 `backend/tools/build_kb_corpus.py` 產） | aws-test-95 建；隊友的 `6Z7LGUSCJN` 是亂碼不要用。細節見 `backend/README.md`「Knowledge Base」 |
| 前端保底 fixture | repo `f2e/src/data/pipeline.json` | 已改為附錄 A envelope（`cd backend && python -m app.fixture` 產出，30/31）；E 的 `scripts/build-demo-fixture.py` 已標棄用 |

---

## 2. 本 session 已完成的任務（保留規格供對照；驗收結果見 2.4）

### 2.0 工作位置
- `git clone https://github.com/guitimliu/mo-juan-mo-renzhen` 到 `/home/james/projects/hackathon/mo-juan-mo-renzhen`，開分支 `backend`。
- 後端放在 repo 根目錄 `backend/`（與 `f2e/` 並列，E 的 README 已預留）。
- 本專案的 `data/poc/` 是工作包的**唯一真相來源**：把它整份複製覆蓋 repo 內的 `f2e/data/poc/`（E 的副本有教示法院舊錯），並在 repo 根目錄也放一份 `data/poc/`，後端從 `../data/poc` 讀。
- 這個 hackathon 目錄本身不必 git init。

### 2.1 後端 `backend/`（Python 3.12，FastAPI + uvicorn）

```
backend/
  app/
    main.py            # FastAPI：CORS、路由
    store.py           # in-memory case store（dict），不用 DB
    pipeline.py        # run_case(case_id)：依序 S1→S2→S2.5→S3→S4→S5，每步寫回 store，失敗記 error 不中斷後續可跑的步
    rules.py           # S2.5 程序檢核（真的規則，不是 stub）
    checker.py         # 薄包裝：import data/poc/07_檢核.py 的 check()
    adapters/
      base.py          # Protocol：OCRAdapter.run(images)->S1；ExtractAdapter.run(S1)->S2；RetrievalAdapter.run(S2)->S3；GenerateAdapter.run(S2,S2_5,S3)->S4
      stub.py          # 四個 Stub*：讀 data/poc 的固定內容
      bedrock.py       # 先留空殼（NotImplementedError），介面同 base
    settings.py        # ADAPTER=stub|bedrock（env），DATA_DIR
  tests/
    test_rules.py      # 30 日、寄存送達、77 條各款
    test_pipeline.py   # 用 stub 跑 113-16 → 檢核 30/30
  requirements.txt     # fastapi uvicorn[standard] python-multipart pytest httpx
  README.md
```

**API**（03_介面規格.md S0 ＋ 附錄 A/B/C，**照附錄的欄位名與 enum，不要自創**）
- `GET /api/health` → `{status, adapter_mode}`
- `POST /api/cases`　multipart：`petition_image`、`disposition_image`（stub 模式下影像內容不重要，但欄位要收、大小上限 10 MB 與 E 一致）→ `{case_id}`；背景執行 pipeline（`BackgroundTasks` 即可）
- `GET /api/cases/{case_id}` → 附錄 A 的 envelope；每階段 `{status, data, error, elapsed_ms}`
- `GET /api/cases` → 列表（demo 用）
- stub 模式每階段 `await asyncio.sleep(1.5)`，讓前端六區塊逐一出現（E 的模擬流程約 12 秒，節奏對齊）
- 路徑前綴 `/api`；E 的 `.env.example` 用 `VITE_API_BASE_URL=http://localhost:8000`，後端 CORS 允許 `http://localhost:5173`

**Stub 行為**（讓前端有真實感、檢核能拿 30/30）
- `StubOCR`：回 `01_模擬訴願書.md`、`02_模擬書面告誡.md` 去掉 markdown 標記後的純文字；`ocr_confidence_note` 填「stub：未實際辨識」
- `StubExtract`：回 03 規格裡的 S2 範例（依 01/02 內容補齊欄位；`served_date` 113-09-02、`petition_filed_date` 113-09-05）
- `StubRetrieval`：回 S3；`statutes` 至少含洗錢防制法 22 條 1、2 項與訴願法 79 條 1 項的**條文全文**（條文在 `00_標準答案` 理由第一項有逐字引用，可取用）；`precedents` 含最高行 108 判 531、109 上 780（摘要可從 `data/petitions.jsonl` 的 113-15 理由欄擷取）；`similar_cases` 含 113-15（駁回）、114-18（撤銷），欄位照規格
- `StubGenerate`：把 `00_標準答案` 轉成 S4（`07_檢核.py` 的 `draft_from_gold()` 已經會做，直接用），`citations` 依附錄 B 帶 `section`／`index`，`gaps` 列三篇不在資料集的判決
- 所有 stub 輸出可以直接參考 E 的 `f2e/src/data/pipeline.json`（s1/s2/procedure/s3/s4/s5 六段）——那是 E 用 `scripts/build-demo-fixture.py` 從同一份工作包產的，欄位對齊即可，但 envelope 要用附錄 A
- **README 與前端都要標明 stub 模式輸出＝正本改寫，不是 AI 生成**，避免 demo 誤導

**rules.py（真規則）**
- 訴願法 14 條：`filed - served <= 30` 天；輸入含 `service_method: "direct|deposit"`，寄存送達以寄存日視為送達日（法務部 93 法律字 0930014628）
- 77(3)：訴願人是否＝處分相對人（比對 S2 `appellant.name` 與處分書受處分人）
- 77(8)：處分類型是否在行政處分白名單（書面告誡、裁處書、罰鍰處分書…）；「函」「陳情回覆」→ 非處分
- 撤銷前置檢核：處分書 `facts` 是否空白／缺理由（行政程序法 96 條）→ `defect_flags`；這是第二場景 114-18 的觸發點
- 輸出格式照 03 的 S2.5，每條 `{rule, pass, note, inputs}`

### 2.2 前端串接（E 的 `f2e/`，本次只做最小改動）

前端已有全部六區塊與假資料。本次要做的只有「把資料來源從 fixture 換成 API」：
- 新增 `src/api.ts`：`createCase(files)`、`getCase(id)`，base URL 讀 `import.meta.env.VITE_API_BASE_URL`
- `App.vue` 的「開始模擬分析」改為：POST → 取 case_id → 每 1.5 s GET → 依 `stages.*.status` 推進 `ProcessingStatus`，`data` 餵進現有的 `demo.ts` 轉換
- 保留「載入示範案件」按鈕走 fixture（後端掛掉時的保底）
- 頂部依 `GET /api/health` 的 `adapter_mode` 顯示「示範資料（stub）」標籤
- **不要動版型與元件結構**；改動集中在 `api.ts`、`App.vue` 的資料流、`demo.ts` 的 envelope 解包。改完在 `f2e/docs/backend-integration.md` 把「尚未定義」段落改成指向 03 附錄 A/B/C。

### 2.3 驗收（本次 session 結束前必須全部成立）
1. `cd backend && pytest` 全綠；`test_pipeline` 斷言：不帶 retrieval 檢核 30/30、帶 stub retrieval 30/31（唯一 ✘ 為「引用判決皆在檢索結果內」，屬預期）
2. 兩個終端：`cd backend && uvicorn app.main:app --reload --port 8000`、`cd f2e && npm run dev` → 瀏覽器上傳任意兩張圖 → 六個區塊隨階段逐一出現，內容來自 API 而非 fixture（關掉後端再按一次，應顯示錯誤而非假資料）
3. `curl -F petition_image=@a.jpg -F disposition_image=@b.jpg localhost:8000/api/cases` → 拿 id → `curl localhost:8000/api/cases/{id}` 回附錄 A 格式
4. 分支 `backend` 有 commit 且 push；`backend/README.md` 寫清楚啟動、adapter 切換、之後接 Bedrock 要改哪個檔；`f2e/data/poc` 已同步為修正版
5. 不要改 `f2e/` 的版型；不要改 `03_介面規格.md` 正文（附錄可補充）

---

### 2.4 驗收結果（2026-09-12 實測）
1. `cd backend && pytest` → **全綠（108，含 aws-test-95 的 Bedrock 假 client 測試）**；`test_pipeline` 斷言不帶檢索 30/30、帶 stub 檢索 30/31（唯一 ✘「引用判決皆在檢索結果內」）成立。
2. 兩個終端起 uvicorn（本機 8000 被別的 docker 服務占用，實測用 `--port 8011` 並改 `f2e/.env`）＋ `npm run dev`；Playwright 實測：上傳兩張圖 → 六步進度 9.2 s 內依序完成、各區塊由 API 填入（案號 poc-001、教示為臺北高等行政法院、10 筆段落引用 chip 顯示條項、3 條 gaps、檢核 30/31）；關掉後端再按 → 「分析失敗：無法連線後端」，區塊停用，不出現假資料；「載入示範案件」仍可看 fixture。
3. `curl -F petition_image=@a.jpg -F disposition_image=@b.jpg :8011/api/cases` → 202 `{"case_id":"poc-001"}`；`GET /api/cases/poc-001` 回附錄 A 形狀，t+0.5 s `S1 running`、t+4 s `S2_5 running`、t+10 s `done`。
4. 分支 `backend` 已 commit 並 push；`backend/README.md` 寫了啟動、adapter 切換、接 Bedrock 要改哪個檔；`f2e/data/poc` 已同步。
5. 未改 `f2e/` 版型（只改資料綁定與文字、`ProcessingStatus` 加 `error`/`note` 兩個 prop）；未改 `03_介面規格.md` 正文。

規格沒寫、後端自己決定的細節列在 `backend/README.md`「規格沒寫到、這裡自己決定的細節」。
commit 前跑過一輪 5 面向 × 2 反駁者的對抗審查（85 個 agent），確認 37 項、已修 30 項（規則引擎休息日順延／送達方式別名／姓名正規化／函形式處分、checker 型別寬容與引用比對、前端 source 保底／選檔清空／逾時／chip 顯示條項、文件），未修的 7 項屬設計取捨或另一 session 範圍（S2.5 失敗後 S3 仍跑＝HANDOFF 要求；舊 fixture 相容只保證不炸；Bedrock 文件由 aws-test-95 維護）。

### 2.5 Docker Compose（2026-09-12 16:00 加）
- `docker-compose.yml`：`backend`（`backend/Dockerfile`，context 是 repo 根目錄以便包 `data/`，healthcheck）＋ `frontend`（`f2e/Dockerfile` 多階段 build → nginx，`f2e/nginx.conf` 把 `/api/` 代理到 `backend:8000`，同源不需 CORS）。
- `cp .env.example .env && docker compose up --build` → http://localhost:8080；Bedrock 模式在 `.env` 填 `ADAPTER=bedrock` 與 AWS 憑證（env_file 只在有填時帶進容器）。
- aws-test-95 實測 Docker **bedrock 模式**：`.env` 填 `ADAPTER=bedrock`＋AWS 三變數 → 六階段全 done，116 s，S5 28/31；前端輪詢逾時已放寬到 300 s（`f2e/src/api.ts`）。main 的 PR #3（Slidev 簡報 `slides/`）也已併進 backend 分支。
- 本機 8080/8000 被別的容器占用，本機 `.env` 設 `FRONTEND_PORT=8093`、`BACKEND_PORT=8012`；實測：nginx → `/api/health` OK、POST（含 `service_date`）→ 9 s 六階段 done、S5 30/31；Playwright 走 E v2 介面：五步進度、區塊由 API 填入、PDF／Word 匯出 OK。
- 合併 E 的 v2 時保留：`showDeveloperChecks=false` 隱藏第 6 步（後端仍算 S5）、送達日期欄位（現在會以 `service_date` POST 給後端覆蓋 S2.served_date）、匯出模組改吃目前 view（案號＝case_id）。

## 3. 之後要接的（介面已留好）
- `backend/app/adapters/bedrock.py`：**四段已接 AWS（KB `ZOMMOWFOT2`）；模型預設全階段 Claude Sonnet 5（`BEDROCK_MODEL_ID`，可整體或分階段用環境變數改），黑客松帳戶拿不到 Sonnet 5 時自動降級 `BEDROCK_FALLBACK_MODEL_ID`（Sonnet 4.6），`/api/health` 會顯示實際模型；Generate 實測 S5 29/31（4.5 與 4.6 皆 29/31）**，剩 2 分是正本才有的 LINE 對話內容（輸入文件沒有），不再追。要再調就改 system prompt（`data/poc/09_生成提示詞.md`＋`04`＋`05`）與後處理（`stub.build_citations()`／`find_gaps()`）。細節與環境變數見 `backend/README.md`「Bedrock 模式」「之後接 Bedrock 要改哪裡」。
- 啟動 `ADAPTER=bedrock uvicorn app.main:app`（需 AWS 憑證；主辦方憑證是臨時的），其他檔不用動；前端頂部標籤會自動顯示 `bedrock`。
- 部署：EC2 一台跑 uvicorn＋靜態前端即可；區域 us-east-1。

## 4. 已知坑
- E 的 README 說「Node.js 24 LTS」，本機是 Node 22.19；Vite 8 需要 Node ≥ 20.19，可以跑。若 `npm install` 抱怨 engines，用 `npm install --engine-strict=false`。
- fixture 現在由後端產（`cd backend && python -m app.fixture`），是附錄 A envelope；**不要再跑 E 的 `f2e/scripts/build-demo-fixture.py`**（已標棄用，會寫回舊形狀舊內容）。
- 本機 port 8000 被別的 docker 容器占用；用 `--port 8011` 並同步改 `f2e/.env` 的 `VITE_API_BASE_URL`。
- `pkill -f "uvicorn app.main:app"` 會連同含該字串的 shell 一起殺掉；用 `pkill -f "port 8011"` 之類更短的 pattern，或記 PID。
- WeasyPrint 不套頁面 CSS 進 SVG（只影響報告 PDF，與本次無關）。
- `07_檢核.py` 用檔名含中文與數字開頭，import 時用 `importlib.util.spec_from_file_location`。
- 資料集裡沒有真實訴願書，01/02 是逆推的模擬件；主辦方 Q&A 若拿到真實範本，優先替換。

## §V 繳交影片（2026-09-13 交接，aws-test session）

**現況**：影片產線全部可重現（`video/README.md`）。唯一未完成：把修好的 Demo 場景接回成品。機器在 ffmpeg 接回時當機兩次（疑記憶體），所以改用保守設定。

| 檔案（都在 `video/`） | 狀態 |
|---|---|
| `narration.json` ＋ `assets/generated/tts/*.wav`（12 句，Leda） | ✅ 每句經 Gemini 聽寫驗證（`tts_report.md`） |
| `assets/generated/demo_cfr.mp4`（Playwright 實錄 164 s） | ✅ |
| `remotion/out/final.mp4`（v1，4:49；**音軌正確**，3:23–3:43 畫面黑） | ✅ 音軌沿用 |
| `remotion/out/demo_scene.mp4`（修正後 Demo 場景，3018 幀） | ✅ 已驗證不黑 |
| `remotion/out/final_v2.mp4`（＝`out/mjmr_demo_video.mp4`） | ✅ 2026-09-13 以下方分段流程接回完成；8669 幀 / 289 s；已驗證 122–224 s 不黑、150 s 字幕單層、有聲。預覽版 `final_v2_preview.mp4`（CRF 24，20 MB） |

**黑畫面根因**：Remotion `OffthreadVideo` 的 `endAt` 以合成幀數計、不隨 `playbackRate` 換算，0.72× 慢放段 25 s 後無畫面。已修（`c2b5954`：移除 endAt、尾端 `<Freeze>`、加 `Demo` 獨立 composition）。

**已完成的分段、低記憶體作法（單一 filter_complex 版本讓機器當機三次，勿再用）**，在 `video/remotion/` 逐步執行，每步獨立、各約 1–3 分鐘，記憶體無壓力。**注意：步驟 2 不要燒 `06b.ass`**——`demo_scene.mp4` 是在 `509e23d` 之後 render 的，Remotion 已內建 06b 字幕（`scenes.tsx` 的 `<Narration id="06b_demo_wait">`），再燒會變雙層字幕（第一次接回時即踩到，已重做 partB）：
```bash
# 0. 音軌（沿用 v1，含全部旁白）
ffmpeg -y -i out/final.mp4 -vn -c:a copy out/audio.m4a
# 1. 前段視訊 frame 0–3674（0–122.5 s）
ffmpeg -y -i out/final.mp4 -an -vf "trim=end_frame=3675,setpts=PTS-STARTPTS" -c:v libx264 -preset veryfast -threads 1 -crf 18 -pix_fmt yuv420p out/partA.mp4
# 2. Demo 段：修好的 demo_scene.mp4 重編成同參數（字幕已由 Remotion 內建，勿再燒 06b.ass）
ffmpeg -y -i out/demo_scene.mp4 -an -c:v libx264 -preset veryfast -threads 1 -crf 18 -pix_fmt yuv420p out/partB.mp4
# 3. 後段視訊 frame 6693–end（223.1 s–）
ffmpeg -y -i out/final.mp4 -an -vf "trim=start_frame=6693,setpts=PTS-STARTPTS" -c:v libx264 -preset veryfast -threads 1 -crf 18 -pix_fmt yuv420p out/partC.mp4
# 4. 串接（同編碼，不重編碼，幾乎不吃記憶體）＋ 合音軌
printf "file 'partA.mp4'\nfile 'partB.mp4'\nfile 'partC.mp4'\n" > out/concat.txt
ffmpeg -y -f concat -safe 0 -i out/concat.txt -i out/audio.m4a -c copy -movflags +faststart out/final_v2.mp4
```
驗證：`ffprobe` 總長 ≈ 289 s；`ffmpeg -ss 205 -i out/final_v2.mp4 -frames:v 1 x.png` 不黑；150 s 有 06b 字幕；`-af volumedetect` 140／180／200 s 有聲。完成後 `cp out/final_v2.mp4 ../out/mjmr_demo_video.mp4`；要傳人看再出 CRF 24 預覽版（< 30 MB）。
若仍當機：先 `docker stop $(docker ps -q)` 釋放記憶體，並檢查 `%UserProfile%\.wslconfig` 的 `memory=` 上限。

**若要改內容**：改 `narration.json` → `python tts.py`（只重生變動句）→ 複製 wav 到 `remotion/public/tts/` → 重建 `src/timeline.json` → `npm run render`（全片 45 分鐘；或只 render `Demo` composition 再用上面 ffmpeg 接回）。金鑰在 `video/.env`（gitignore）。
