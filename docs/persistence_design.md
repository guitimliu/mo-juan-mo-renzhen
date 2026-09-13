# 承辦人回頭編輯同一案件：儲存層可行性分析（2026-09-13）

需求：承辦人送出案件後，之後還能回到**同一個案件**（同一顆按鍵／同一列）繼續看、改草稿、重跑；因此上傳的影像、各階段結果、草稿修改都要留下來。目前後端是 in-memory，重啟即清空。

## 1. 現況（backend/app/store.py）

| 項目 | 現在 | 問題 |
|---|---|---|
| 案件 envelope（S1–S5） | `dict` in-memory | uvicorn 重啟／容器重建（換 token 就會）全部消失 |
| 上傳影像 | `UploadedImage` bytes 存在 `Case.images`（記憶體） | 沒落地；多案同時跑吃 RAM；無法回看 |
| PII 對照表 | `Case.pii_map` 只在記憶體、刻意不出本機 | 重啟後 S4 無法還原真名（設計上是優點，要保留這個原則） |
| 草稿 | S4 的 `data` 只有機器產出，沒有「承辦人改過的版本」 | 前端匯出 PDF／Word 後就斷了，沒有版本 |
| 案件列表 | 無 `GET /api/cases` | 前端只能靠 localStorage 記 case_id |
| 身分 | 單一帳號 HMAC token | 多人時分不出誰的案件 |

API 現有：`POST /api/cases`、`GET /api/cases/{id}`、`WS /api/cases/{id}/ws`、`POST /api/login`、`GET /api/health`。

## 2. 要新增的資料模型

```
cases          case_id PK, owner(username), status, current_stage, adapter_mode,
               service_date, created_at, updated_at, error, pii_summary(json)
case_files     file_id PK, case_id FK, field(petition|disposition), filename, content_type,
               size, sha256, storage_key(本機路徑或 S3 key), created_at
stage_results  case_id FK, stage(S1..S5) PK 組合, status, data(json), error, elapsed_ms, run_no
               -- run_no 讓「重跑」保留舊結果
drafts         draft_id PK, case_id FK, version(遞增), base_stage_run(依據哪次 S4),
               content(json：header/holding/facts/reasons/instruction/citations),
               edited_by, edited_at, note(承辦人備註), is_current
audit_log      id, case_id, actor, action(create|rerun|edit_draft|export|view), at, detail(json)
```

- **草稿用版本而不是覆蓋**：`drafts.version` 每存一次 +1，`is_current` 指向最新；「還原成 AI 版本」就是回到 version 1。這是承辦人最需要的功能，也是稽核要求（誰改了 AI 產出的什麼）。
- **PII 對照表不進 DB**：仍只在記憶體；重啟後若要還原真名，改成「承辦人在前端填一次姓名」或「重跑 S1」。若真的要存，必須另用 KMS 加密欄位，並與案件資料分庫——POC 不建議。
- 影像：檔案本體不放 DB，存 S3（或本機 volume），DB 只存 key + sha256。

## 3. 三種做法比較

| | A. SQLite + 本機 volume | B. PostgreSQL（RDS）+ S3 | C. DynamoDB + S3 |
|---|---|---|---|
| 改動量 | 小：`store.py` 換成 SQLAlchemy/SQLModel，一個檔案；compose 加 volume | 中：同 A 的 ORM，多一個 RDS、VPC 安全群組、連線字串 | 中大：資料模型要改成 key-value／單表設計，查詢彈性差 |
| 適合 | 單台 EC2、POC／評審 demo、≤ 數千案 | 正式上線、多實例、多人、報表 | 無伺服器、超大量；此案不需要 |
| 風險 | 單機；EC2 重建就要備份 `.db`（可 cron 丟 S3） | 成本、Workshop 帳戶能否開 RDS 不確定 | 團隊不熟、開發最慢 |
| 遷移 | SQLAlchemy 換連線字串即可升到 B | — | — |

**建議：A 先上（今天可做），ORM 寫法直接相容 B。** 影像先放本機 volume（`/data/uploads/<case_id>/`），介面留 `storage_key`，之後換 S3 只改一個函式。

## 4. 具體改動（估 3–4 小時，不影響現有 API 形狀）

1. `backend/app/db.py`：SQLModel + `sqlite:////data/mjmr.db`（env `DATABASE_URL` 可換 Postgres）；啟動時 `create_all`。
2. `store.py`：`create/get/update_stage` 改寫 DB，`Case` 仍當作記憶體快取（WS 訂閱者、pii_map 留在記憶體）。`to_envelope()` 不變 → 前端零改動。
3. 新 API：
   - `GET /api/cases?owner=me&limit=50` 列表（前端做「我的案件」側欄，就是「同一顆按鍵回來」的入口）
   - `GET /api/cases/{id}/files/{file_id}` 回看原始影像
   - `PUT /api/cases/{id}/draft` 存承辦人修改版（body = S4 形狀 + note）→ 新 version；`GET /api/cases/{id}/drafts` 版本列表；`POST /api/cases/{id}/drafts/{v}/restore`
   - `POST /api/cases/{id}/rerun?from=S3` 從某階段重跑（沿用已存的 S1/S2，不必再上傳）
4. 匯出 PDF／Word 改讀 `drafts.is_current`，不再讀 S4 原始資料。
5. compose：`backend` 加 `volumes: [mjmr-data:/data]`；`.env` 加 `DATABASE_URL`、`UPLOAD_DIR`；每日 `aws s3 cp /data/mjmr.db s3://…/backup/`。
6. 前端（UI 調整中，之後接）：案件列表、草稿編輯區的「儲存」「版本」「還原 AI 版」三顆鍵。

## 5. 要先決定的事

- **保存期限與去識別化**：訴願書影像含身分證字號等，是個資法上的敏感資料。建議 DB 只存去識別化後的 S1 文字與影像 key，影像目錄設保存期限（例如結案 30 天後刪）並加密（S3 SSE-KMS 或 volume 層）。
- **多人**：`AUTH_USERNAME` 單帳號要改成多帳號表（可先 `users` 表 + bcrypt），否則 `owner` 欄位沒意義。
- **同時編輯**：單人承辦不會撞；若多人，`PUT draft` 帶 `base_version` 做樂觀鎖即可。
- Workshop 帳戶若不能開 RDS，A 方案在 EC2 上就能跑完整流程，評審 demo 也夠。

## 6. 結論

可行，而且不需要動 S1–S5 管線與前端的 envelope 契約。最小路徑是 SQLite + volume + 三支草稿 API（版本化），影像先落本機、DB 只存 key；PII 對照表維持不落地。之後正式化再切 RDS + S3，ORM 層不必重寫。
