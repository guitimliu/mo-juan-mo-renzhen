# backend — 訴願 POC 後端（FastAPI）

輸入訴願書＋處分書影像 → S1 OCR → S2 案件摘要 → S2.5 程序檢核 → S3 檢索 → S4 決定書草稿 → S5 正本比對檢核。
契約：`../data/poc/03_介面規格.md`（S0–S5 ＋ 附錄 A/B/C，**已凍結**）。

> **stub 模式的輸出＝工作包正本改寫，不是 AI 生成。** S4 草稿是 `data/poc/00` 正本經 `07_檢核.py` 的 `draft_from_gold()` 轉出來的，
> S1 是 01/02 模擬文件的純文字，S3 是查表。demo 時請照實說明；前端也在頁面上標示。

## 啟動

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate        # 或 uv venv .venv && . .venv/bin/activate（uv 建的 venv 沒有 pip，請配 uv pip）
python -m pip install -r requirements.txt            # 或 uv pip install -r requirements.txt；需要 pdftotext（poppler-utils）才能跑 tools/
uvicorn app.main:app --reload --port 8000
```

前端 `f2e/.env.example` 預設 `VITE_API_BASE_URL=http://localhost:8000`；CORS 已允許 `http://localhost:5173`。
（本機 8000 被別的服務占用時改 `--port 8011`，並把 `f2e/.env` 的 `VITE_API_BASE_URL` 改成一樣的埠。）

```bash
pytest                                                # 全綠；test_pipeline 斷言 30/30（不帶檢索）、30/31（帶 stub 檢索）
python -m app.fixture                                 # 用 stub pipeline 重產前端保底 fixture f2e/src/data/pipeline.json（附錄 A 形狀）
```

## API（前綴 `/api`）

| 方法 | 路徑 | 說明 |
|---|---|---|
| POST | `/api/login` | body `{username, password}` → `{auth_required, token, expires_at, username}`；帳密來自 `AUTH_USERNAME`／`AUTH_PASSWORD`，沒設則回 `auth_required:false`（不用登入）。錯誤 401 |
| GET | `/api/me` | 目前登入者（需 Bearer token；驗證關閉時 username 為 null） |
| GET | `/api/health` | `{status:"ok", adapter_mode:"stub"\|"bedrock", models?:{…}}`（bedrock 模式多回各階段模型與降級狀態） |
| POST | `/api/cases` | multipart `petition_image`、`disposition_image`（JPG/PNG/WebP，各 ≤ 10 MB）＋選填 `service_date`（前端「送達日期」欄；YYYY-MM-DD 或民國 YYY-MM-DD，解析失敗 422）→ **202** `{case_id}`；pipeline 在 BackgroundTasks 跑 |
| GET | `/api/cases/{case_id}` | 附錄 A envelope：`{case_id, status, current_stage, adapter_mode, created_at, updated_at, stages{S1,S2,S2_5,S3,S4,S5:{status,data,error,elapsed_ms}}, error}`；不存在 404 |
| GET | `/api/cases` | `{cases:[envelope 去掉 stages.data]}`，新的在前（demo 用） |

```bash
curl -F petition_image=@a.jpg -F disposition_image=@b.jpg localhost:8000/api/cases   # → {"case_id":"poc-001"}
curl localhost:8000/api/cases/poc-001 | jq '.status, .current_stage, (.stages|map_values(.status))'
```

## 目錄

