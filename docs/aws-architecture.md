# 墨卷莫認真｜AWS 架構圖說明

- 圖檔：`aws-architecture.drawio`（draw.io 原檔，官方 `mxgraph.aws4` 圖示）、`aws-architecture.png`（2× 匯出）、`aws-architecture.svg`。
- 產生方式：依 [vidanov/aws-architecture-diagram-skill](https://github.com/vidanov/aws-architecture-diagram-skill) 的規範（左→右、78px 圖示、strokeWidth 2、≥220px 間距、群組 `container=1`）手寫 mxGraph XML；匯出用自架 `jgraph/drawio` 容器＋embed 協定（`docker run -p 127.0.0.1:8089:8080 jgraph/drawio`，Playwright postMessage `load`→`export`），不經外部服務。

## 資料流
1. 承辦人瀏覽器（帳密登入）→ EC2 上 nginx（frontend）→ FastAPI（backend）：`POST /api/cases`，WebSocket `/api/cases/{id}/ws` 即時進度。
2. S1 OCR：FastAPI → Bedrock Converse（Claude Sonnet 5，帳戶不可用時降級 4.6）。OCR 後先做個資取代（姓名→甲○○，對照表僅存本機）再進後續階段。
3. S2 擷取／S3 篩選／S4 生成（串流）同樣走 Converse；S2.5 程序檢核與 S5 檢核為純規則，不呼叫模型。
4. S3 檢索：法條精確查容器內 `statutes.json`；判解／函釋／決定書向 Bedrock Knowledge Base `ZOMMOWFOT2`（Titan Text Embeddings v2 → S3 Vectors）做三次 Retrieve，排除本案。
5. 離線建置：主辦方 PDF → `tools/build_kb_corpus.py`（pdftotext）→ `aws s3 sync` 到語料 bucket → `start-ingestion-job`。

## 服務
| 服務 | 用途 |
|---|---|
| Amazon EC2 t3.large（Docker Compose：frontend／backend／slides） | 應用主機；SG 只開 22/80/443 |
| Amazon Bedrock Converse API | 四個 AI 階段；全部呼叫共用 ≤ 1 RPS 限流 |
| Amazon Bedrock Knowledge Base ＋ Titan Text Embeddings v2 | 判解／函釋／相似案向量檢索 |
| Amazon S3 Vectors | 向量索引 `mo-juan-mo-renzhen-vectors/kb-text` |
| Amazon S3 | 語料 bucket `mo-juan-mo-renzhen-kb-text`（141 篇純文字＋metadata；Block Public Access） |
| IAM Role | KB 執行角色：S3 讀取、Titan invoke、S3 Vectors |

## 設計決策
- 結論（駁回／撤銷／不受理）由規則引擎決定，模型只負責撰寫；引用只認檢索結果，缺依據列待補查。
- AWS 帳戶內不放個資：影像 OCR 後即去識別化，S2–S4 送模型的是代號版，草稿輸出時本機還原。
- 憑證走 `.env`（gitignore），區域 us-west-2，符合黑客松環境規範。
