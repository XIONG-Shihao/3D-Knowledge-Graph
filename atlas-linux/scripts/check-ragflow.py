"""Read-only RAGFlow connection check; never prints an API key."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Settings  # noqa: E402
from backend.ragflow import RAGFlowClient, RAGFlowError  # noqa: E402

settings = Settings.from_env()
if not settings.ragflow_configured:
    raise SystemExit(
        "请填写 RAGFLOW_BASE_URL 和 RAGFLOW_API_KEY / Configure the RAGFlow URL and API key."
    )
try:
    RAGFlowClient(settings).request("GET", "datasets", params={"page": 1, "page_size": 1})
except RAGFlowError as exc:
    print(f"连接失败 / Connection failed: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc
print(
    "连接成功 / Connected. API authentication and dataset access work. Models and parsing need a document smoke test."
)
