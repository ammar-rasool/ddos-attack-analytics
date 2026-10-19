from api_clients import data
import pprint
from datetime import datetime, timedelta
import numpy as np
import concurrent.futures
import os
import json
import threading

# Lock to avoid race conditions when writing cache
_cache_lock = threading.Lock()

LAYER_CONFIG = {
    "layer3" : {
        "time_series_data_url" : "https://api.cloudflare.com/client/v4/radar/attacks/layer3/timeseries",
        "time_series_data_params" : {
                "aggInterval": "1d",         # Use 15-minute buckets
                "dateRange": "30d",
                "metric": "bytes",  # Specify the metric to analyze
                "normalization": "MIN0_MAX",   # Specify the metric
                "direction": "ORIGIN"  # Specify the direction of traffic (in or out)
            },
        "origin_location_url" : "https://api.cloudflare.com/client/v4/radar/attacks/layer3/top/locations/origin",
        "target_location_url" : "https://api.cloudflare.com/client/v4/radar/attacks/layer3/top/locations/target"
    },
    "layer7" : {
        "time_series_data_url" : "https://api.cloudflare.com/client/v4/radar/attacks/layer7/timeseries",
        "time_series_data_params" : {
                "aggInterval": "1d",         # Use 15-minute buckets
                "dateRange": "30d",
                "normalization": "MIN0_MAX",   # Specify the metric
            },
        "origin_location_url" : "https://api.cloudflare.com/client/v4/radar/attacks/layer7/top/locations/origin",
        "target_location_url" : "https://api.cloudflare.com/client/v4/radar/attacks/layer7/top/locations/target"
    }
}

def get_cached_or_fetch(url, params, cache_dir, filename):
    os.makedirs(cache_dir, exist_ok=True)
    filepath = os.path.join(cache_dir, filename)
    
    with _cache_lock:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    
    response_data = data(params, url)
    
    with _cache_lock:
        with open(filepath, 'w') as f:
            json.dump(response_data, f)
            
    return response_data

def build_probability_distribution(data_list, name_key, rng=None, apply_uncertainty=False):
    probs = {
        item[name_key]: float(item['value']) / 100
        for item in data_list
    }
    
    if not probs:
        return [], []

    total = sum(probs.values())
    if total == 0:
        return list(probs.keys()), [0] * len(probs)
        
    normalized = [value / total for value in probs.values()]

    if apply_uncertainty and rng is not None:
        # Scale to form Dirichlet alpha parameters (adding small epsilon to prevent 0)
        alphas = [max(p * 100, 0.1) for p in normalized]
        sampled = rng.dirichlet(alphas)
        normalized = sampled.tolist()

    return list(probs.keys()), normalized

def generate_historic_flows(layer="layer3", country_count=10, attack_scale=120, seed=42, add_uncertainty=False):
    rng = np.random.default_rng(seed=seed)
    config = LAYER_CONFIG[layer]
    
    # Optional caching for time-series is not as important, but possible
    response = data(
        config["time_series_data_params"],
        config["time_series_data_url"]
    )

    time_series_data = list(
        map(float, response['result']['serie_0']['values'])
    )

    time_stamps = response['result']['serie_0']['timestamps']

    lambda_rates = [
        int(attack_scale * value)
        for value in time_series_data
    ]

    attack_counts = [
        rng.poisson(lam)
        for lam in lambda_rates
    ]

    def process_bucket(bucket_idx, attacks):
        local_flows = []
        try:
            # Seed local to this thread + bucket to avoid thread sharing and ensure true reproducibility
            local_rng = np.random.default_rng(seed + bucket_idx)
            
            bucket_start = datetime.fromisoformat(
                time_stamps[bucket_idx].replace("Z", "+00:00")
            )
            
            # Assuming timestamps mark bucket start
            bucket_end = bucket_start + timedelta(days=1)
            date_str = bucket_start.strftime("%Y-%m-%d")

            origin_params = {
                "dateStart": bucket_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "dateEnd": bucket_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": country_count
            }

            target_params = {
                "dateStart": bucket_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "dateEnd": bucket_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": country_count
            }

            cache_dir = f"cache/{layer}"
            
            origin_response = get_cached_or_fetch(
                config["origin_location_url"], 
                origin_params, 
                cache_dir, 
                f"{date_str}_origin.json"
            )
            origin_data = origin_response['result']['top_0']

            target_response = get_cached_or_fetch(
                config["target_location_url"], 
                target_params, 
                cache_dir, 
                f"{date_str}_target.json"
            )
            target_data = target_response['result']['top_0']

            origin_countries, origin_probabilities = build_probability_distribution(
                origin_data, "originCountryName", rng=local_rng, apply_uncertainty=add_uncertainty
            )

            target_countries, target_probabilities = build_probability_distribution(
                target_data, "targetCountryName", rng=local_rng, apply_uncertainty=add_uncertainty
            )

            if not origin_countries or not target_countries:
                return local_flows

            origin_counts = local_rng.multinomial(
                attacks,
                origin_probabilities
            )

            for i, origin_attack_count in enumerate(origin_counts):
                if origin_attack_count == 0:
                    continue

                target_counts = local_rng.multinomial(
                    origin_attack_count,
                    target_probabilities
                )

                for j, target_attack_count in enumerate(target_counts):
                    if target_attack_count > 0:
                        local_flows.append({
                            "timestamp": time_stamps[bucket_idx],
                            "origin": origin_countries[i],
                            "target": target_countries[j],
                            "attacks": int(target_attack_count),
                            "layer": layer
                        })
            return local_flows
        except Exception as e:
            print(f"Error processing bucket {bucket_idx}: {e}")
            return []

    flows = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks to the executor
        futures = [
            executor.submit(process_bucket, bucket_idx, attacks)
            for bucket_idx, attacks in enumerate(attack_counts)
        ]
        
        # Collect the results as they complete
        for future in concurrent.futures.as_completed(futures):
            flows.extend(future.result())

    # Optional: Sort array by timestamp since threads finish out of order
    flows = sorted(flows, key=lambda x: x["timestamp"])

    return flows


# origin_data = data({
#         "dateRange": "7d", 
#         "limit" : 5
#     }, "https://api.cloudflare.com/client/v4/radar/attacks/layer3/top/locations/origin")
# pprint.pprint(origin_data)