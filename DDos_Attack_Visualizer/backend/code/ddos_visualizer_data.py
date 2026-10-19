import api_clients
from config import MAX_WORKERS, MAX_LIMIT, DEFAULT_SEED, DEFAULT_ATTACK_COUNT
from country_coords import get_coords
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import concurrent.futures
import os
import logging
from typing import Dict, List, Tuple, Any, TypedDict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FlowMetadata(TypedDict):
    layer: str
    source_interval: str
    distribution_interval: str
    normalization: str
    data_type: str
    seed: int

class GeneratedFlows(TypedDict):
    metadata: FlowMetadata
    flows: pd.DataFrame

def get_date_range() -> Tuple[datetime, datetime]:
    end = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = end - timedelta(days=1)
    return start, end

def increment_time_hourly(time_dt: datetime) -> datetime:
    return time_dt + timedelta(hours=1)

def get_layer_config(layer: str, date_start: str, date_end: str) -> Dict[str, Any]:
    configs = {
        "layer3": {
            "time_series_data_url": "https://api.cloudflare.com/client/v4/radar/attacks/layer3/timeseries",
            "time_series_data_params": {
                "aggInterval": "15m",
                "dateStart": date_start,
                "dateEnd": date_end,
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
                "dateStart": date_start,
                "dateEnd": date_end,
                "normalization": "MIN0_MAX"
            },
            "origin_target_pair_url": "https://api.cloudflare.com/client/v4/radar/attacks/layer7/top/attacks"
        }
    }
    return configs.get(layer, configs["layer3"])

def fetch_timeseries(config: Dict[str, Any], start_dt: datetime) -> Tuple[List[float], List[str]]:
    """Fetch the timeseries data for the past 24 hours."""
    try:
        response = api_clients.fetch_cloudflare_data(config["time_series_data_params"], config["time_series_data_url"])
        if 'result' not in response or 'serie_0' not in response['result']:
            raise ValueError("Malformed API response: Missing 'result' or 'serie_0'")
        time_series_data = response['result']['serie_0']['values']
        api_timestamps = response['result']['serie_0'].get('timestamps', [])
        
        # Verify API timestamps match data length, else fallback to manual
        if api_timestamps and len(api_timestamps) == len(time_series_data):
            time_stamps = api_timestamps
        else:
            logger.warning("API timestamps missing or mismatched with data length. Falling back to manual.")
            time_stamps = [(start_dt + timedelta(minutes=15 * i)).isoformat().replace("+00:00", "Z") for i in range(len(time_series_data))]
                           
        return [float(v) for v in time_series_data], time_stamps
    except Exception as e:
        logger.error(f"Failed to fetch time series: {e}")
        return [], []

def fetch_hourly_pair_distribution(current_hour_start: datetime, config: Dict[str, Any], max_limit: int = MAX_LIMIT) -> Tuple[datetime, List[Dict[str, Any]], np.ndarray]:
    """Fetch a single hour's distribution."""
    try:
        current_hour_end = increment_time_hourly(current_hour_start)
        origin_target_pair_params = {
            "limit": max_limit,
            "dateStart": current_hour_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "dateEnd": current_hour_end.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        response = api_clients.fetch_cloudflare_data(origin_target_pair_params, config["origin_target_pair_url"])
        if 'result' not in response or 'top_0' not in response['result']:
            raise ValueError("Malformed API response: Missing 'result' or 'top_0'")
        origin_target_data = response['result']['top_0']
        
        if not origin_target_data:
            return current_hour_start, [], np.array([])
            
        origin_target_probs = np.array([float(pair['value']) / 100 for pair in origin_target_data])
        
        prob_sum = origin_target_probs.sum()
        if prob_sum == 0 or np.isnan(prob_sum):
            logger.warning(f"Zero or NaN probability sum for {current_hour_start}")
            return current_hour_start, [], np.array([])
            
        # Normalize probabilities
        origin_target_probs = origin_target_probs / prob_sum
        
        # Validation checks
        if not np.isclose(origin_target_probs.sum(), 1.0):
            raise ValueError("Probabilities must sum to 1.0")
        if len(origin_target_probs) != len(origin_target_data):
            raise ValueError("Mismatched lengths")
        
        return current_hour_start, origin_target_data, origin_target_probs
    except Exception as e:
        logger.error(f"Failed to fetch hourly distribution for {current_hour_start}: {e}")
        return current_hour_start, [], np.array([])

def build_hourly_cache(config: Dict[str, Any], start_dt: datetime, end_dt: datetime, max_limit: int = MAX_LIMIT) -> Dict[datetime, Dict[str, Any]]:
    """Pre-fetch all 24 hourly distributions concurrently."""
    hours = []
    current_time = start_dt
    
    while current_time < end_dt:
        hours.append(current_time)
        current_time = increment_time_hourly(current_time)
        
    cache: Dict[datetime, Dict[str, Any]] = {}
    max_workers = min(len(hours), MAX_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_hourly_pair_distribution, hr, config, max_limit): hr for hr in hours}
        for future in concurrent.futures.as_completed(futures):
            try:
                hr, pairs, probs = future.result()
                cache[hr] = {
                    "pairs": pairs,
                    "probs": probs
                }
            except Exception as e:
                logger.error(f"Future result evaluation failed: {e}")
            
    return cache

