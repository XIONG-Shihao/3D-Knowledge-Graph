import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(os.getenv("ATLAS_ENV_FILE", str(ROOT / ".env")))


@dataclass
class Settings:
    data_dir: Path
    seed_demo: bool = True
    ragflow_url: str = ""
    ragflow_key: str = ""
    embedding_model: str = ""
    legacy_graph_api: bool = False
    timeout: float = 30
    max_upload_bytes: int = 20 * 1024 * 1024

    @property
    def ragflow_configured(self) -> bool:
        return bool(self.ragflow_url and self.ragflow_key)

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("KB_DATA_DIR", str(ROOT / "data"))).resolve(),
            seed_demo=os.getenv("KB_SEED_DEMO", "true").lower() == "true",
            ragflow_url=os.getenv("RAGFLOW_BASE_URL", "").rstrip("/"),
            ragflow_key=os.getenv("RAGFLOW_API_KEY", ""),
            embedding_model=os.getenv("RAGFLOW_EMBEDDING_MODEL", ""),
            legacy_graph_api=os.getenv("RAGFLOW_LEGACY_GRAPH_API", "false").lower() == "true",
            timeout=float(os.getenv("RAGFLOW_TIMEOUT_SECONDS", "30")),
        )
