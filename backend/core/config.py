"""Central configuration. Everything defaults to free / offline-capable."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Read BASE_DIR/.env into the environment. Real env vars always win.

    Deliberately stdlib-only — dataid installs no extra dependency for this.
    """
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()
DATA_DIR = Path(os.getenv("DATAID_DATA_DIR", BASE_DIR / "storage"))
RUNS_DIR = DATA_DIR / "runs"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "dataid.db"

for _d in (DATA_DIR, RUNS_DIR, UPLOADS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- LLM
# "none"     no narrator: metrics, rankings and attribution are still computed and reported,
#            the prose is simply absent rather than pattern-matched from a template.
# "ollama"   free, local (ollama serve + `ollama pull llama3.1`)
# "groq"     free tier, set GROQ_API_KEY
# "openrouter" free-tier models, set OPENROUTER_API_KEY
# "gemini"   free tier, set GEMINI_API_KEY
# "nvidia"   NVIDIA build (integrate.api.nvidia.com), set NVIDIA_API_KEY
# "huggingface" HF Inference Providers router, set HF_TOKEN — one key, many open-weights models
LLM_PROVIDER = os.getenv("DATAID_LLM_PROVIDER", "none")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("DATAID_OLLAMA_MODEL", "llama3.1")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("DATAID_GROQ_MODEL", "llama-3.3-70b-versatile")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("DATAID_OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("DATAID_GEMINI_MODEL", "gemini-2.5-flash")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.getenv("DATAID_NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
# The nemotron-3 family reasons before answering and *requires* thinking to be enabled;
# models without a reasoning config (llama-3.3-70b) return HTTP 500 if these are sent, so
# they are gated per model. "auto" follows NVIDIA_THINKING_MODELS; "on"/"off" force it.
NVIDIA_THINKING = os.getenv("DATAID_NVIDIA_THINKING", "auto").lower()
NVIDIA_THINKING_MODELS = r"nemotron-3"
# Reasoning tokens come out of the same budget as the prose, so thinking models need headroom.
NVIDIA_REASONING_BUDGET = int(os.getenv("DATAID_NVIDIA_REASONING_BUDGET", "8192"))

# Hugging Face Inference Providers: one token routed to whichever partner currently serves
# the model, so the open-weights frontier is reachable without an account per vendor.
HF_TOKEN = os.getenv("HF_TOKEN", "") or os.getenv("HUGGINGFACE_API_KEY", "")
HF_MODEL = os.getenv("DATAID_HF_MODEL", "moonshotai/Kimi-K3")
# Kimi K3 reasons on every call and offers no switch to stop it, so thinking and prose share
# one completion budget. The 2048 floor is not enough: the explainability prompt spends it all
# on reasoning and the narration comes back truncated. Gated per model — a non-thinking model
# served through the same router gets the ordinary floor.
HF_THINKING_MODELS = r"[Kk]imi-[Kk]3|[Tt]hinking|[Rr]easoning"
HF_REASONING_BUDGET = int(os.getenv("DATAID_HF_REASONING_BUDGET", "8192"))

# Gemini 3.x models spend part of the completion budget on hidden reasoning tokens; an 800-token
# cap gets consumed by thinking and the prose comes back truncated (finish_reason="length").
LLM_MIN_MAX_TOKENS = int(os.getenv("DATAID_LLM_MIN_MAX_TOKENS", "2048"))
LLM_RETRIES = int(os.getenv("DATAID_LLM_RETRIES", "2"))

# ---------------------------------------------------------------- modelling
RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 3
MAX_TRAIN_ROWS = 200_000
HIGH_CARDINALITY_THRESHOLD = 40
LEAKAGE_CORRELATION_THRESHOLD = 0.98
LEAKAGE_AUC_THRESHOLD = 0.995
OUTLIER_CONTAMINATION = 0.02
DRIFT_PSI_WARN = 0.1
DRIFT_PSI_ALERT = 0.25

CORS_ORIGINS = os.getenv("DATAID_CORS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
REQUIRE_API_KEY = os.getenv("DATAID_REQUIRE_API_KEY", "false").lower() == "true"
ADMIN_TOKEN = os.getenv("DATAID_ADMIN_TOKEN", "")
