"""
呼叫 Amazon Bedrock AgentCore harness 並串流印出回覆。

設定方式（優先順序：命令列參數 > 環境變數 > 預設值）：
- HARNESS_ARN        : harness 的 ARN
- AWS_DEFAULT_REGION : AWS 區域（預設 us-west-2）
- RUNTIME_SESSION_ID : 對話 session id（未設定時自動產生）

AWS 憑證由 boto3 依標準方式解析（環境變數、~/.aws/credentials、IAM role 等）。

使用範例：
    python invoke.py
    python invoke.py "請介紹 AWS Well-Architected 的五大支柱"
"""

import os
import sys
import uuid

import boto3
from botocore.config import Config

# 若有安裝 python-dotenv，且專案根目錄存在 .env，則自動載入
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ---- 設定（可用環境變數覆寫）----
REGION = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
HARNESS_ARN = os.getenv(
    "HARNESS_ARN",
    "arn:aws:bedrock-agentcore:us-west-2:833864702926:harness/harness_jstj4-CRUo6K5B8U",
)
# session id 未設定時自動產生一個，讓多次執行互不干擾
SESSION_ID = os.getenv("RUNTIME_SESSION_ID") or f"session-{uuid.uuid4()}"

# 訊息內容：優先取命令列參數，否則用預設問候語
MESSAGE = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello, how can you help me?"


def main() -> int:
    cfg = Config(read_timeout=60, connect_timeout=15, retries={"max_attempts": 1})
    client = boto3.client("bedrock-agentcore", region_name=REGION, config=cfg)

    try:
        response = client.invoke_harness(
            harnessArn=HARNESS_ARN,
            runtimeSessionId=SESSION_ID,
            messages=[
                {"role": "user", "content": [{"text": MESSAGE}]},
            ],
        )

        # 串流印出回覆文字
        for event in response["stream"]:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    print(delta["text"], end="", flush=True)
        print()
        return 0
    except Exception as e:
        # 串流中的錯誤事件（例如憑證過期、模型存取權限問題）會在此被清楚印出，
        # 而不是靜默卡住
        print(f"\n[錯誤] {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