```
app/
  main.py          FastAPI：CORS、路由、上傳驗證（create_app() 可注入 adapters/store/delay 供測試）
  settings.py      ADAPTER=stub|bedrock、DATA_DIR、STUB_STAGE_DELAY_S、MAX_UPLOAD_BYTES、CORS_ORIGINS（皆可用環境變數覆蓋）
  store.py         in-memory dict；Case.to_envelope() 就是附錄 A
  pipeline.py      run_case()：S1→S2→S2.5→S3→S4→S5，每步寫回 store；失敗處理見下
  rules.py         S2.5 程序檢核，純規則（真的，不是 stub）
  checker.py       薄包裝 data/poc/07_檢核.py，另算附錄 C 的 summary
  fixture.py       python -m app.fixture → 產前端保底 fixture
  adapters/
    base.py        Protocol：OCRAdapter / ExtractAdapter / RetrievalAdapter / GenerateAdapter（全部 async run）
    stub.py        四個 Stub*，內容從 ../data 讀
    bedrock.py     OCR（Claude 多模態）、Extract（Claude → S2 JSON ＋ rules.py 補漏）、Retrieval（KB 三次 retrieve ＋ statutes.json 查表 ＋ Claude 篩選／寫 why_similar）、Generate（主文由 S2.5 規則決定，Claude 依 09＋04＋05 生成，citations/gaps 走 stub 同一套後處理）四段全部接 AWS；共用 1 RPS RateLimiter＋Throttling 退避
tools/
  extract_statutes.py    相關法規 PDF → data/statutes.json（洗防法 22；訴願法 14/18/77/79/81；行政程序法 74/96/114；行政罰法 7）
  extract_precedents.py  判解 PDF → data/precedents.json（最高行 108 判 531、109 上 780、北高行 114 簡上 13）
tests/
  test_rules.py     30 日（含休息日順延）、寄存送達、77(3)、77(8)、96 條瑕疵、S2→S2.5 整合
  test_pipeline.py  stub 跑 113-16 → 30/30、30/31；附錄 B/C 形狀；失敗傳播；四個 Bedrock adapter（假 client）＋ bedrock 全管線 S1～S5 done
  test_api.py       health、POST/GET、422/415/400/413、404、CORS、啟動缺檔 fail-fast
  test_checker.py   07 包裝：30/30、弱草稿幻覺法條、_covered 精確比對、citation_grounded 要 text 對得上 source、壞型別不炸
```

## 程序檢核 rules.py（S2.5）

輸入 S2（＋S1 的處分書全文），輸出 `{admissible, needs_review[], checks[], defect_flags[]}`；每條 check 至少含 `rule, pass, note, inputs`。

| rule | 規則 | 備註 |
|---|---|---|
| 訴願法14條 30日 | 提起日 ≤ 送達日＋30 日（訴願法 14 I，自送達之次日起算）；末日遇週六日／國定假日依民法第122條順延到次一工作日（訴願法 17 條） | `service_method` 接受 direct/deposit 與中文別名（寄存、寄存送達）；deposit 以 `deposit_date` 為送達日（法務部 93.4.13 法律字 0930014628）；假日表只列固定假日＋113–115 年農曆假日，所以「逾期 ≤ 3 天」一律 `needs_review`；另帶 `served/filed/days` 欄位（同規格範例） |
| 訴願法77(3) 當事人適格 | S2 `appellant.name` ＝ 處分書受處分人 | 受處分人優先取 S2 `disposition.addressee`，沒有就從處分書全文抓「受告誡人：」等欄位；姓名去空白、去「先生／小姐」尾綴與標點；含「○」遮罩視為萬用字元但 `needs_review` |
| 訴願法77(8) 行政處分 | `disposition.type` 在處分白名單（書面告誡、裁處書、罰鍰處分書…） | 「陳情回覆」→ 非處分；「函」「通知」與「不予／撤銷…」開頭 → `needs_review`（須實質認定） |
| 行政程序法96條 處分書應記載事項 | 處分書「事實」「理由」「法令依據」是否空白／缺漏 | 撤銷前置檢核（114-18 場景）；結果進 `defect_flags`，**不影響 `admissible`**；函形式（主旨／說明）不報欄位缺漏改 `needs_review`；同標籤重複出現合併不覆蓋 |

- `admissible` = 三條訴願法規則皆 pass。無法判定（缺日期、認不出受處分人、未知處分類型、送達方式未知、寄存送達缺寄存日）→ `needs_review:true`，留給人判斷，不猜。
- 在途期間（訴願法 16 條）未實作，note 會提醒。
- 對外函式簽名（`parse_roc_date`、`to_roc`、`extract_addressee`、`parse_disposition_sections`、`check_procedure`）供 `adapters/bedrock.py` 的 Extract 後處理共用。

## Pipeline 失敗處理

