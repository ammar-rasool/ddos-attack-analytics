import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import HEADER, CACHE_TTL
import time
import json
from threading import Lock

# Configure session with retry logic
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1,  # Added jitter to retry backoff if possible internally by standard libraries but fixed at 1 for scale
    status_forcelist=[429, 500, 502, 503, 504],
)
session.mount('https://', HTTPAdapter(max_retries=retries))

# Simple TTL cache for API requests
_CACHE = {}
_CACHE_LOCK = Lock()


def fetch_cloudflare_data(param:dict, url:str) -> dict:
    # Create a stable cache key from url and params
    cache_key = f"{url}_{json.dumps(param, sort_keys=True)}"
    current_time = time.time()
    
    # Return cached data if valid
    with _CACHE_LOCK:
        if cache_key in _CACHE:
            cached_data, timestamp = _CACHE[cache_key]
            if current_time - timestamp < CACHE_TTL:
                return cached_data
            
    # Fetch, timeout=(connect_timeout, read_timeout)
    response = session.get(url, params=param, headers=HEADER, timeout=(5, 15))
    response.raise_for_status()
    
    result = response.json()
    
    with _CACHE_LOCK:
        _CACHE[cache_key] = (result, current_time)
        
    return result
