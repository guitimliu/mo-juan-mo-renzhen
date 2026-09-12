# AgentCore Invoke 範例

用 Python + boto3 呼叫 Amazon Bedrock AgentCore 的 harness，並串流印出回覆。

## 需求

- Python 3.9 以上（建議 3.10+）
- 一組可用的 AWS 憑證，且該帳號／角色有權限呼叫 Bedrock AgentCore

## 安裝

```bash
# 1. 建立並啟用虛擬環境
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. 安裝套件
pip install -r requirements.txt
```

## 設定憑證

任選一種方式。

### 方式 A：使用 .env 檔（推薦，最方便）

```bash
cp .env.example .env
```

打開 `.env` 填入你的 AWS 憑證與 `HARNESS_ARN`。程式啟動時會自動載入。
`.env` 已被 `.gitignore` 忽略，不會被提交。

> 臨時憑證（`ASIA` 開頭）需要同時填 `AWS_SESSION_TOKEN`；
> 長期憑證（`AKIA` 開頭）則不需要。

### 方式 B：使用環境變數（每個終端機視窗設定一次）

```bash
export AWS_DEFAULT_REGION="us-west-2"
export AWS_ACCESS_KEY_ID="你的_access_key_id"
export AWS_SECRET_ACCESS_KEY="你的_secret_access_key"
export AWS_SESSION_TOKEN="你的_session_token"   # 臨時憑證才需要
```

### 方式 C：使用 AWS CLI 設定檔

若已用 `aws configure` 設定過 `~/.aws/credentials`，boto3 會自動採用，無需額外設定。

## 使用

```bash
# 使用預設問候語
python invoke.py

# 自訂要問的內容
python invoke.py "請介紹 AWS Well-Architected 的五大支柱"
```

成功時會串流印出 harness 的回覆。

## 設定項目

| 環境變數 | 說明 | 預設值 |
| --- | --- | --- |
| `AWS_DEFAULT_REGION` | AWS 區域 | `us-west-2` |
| `HARNESS_ARN` | 要呼叫的 harness ARN | 內建範例值 |
| `RUNTIME_SESSION_ID` | 對話 session id | 未設定時自動產生 |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` | AWS 憑證 | 依 boto3 標準解析 |

## 疑難排解

- **`Unable to locate credentials`**：沒設定憑證，或臨時憑證已過期。重新取得憑證後填入。
- **`AccessDeniedException ... aws-marketplace`**：harness 使用的模型需要 AWS Marketplace 訂閱。改用 serverless 模型（例如 Amazon Nova 系列），或請帳號管理員完成模型存取／訂閱設定。
- **程式沒有輸出、疑似卡住**：程式已設定 60 秒讀取逾時，並會攔截串流中的錯誤事件印出 `[錯誤] ...` 訊息。

## 安全提醒

- 切勿把真實憑證寫進程式碼或提交到版控。使用 `.env`（已被忽略）或環境變數。
- 臨時憑證會過期；若不慎外洩，請立即輪替失效。