- 某步丟例外：該步 `status:"error"`、`error:"ExcType: msg"`；依賴它的後續步 `status:"skipped"`（error 註明上游）；不依賴的步照跑（S3 失敗時 S2.5 仍完成）。
- 整體 `status`：全部 done → `done`；任一步 error → `error`，`envelope.error` 記第一個失敗階段。
- 依賴：S2←S1；S2.5←S2（＋S1 全文）；S3←S2；S4←S2,S2.5,S3；S5←S4（S3 有就帶）。

## 規格沒寫到、這裡自己決定的細節

- `POST /api/cases` 回 **202 Accepted**（非同步處理；`fetch` 的 `res.ok` 仍為 true）。
- `case_id` 為 process 內流水號 `poc-001`、`poc-002`…（同規格範例；重啟歸零，store 本來就是 in-memory）。
- 時間戳 ISO 8601 帶固定 `+08:00`（不查系統 tz 資料庫，Windows 沒裝 tzdata 也能跑），秒精度。
- `elapsed_ms` 只計實際工作時間，**不含** stub 的 1.5 s 模擬延遲（規格範例 S2_5 為 5 ms 的精神）。
- stub 延遲套用在六步全部（含 S2.5、S5），總長約 9 s，接近 E 原本 12 s 的節奏；`STUB_STAGE_DELAY_S=0` 可關。
- 上傳驗證：content-type 不在 JPG/PNG/WebP → 415；空檔 → 400；> 10 MB → 413（先看 `UploadFile.size` 再讀）；缺欄位 → 422（FastAPI 預設）。
- 啟動時 `check_data_files()` 確認 `DATA_DIR` 下 poc/、statutes.json、precedents.json、petitions.jsonl 齊全，缺就 RuntimeError，不等到第一件才在 S1 失敗。
- S2 附加了規格外欄位 `disposition.addressee`、`service_method`（給 rules.py 用；前端忽略）。S3 每筆附加 `source`（來源檔）、相似案附加 `case_type/holding/agency/decided/excerpt`；S4 附加 `provenance`（stub 標示）。附錄 A/B/C 的欄位名與 enum 一律未改。
- S5 `summary.citation_grounded`：source 要指到 S3 裡存在的項目**且** text 要對得上（法條以「法第N條」起首、其餘比 id），幻覺引用寫 `statutes[0]` 也不算有據。`checker.run()` 對 S4/S3 先做型別寬容（非 dict/list 降級成空），生成格式稍有出入不會讓整個案件 error。
- S5 `summary.gold_citations_recalled/missed`：有檢索結果時＝標準答案引用是否被 S3 涵蓋（同規格範例：正本三篇簡字判決列 missed）；沒有檢索結果時退回「草稿本文是否出現」。
- `GET /api/cases` 回 `{cases:[…]}` 而非裸陣列。
- `service_date` 有填時，S2 完成後直接覆蓋 `served_date`（民國格式）並加 `served_date_source:"user"`——承辦人依送達證明填的日期比 OCR／LLM 擷取可靠。
- Docker：`backend/Dockerfile`（context 是 repo 根目錄，因為要 `data/`）；`docker compose up --build` 見根目錄 README。
- 沒有取消端點（附錄 A）；前端「停止」只停輪詢。
- 法條／判解摘要不是手打的：`tools/extract_*.py` 從主辦方 PDF 切出來，存 `data/statutes.json`、`data/precedents.json`（含 `source`）。`data/petitions.jsonl` 是 101 件歷史決定書結構化資料（從 hackathon 目錄同步）。

## 個資前處理（`app/pii.py`，取代法）

黑客松規範第 2 條「AWS 帳戶內不放個資」。S1 OCR 一回來、任何文字送 Bedrock 之前，`pipeline.py` 用**純規則**（不呼叫模型）偵測並取代：

