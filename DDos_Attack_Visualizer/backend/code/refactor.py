import os

code = """from api_clients import data
from datetime import datetime, timedelta, timezone
import numpy as np
import concurrent.futures

# Global dates to avoid recomputation
def _get_date_end() -> str:
    target = datetime.now(timezone.utc)
    target = target.replace(hour=0, minute=0, second=0, microsecond=0)
    return target.strftime('%Y-%m-%dT%H:%M:%SZ')

def _get_date_start() -> str:
    target = datetime.now(timezone.utc) - timedelta(days=1)
    target = target.replace(hour=0, minute=0, second=0, microsecond=0)
    return target.strftime('%Y-%m-%dT%H:%M:%SZ')

GLOBAL_DATE_START = _get_date_start()
GLOBAL_DATE_END = _get_date_end()

def increment_time_hourly(time_str: str) -> str:
    dt = datetime.strptime(
        time_str,
        "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)
    target = dt + timedelta(hours=1)
    return target.strftime('%Y-%m-%dT%H:%M:%SZ')

LAYER_CONFIG = {
    "layer3": {
        "time_series_data_url": "https://api.cloudflare.com/client/v4/radar/attacks/layer3/timeseries",
        "time_series_data_params": {
            "aggInterval": "15m",
            "dateStart": GLOBAL_DATE_START,
            "dateEnd": GLOBAL_DATE_END,
            "metric": "bytes",
            "normalization": "MIN0_MAX",
            "direction": "ORIGIN"
        },
        "origin_target_pair_url": "https://api.cloudflare.com/client/v4/radar/attacks/layer3/top/attacks"
    },
    "layer7": {
        "time_series_data_url": "https://api.cloudflare.com/client/v4/radar/attacks/layer7/timeseries",
        "time_series_data_params": {
            "aggInterval": "15m",
            "dateStart": GLOBAL_DATE_START,
            "dateEnd": GLOBAL_DATE_END,
            "normalization": "MIN0_MAX"
        },
        "origin_target_pair_url": "https://api.cloudflare.com/client/v4/radar/attacks/layer7/top/attacks"
    }
}

def fetch_timeseries(config):
    \"\"\"Fetch the timeseries data for the past 24 hours.\"\"\"
    response = data(config["time_series_data_params"], config["time_series_data_url"])
    time_series_data = response['result']['serie_0']['values']
    
    start_dt = datetime.strptime(GLOBAL_DATE_START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    time_stamps = [(start_dt + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
                   for i in range(len(time_series_data))]
                   
    return [float(v) for v in time_series_data], time_stamps

def fetch_hourly_pair_distribution(current_hour_start, config, max_limit=200):
    \"\"\"Fetch a single hour's distribution.\"\"\"
    current_hour_end = increment_time_hourly(current_hour_start)
    origin_target_pair_params = {
        "limit": max_limit,
        "dateStart": current_hour_start,
        "dateEnd": current_hour_end
    }
    
    response = data(origin_target_pair_params, config["origin_target_pair_url"])
    origin_target_data = response['result']['top_0']
    
    if not origin_target_data:
        return current_hour_start, [], np.array([])
        
    origin_target_probs = np.array([float(pair['value']) / 100 for pair in origin_target_data])
    
    # Normalize probabilities
    origin_target_probs = origin_target_probs / origin_target_probs.sum()
    
    # Validation checks
    assert np.isclose(origin_target_probs.sum(), 1.0), "Probabilities must sum to 1.0"
    assert len(origin_target_probs) == len(origin_target_data), "Mismatched lengths"
    
    return current_hour_start, origin_target_data, origin_target_probs

def build_hourly_cache(config, max_limit=200):
    \"\"\"Pre-fetch all 24 hourly distributions concurrently.\"\"\"
    hours = []
    current_time = GLOBAL_DATE_START
    while current_time < GLOBAL_DATE_END:
        hours.append(current_time)
        current_time = increment_time_hourly(current_time)
        
    cache = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_hourly_pair_distribution, hr, config, max_limit): hr for hr in hours}
        for future in concurrent.futures.as_completed(futures):
            hr, pairs, probs = future.result()
            cache[hr] = {
                "pairs": pairs,
                "probs": probs
            }
            
    return cache

def generate_attack_counts(time_series_data, max_attack_count, rng):
    \"\"\"Generate attack counts based on timeseries data using seeded RNG.\"\"\"
    lambda_rates = [int(max_attack_count * value) for value in time_series_data]
    return [rng.poisson(lam) for lam in lambda_rates]

def generate_recent_flows(layer: str = "layer3", max_attack_count: int = 1000, seed: int = 42) -> list:
    \"\"\"
    Generate flows for visualization and caching.
    Note: The statistical assumption P(origin,target|15m) approx P(origin,target|1h) 
    is used here. This is acceptable for visualization and dashboards 
    but may not be fully defensible for scientific inference or geopolitical attribution.
    \"\"\"
    # Seeded RNG for reproducibility
    rng = np.random.default_rng(seed)
    
    config = LAYER_CONFIG[layer]
    
    # Phase 1: Pre-fetch API data
    time_series_data, time_stamps = fetch_timeseries(config)
    hourly_pair_cache = build_hourly_cache(config)
    
    # Phase 2: Generate locally
    attack_counts = generate_attack_counts(time_series_data, max_attack_count, rng)
    
    flows = []
    current_hour_start = GLOBAL_DATE_START
    
    for bucket_idx in range(len(time_stamps)):
        if bucket_idx > 0 and bucket_idx % 4 == 0:
            current_hour_start = increment_time_hourly(current_hour_start)
            
        hour_data = hourly_pair_cache.get(current_hour_start)
        if not hour_data or len(hour_data["pairs"]) == 0:
            continue
            
        origin_target_data = hour_data["pairs"]
        origin_target_probs = hour_data["probs"]
        
        origin_target_pair_counts = rng.multinomial(
            attack_counts[bucket_idx],
            origin_target_probs
        )
        
        for pair_idx, count in enumerate(origin_target_pair_counts):
            if count == 0:
                continue
                
            pair_data = origin_target_data[pair_idx]
            
            flows.append({
                "timestamp": time_stamps[bucket_idx],
                "origin": pair_data['originCountryName'],
                "target": pair_data['targetCountryName'],
                "attacks": int(count),
                "layer": layer,
                "source_interval": "15m",
                "distribution_interval": "1h",
                "normalization": "MIN0_MAX",
                "generated": True
            })
            
    return flows
"""

with open(r'd:\Ammar Data\Projects\DDos_Attack_Visualizer\ddos_recent_data.py', 'r', encoding='utf-8') as f:
    content = f.read()

split_idx = content.find('from api_clients import data')
if split_idx != -1:
    new_content = content[:split_idx] + code
    with open(r'd:\Ammar Data\Projects\DDos_Attack_Visualizer\ddos_recent_data.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Refactor successful.')
else:
    print('Could not find split point in ddos_recent_data.py')