def generate_attack_counts(time_series_data: List[float], max_attack_count: int, rng: np.random.Generator) -> List[int]:
    """Generate attack counts based on timeseries data using seeded RNG."""
    lambda_rates = [int(max_attack_count * value) for value in time_series_data]
    return [rng.poisson(lam) for lam in lambda_rates]

def generate_recent_flows(layer: str = "layer3", max_attack_count: int = DEFAULT_ATTACK_COUNT, seed: int = DEFAULT_SEED) -> GeneratedFlows:
    """
    Generate flows for visualization and caching.
    Note: The statistical assumption P(origin,target|15m) approx P(origin,target|1h) 
    is used here. This is acceptable for visualization and dashboards 
    but may not be fully defensible for scientific inference or geopolitical attribution.
    """
    # Seeded RNG for reproducibility
    rng = np.random.default_rng(seed)
    
    # Determine dynamic date range for this generation run
    start_dt, end_dt = get_date_range()
    date_start_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    date_end_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    config = get_layer_config(layer, date_start_str, date_end_str)
    
    # Phase 1: Pre-fetch API data
    time_series_data, time_stamps = fetch_timeseries(config, start_dt)
    if not time_series_data:
        logger.error("Empty time series data returned. Exiting.")
        return {"metadata": {"layer": layer, "source_interval": "15m", "distribution_interval": "1h", "normalization": "MIN0_MAX", "data_type": "synthetic_visualization", "seed": seed}, "flows": pd.DataFrame()}
        
    hourly_pair_cache = build_hourly_cache(config, start_dt, end_dt)
    
    # Phase 2: Generate locally
    attack_counts = generate_attack_counts(time_series_data, max_attack_count, rng)
    
    timestamp_list = []
    origin_list = []
    origin_lat_list = []
    origin_lng_list = []
    target_list = []
    target_lat_list = []
    target_lng_list = []
    attacks_list = []
    prob_list = []

    current_hour_start = start_dt
    
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
            origin_name = pair_data['originCountryName']
            target_name = pair_data['targetCountryName']
            o_lat, o_lng = get_coords(origin_name)
            t_lat, t_lng = get_coords(target_name)

            timestamp_list.append(time_stamps[bucket_idx])
            origin_list.append(origin_name)
            origin_lat_list.append(o_lat)
            origin_lng_list.append(o_lng)
            target_list.append(target_name)
            target_lat_list.append(t_lat)
            target_lng_list.append(t_lng)
            attacks_list.append(int(count))
            prob_list.append(float(origin_target_probs[pair_idx]))
            
    flows_df = pd.DataFrame({
        "timestamp": timestamp_list,
        "origin": origin_list,
        "origin_lat": origin_lat_list,
        "origin_lng": origin_lng_list,
        "target": target_list,
        "target_lat": target_lat_list,
        "target_lng": target_lng_list,
        "attack_intensity": attacks_list,
        "hourly_probability": prob_list
    })
            
    # Output structure separates metadata from observational data
    return {
        "metadata": {
            "layer": layer,
            "source_interval": "15m",
            "distribution_interval": "1h",
            "normalization": "MIN0_MAX",
            "data_type": "synthetic_visualization",
            "seed": seed
        },
        "flows": flows_df
    }