| 類別 | 偵測 | 取代 |
|---|---|---|
| 姓名 | 「訴願人／受告誡人／代理人…：」標籤後 2–4 字（已遮罩的 陳○超 不動） | 代號 **甲○○／乙○○…**，同一人全文一致 |
| 身分證 | `[A-Z][12]\d{8}` | `A1○○○○○○○○` |
| 電話 | 市話／手機 | `○○○○-○○○-○○○` |
| 門牌地址 | 縣市區＋路段號樓 | 保留縣市區（管轄），`○○路○段○○號` |
| 出生年月日 | 「出生年月日：」後的日期 | 保留年（訴願能力），月日 `○` |

- 對照表只在 `Case.pii_map`（記憶體），**不進 envelope、不進 log、不上 AWS**；envelope 多 `pii` 摘要 `{mode, replaced:{name,id,phone,address,dob}, codes}`，S1 的 `ocr_confidence_note` 前面會寫「已去識別化（取代法）：姓名×3、…」讓前端 OCR 頁直接看到。
- S2／S3／S4 送模型的全是代號版；規則引擎「訴願人＝處分相對人」用代號比對照樣成立。**S4 草稿產出後只還原姓名**（身分證／地址本來就不該出現在決定書）；S2 保持代號版當作「送出去的證據」。
- 開關 `PII_MASK`：`auto`（預設；bedrock 開、stub 關）／`1`／`0`。
- 實測（demo 影像含虛構的 0912-345-678、A123456789、北新路二段88號5樓）：S1～S3 envelope 完全不含原值，S4 還原「訴願人王小明」，S2.5 四項 PASS，全鏈 103 s。影像本身仍須送 OCR（無法避免），demo 影像是虛構資料。

## 登入（`app/auth.py`，環境變數設定）

- `AUTH_USERNAME`＋`AUTH_PASSWORD` **都設**才啟用：前端會先出現登入頁，`/api/cases*` 要帶 `Authorization: Bearer <token>`（`POST /api/login` 取得）；`/api/health` 不用登入並回 `auth_required`。任一沒設＝不驗證，本機開發／stub demo 直接用。
- token 是 HMAC 簽章的 `username:expires`（無狀態）；`AUTH_SECRET` 沒設就每次啟動隨機（重啟後要重新登入），`AUTH_TOKEN_TTL_S` 預設 12 小時。單一帳號、`hmac.compare_digest` 比對；POC 規模夠用。
- 前端把 token 放 localStorage，任何 401 會自動清掉並切回登入頁；側欄有登出。

## Demo 文件（一鍵測試）

前端「文件上傳」有兩顆按鈕：**載入 Demo 文件**（把 `f2e/public/demo/petition.jpg`、`disposition.jpg` 填進兩個上傳格）與 **一鍵 Demo（載入並分析）**。這兩張是 `data/poc/01`／`02` 模擬文件渲染成的 JPG（人名帳號皆虛構、稍微歪斜模擬拍照），bedrock 模式實測全鏈約 105–120 s、S5 28–29/31。

## Bedrock 模式（四段全通）

