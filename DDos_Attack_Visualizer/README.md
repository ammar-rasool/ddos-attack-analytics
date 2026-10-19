# DDoS Attack Visualizer

A synthetic cyberattack flow generation and visualization pipeline built using the Cloudflare Radar API.

This project generates realistic Layer 3 and Layer 7 DDoS attack flow simulations for globe-based visualizations using probabilistic modeling and concurrent API aggregation.

**Designed for:**
- Real-time cyberattack visualization
- Dashboard systems
- `globe.gl` integrations
- Educational cyber analytics
- Synthetic traffic simulations

**Not intended for:**
- Forensic attribution
- Geopolitical intelligence
- Scientific causal inference
- Packet-level security analysis

## Features

- **15-minute attack intensity modeling**
- **Layer 3 and Layer 7 attack support**
- **Concurrent API fetching** using thread pools
- **Retry/backoff networking architecture**
- **Session-persistent HTTP connections**
- **In-memory TTL caching**
- **Seeded stochastic reproducibility**
- **Structured metadata + pandas DataFrame output**
- **Synthetic origin-to-target flow generation**
- **Visualization-ready pipeline for `globe.gl`**

## Architecture

```text
+----------------------------+
| Cloudflare Radar API       |
+----------------------------+
             ↓
+----------------------------+
| Fetch Timeseries (15m)     |
+----------------------------+
             ↓
+----------------------------+
| Origin–Target Distributions|
+----------------------------+
             ↓
+----------------------------+
| Probability Normalization  |
+----------------------------+
             ↓
+----------------------------+
| Poisson Attack Sampling    |
+----------------------------+
             ↓
+----------------------------+
| Flow Allocation (Multinomial)|
+----------------------------+
             ↓
+----------------------------+
| Synthetic Dataset          |
+----------------------------+
             ↓
+----------------------------+
| Globe.gl Visualization     |
+----------------------------+
```


### Phase 1: API Aggregation

The system concurrently queries Cloudflare Radar API endpoints using:
- `ThreadPoolExecutor`
- Persistent `requests.Session`
- Retry-enabled `HTTPAdapter`
- TTL-based in-memory caching

This minimizes blocking network I/O and significantly reduces repeated dashboard query latency.

#### Retrieved Data

| Source | Interval |
|--------|----------|
| Attack intensity timeseries | 15 minutes |
| Origin-target attack distributions | 1 hour |

### Phase 2: Synthetic Flow Generation

The visualization engine constructs synthetic attack flows using:
- **Poisson sampling** for attack intensity generation
- **Multinomial allocation** for origin-target distribution mapping
- **Seeded NumPy random generators** for reproducibility

Generated flows are returned as structured `pandas.DataFrame` objects.

## Statistical Assumption

This project uses the following approximation:

$$ P(origin, target \mid 15m) pprox P(origin, target \mid 1h) $$

### Why this assumption exists

Cloudflare Radar exposes:
- High-resolution 15-minute attack intensity data.
- Hourly origin-to-target attack distributions.

To generate continuous visual flows, hourly distributions are probabilistically projected onto 15-minute intervals. This allows smooth temporal visualization while preserving aggregate regional attack behavior.

### Important Limitation

The generated flows are **synthetic probabilistic approximations**, not direct observational traffic records. 

This means flows are:
- Visualization-grade
- Not attribution-grade
- Not packet-level truth
- Not suitable for scientific geopolitical inference

The system models likely distributions, not exact real-world routing events.

## Example Output

```json
{
    "metadata": {
        "layer": "layer3",
        "source_interval": "15m",
        "distribution_interval": "1h",
        "normalization": "MIN0_MAX",
        "data_type": "synthetic_visualization",
        "seed": 42
    },
    "flows": pandas.DataFrame(...)
}
```

## Performance Design

### Networking Optimizations
- Connection pooling via `requests.Session`
- Automatic retries for `429`, `500`, `502`, `503`, and `504` errors
- Configurable worker pools
- TTL response caching

### Computational Optimizations
- Vectorized NumPy operations
- Batched DataFrame construction
- Minimized Python object overhead
- Seeded RNG reuse

## Technology Stack

- Python
- NumPy
- Pandas
- Requests
- Concurrent Futures
- Cloudflare Radar API
- globe.gl

## Installation

```bash
git clone <your-repo-url>
cd ddos-attack-visualizer
pip install -r requirements.txt
```

## Usage

Run the generator:

```bash
python main.py
```

Example integration targets:
- `globe.gl`
- Plotly dashboards
- Real-time cyber maps
- Streaming visual analytics systems

## Repository Structure

```text
.
├── main.py
├── api_clients.py
├── config.py
├── requirements.txt
└── README.md
```

## Future Improvements

- Async HTTP pipeline using `aiohttp`
- WebSocket streaming support
- Redis/distributed caching
- Historical dataset archival
- Uncertainty quantification
- Probabilistic confidence intervals
- Attack-type categorization
- ASN-level visualization

## Disclaimer

This repository is intended for visualization, simulation, and educational analytics purposes. 

It should **not** be interpreted as:
- Exact traffic telemetry
- Forensic evidence
- Geopolitical attribution
- Scientific ground-truth measurement
