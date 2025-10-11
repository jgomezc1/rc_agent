# Phase-1 RS Selector for StructuBIM

A Python tool for selecting optimal reinforcement solutions from `shop_drawings.json` based on various objectives and constraints.

## Quick Start

```bash
# Find top 5 minimum cost solutions
python src/rs_cli.py --objective min_cost --top-k 5

# Find fastest solutions with mechanical couplers only
python src/rs_cli.py --objective fastest --join EM --top-k 3

# Find low-carbon solutions under $150k steel cost
python src/rs_cli.py --objective low_carbon --kpi "steel_cost<=150000"
```

## Installation

```bash
pip install tabulate
```

## Running Tests

```bash
python src/test_rs_selector.py
```