```bash
uv pip install -r requirements.txt            # 多了 boto3
export AWS_PROFILE=hackathon                  # ~/.aws/credentials 的 profile；或直接 export AWS_ACCESS_KEY_ID／SECRET／SESSION_TOKEN
ADAPTER=bedrock uvicorn app.main:app --reload --port 8000
```
- **模型設定（使用者可自行設定）**：`BEDROCK_MODEL_ID` 是四階段共同預設（**`us.anthropic.claude-sonnet-5`**）；`BEDROCK_OCR_MODEL_ID`／`BEDROCK_EXTRACT_MODEL_ID`／`BEDROCK_RETRIEVAL_MODEL_ID`／`BEDROCK_GENERATE_MODEL_ID` 可個別覆寫（Claude 要用 `us.` 開頭的 inference profile）。`BEDROCK_FALLBACK_MODEL_ID`（預設 `us.anthropic.claude-sonnet-4-6`）：預設模型在此帳戶被拒（`AccessDeniedException: not available for this account`）時自動降級並記住，log 有 WARNING，`GET /api/health` 的 `models.fallbacks_in_effect` 會列出；設空字串關掉。其他：`BEDROCK_REGION`（us-west-2）、`BEDROCK_KB_ID`（`ZOMMOWFOT2`）、`BEDROCK_OCR_MAX_TOKENS`（4096）、`BEDROCK_GENERATE_MAX_TOKENS`（6000）。
- **黑客松帳戶現況**：Sonnet 5／Opus 5／Fable 5.1 在 Workshop 帳戶回 AccessDenied（模型協議已接受仍被拒，屬帳戶層級封鎖，需 AWS 開通）；可用的最新是 Sonnet 4.6、Opus 4.6、Sonnet 4.5、Haiku 4.5。所以目前實際跑的是 **Sonnet 5 → 自動降級 Sonnet 4.6**；換到正式帳戶不用改設定。
- `GET /api/health` 在 bedrock 模式多回 `models`：`{default, fallback, kb_id, region, stages{ocr|extract|retrieval|generate: {configured, active}}, fallbacks_in_effect}`。
- OCR 每個欄位（訴願書／告誡）各打一次 Converse，同欄位多張影像視為連續頁面合併；模型回 `{text, low_confidence, note}`，低信心片段與觀察寫進 `ocr_confidence_note`。
- 實測列印體 113-16 兩份文件：約 36 s、4k input tokens；訴願書逐字全對，告誡只錯罕見字「嗣」。主辦方憑證是臨時的（ASIA…），過期要重取。
- Extract 一次 Converse（約 10 s、2.2k input tokens）：S1 兩份全文 → S2 JSON；`normalize_s2()` 補齊缺 key、日期正規化為 YYY-MM-DD、`service_method` 限 direct/deposit，並用 `rules.py` 從原文補 addressee／事實／日期；模型不確定的欄位列在 `uncertain`。實測 113-16：結構欄位與 03 規格範例逐字一致，S2.5 四項全 PASS。
- Retrieval（約 7–10 s）：查詢字串由 S2 的案由／處分依據／事實／主張／爭點組成，對 KB 依 `category` 各 retrieve 一次（判解 8、函釋 6、決定書 12 個 chunk），同一份文件多 chunk 合併取最高分；再用一次 Claude 呼叫（`BEDROCK_RETRIEVAL_MODEL_ID`）**篩掉主題無關的判解／函釋**並為相似案各寫一句 `why_similar`（失敗就全留、用固定句）。
  - `statutes`：處分依據 ∪ 相似案裁決依據（訴願法 77／79／81）∪ 保留判解主題條文，精確查 `data/statutes.json`（已全量 2,214 條，`tools/extract_statutes.py` 不加 `--poc`）。
  - `interpretations`：KB 函釋 ＋ 從判決／決定書原文抽出的「洗錢防制法第15條之2立法理由第N點」引文（兩種引用寫法都認），id 與 07 檢核的 gold 一致。
  - `similar_cases`：`doc_no` 對回 `data/petitions.jsonl` 取結果／主文／機關／日期；**用原處分文號數字排除本案自己的決定書**（demo 的 113-16 在語料裡）。
  - 實測 113-16：判解＝114 簡上 13、立法理由第 2/3/5 點、相似案 113-18（撤銷）／113-15（駁回）／114-15；配正本改寫草稿跑 S5，gold 法條＋立法理由全部 recalled，只缺語料裡本來就沒有的三篇簡字判決（與 03 範例相同）。
