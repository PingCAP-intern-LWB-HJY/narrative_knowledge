import os
import json
from dotenv import load_dotenv

load_dotenv()

# LLM settings
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
LLM_MODEL = os.environ.get("LLM_MODEL", "aya-expanse")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# need 4096 dimension embedding for knowledge graph, fix it later
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "hf.co/Qwen/Qwen3-Embedding-8B-GGUF:Q8_0")
EMBEDDING_BASE_URL = os.environ.get("EMBEDDING_BASE_URL", "http://localhost:11434/v1/")
EMBEDDING_MODEL_API_KEY = os.environ.get("EMBEDDING_MODEL_API_KEY", "ollama")

# DB settings
DATABASE_URI = os.environ.get("DATABASE_URI","mysql+pymysql://2v2WvLxTSjY5adC.root:2rA6B5Zc98PgMqNH@gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com:4000/test?ssl_ca=/etc/ssl/cert.pem&ssl_verify_cert=true&ssl_verify_identity=true")
SESSION_POOL_SIZE: int = int(os.environ.get("SESSION_POOL_SIZE", 40))
MAX_PROMPT_TOKENS = 40960


# Model configurations
def parse_model_configs() -> dict:
    """Parse MODEL_CONFIGS from environment variable"""
    config_str = os.environ.get("MODEL_CONFIGS", "{}")
    try:
        return json.loads(config_str)
    except json.JSONDecodeError:
        print(f"Warning: Invalid MODEL_CONFIGS format: {config_str}")
        return {}


MODEL_CONFIGS = parse_model_configs()
