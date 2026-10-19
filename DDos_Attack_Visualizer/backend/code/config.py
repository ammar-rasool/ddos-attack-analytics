import os
from dotenv import load_dotenv

# Use a path relative to this script so it works on any machine
env_path = os.path.join(os.path.dirname(__file__), "API_Token.env")
load_dotenv(env_path)

API_Token  = os.getenv("API_token")
if not API_Token:
    raise ValueError("API token not found. Please check your .env file.")
HEADER = {
    "Authorization" : f"Bearer {API_Token}",
    "Content-Type"  : "application/json"
}

MAX_WORKERS = 16
CACHE_TTL = 300
MAX_LIMIT = 200
DEFAULT_SEED = 42
DEFAULT_ATTACK_COUNT = 1000000