- Generate（約 80 s、18k input／4.7k output tokens）：**主文版本由規則決定**（09 規則 5：S2.5 `admissible=false` → 不受理版並對回 77 條款次；有 `defect_flags` → 撤銷版；其餘 → 駁回版），模型不得改；system prompt ＝ `09_生成提示詞.md`＋`04_決定書模板.json`＋`05_few_shot.json` 整份；user 帶 S2／S2.5／精簡 S3（每筆標 `statutes[i]` 等 source）。輸出後：`header` 用 S2 覆寫、`holding` 限定模板句、`instruction` 依 04 規則（撤銷不附／其餘臺北高等）、`reasons` 正規化成「一、…」連續編號、`citations` 一律由 `stub.build_citations()` 從本文比對檢索結果產生（模型自己寫的不採信）、`gaps` = `find_gaps()` ＋ 模型標的。
- 改預設 Sonnet 5 後真實重跑（實際降級到 Sonnet 4.6，S2→S5 共 83 s）：S5 **29/31**，與 4.5 持平；降級只發生在第一次呼叫，之後直接用備援。
- Docker Compose bedrock 模式已實測（`.env` 填 `ADAPTER=bedrock`＋三個 AWS 變數）：經 nginx `POST /api/cases` → 六階段全 done，**116 s**（S1 36 s／S2 10 s／S3 7 s／S4 67 s），S5 28/31。因此前端輪詢逾時已從 120 s 放寬到 300 s（`f2e/src/api.ts` `POLL_TIMEOUT_MS`）。同機 8000／8080 被佔時在 `.env` 改 `BACKEND_PORT`／`FRONTEND_PORT`。
- 真實跑 113-16（Sonnet 4.5，S2→S5 共 77 s）：S5 **29/31**——段落 5/5、格式 9/9、結論 3/3、事實 1/1、引用 4/4、防幻覺 3/3、citations 11 筆全 grounded、gaps 空；理由三引了 114 簡上 13 字號、立法理由第 3/5 點、行政罰法 7 條（責任條件）。剩 2 分（R3「LINE 對話顯示訴願人有警覺」、卷內證據 4 項）是正本才有的卷證內容，模擬訴願書／告誡書裡沒有，模型不該自己編——這是輸入資料的天花板，不是 prompt 問題。

## Knowledge Base（S3 檢索用，已建好）

| 項目 | 值 |
|---|---|
| KB ID | `ZOMMOWFOT2`（`mjmr-kb-text-v1`，VECTOR 型，Titan Embed v2 1024d，S3 Vectors `mo-juan-mo-renzhen-vectors/kb-text`） |
| 語料 bucket | `s3://mo-juan-mo-renzhen-kb-text`（data source `HKA97H3WYX`） |
| 語料來源 | `tools/build_kb_corpus.py <PDF 根目錄> data/kb_corpus`：pdftotext 抽 141 篇 → `.txt` ＋ `.txt.metadata.json` |
| metadata 過濾鍵 | `category`（statute／precedent／interpretation／decision）、決定書另有 `year`、`case_type`、`outcome`、`doc_no`（如 `113-16`） |
| 查詢 | `aws bedrock-agent-runtime retrieve --knowledge-base-id ZOMMOWFOT2 --retrieval-query '{"text":"…"}' --retrieval-configuration '{"vectorSearchConfiguration":{"numberOfResults":5,"filter":{"equals":{"key":"category","value":"decision"}}}}'` |

- 為什麼不用隊友的 `6Z7LGUSCJN`：它直接餵 PDF，Bedrock 內建 parser 抽不出中文，所有 chunk 都是亂碼（中文字數 0）；本 KB 用 pdftotext 純文字重建，實測 113-16 案的查詢 top-1 就是正本、法條／判解／函釋都命中。**隊友的 KB 與 `mo-juan-mo-renzhen-s3` 不要動。**
- 更新語料：重跑 `build_kb_corpus.py` → `aws s3 sync data/kb_corpus s3://mo-juan-mo-renzhen-kb-text/ --delete` → `aws bedrock-agent start-ingestion-job --knowledge-base-id ZOMMOWFOT2 --data-source-id HKA97H3WYX`（141 篇約 1 分鐘）。
- Retrieval 實作時記得**排除本案自己的決定書**（doc_no 過濾），不然相似案第一名永遠是答案本身。

## 之後接 Bedrock 要改哪裡

1. 四段都接好了；調 prompt 改 `bedrock.py` 的 `OCR_SYSTEM`／`EXTRACT_SYSTEM`／`SCREEN_SYSTEM`／`BedrockGenerate.run()` 的輸出要求段。
2. Retrieval 已完成（見上）；要調檢索數量／篩選提示詞改 `BedrockRetrieval.run()`／`SCREEN_SYSTEM`。
3. 每次呼叫前 `await limiter.wait()`（`RateLimiter`，≤ 1 RPS）。
4. 啟動時 `ADAPTER=bedrock uvicorn app.main:app …`；其他檔案不用動。
