import json
import pandas as pd
from typing import TypedDict
from langchain.tools import tool

# Simulated data loading
def _df_rs():
    with open("data/simulated_rs_data.json", "r") as f:
        return pd.DataFrame(json.load(f))

# ---- Tool Schemas ----

class ListRsInput(TypedDict):
    input: str  # Dummy field to comply with single-input structure

class FilterRsInput(TypedDict):
    where: str

class TopNRsInput(TypedDict):
    metric: str
    n: int

class PrintReportInput(TypedDict):
    rs_json: str

# ---- Tools ----

@tool(args_schema=ListRsInput)
def list_rs(input: str) -> str:
    """
    Lists all Reinforcement Solution (RS) IDs.
    Call this tool using: {"name": "list_rs", "args": {"input": ""}}
    """
    return json.dumps(_df_rs()["RS_ID"].tolist())

@tool(args_schema=FilterRsInput)
def filter_rs(where: str) -> str:
    """
    Filters RS data using a condition string on columns like Manhours, Cost_total, CO2, etc.
    Example input: {"where": "Manhours < 580 and Cost_total < 450000 and CO2 < 500"}
    """
    df = _df_rs()
    return df.query(where).to_json(orient="records")

@tool(args_schema=TopNRsInput)
def top_n_rs(metric: str, n: int = 3) -> str:
    """
    Ranks top N RSs by a given metric.
    Example input: {"metric": "Cost_total", "n": 3}
    """
    df = _df_rs().sort_values(by=metric).head(n)
    return df.to_json(orient="records")

@tool(args_schema=PrintReportInput)
def print_report_tool(rs_json: str) -> str:
    """
    Generates a readable summary report for a single RS JSON object.
    """
    best = json.loads(rs_json)
    return (
        f"🏷  RS:            {best['RS_ID']}\n"
        f"🔩 Steel tonnage:  {best['Steel_tonnage']:.1f} t\n"
        f"👷 Man‑hours:      {best['Manhours']}\n"
        f"💰 Material cost:  ${best['Cost_total']:,}\n"
        f"📆 Duration:       {best['Duration_days']} days\n"
        f"🌱 CO₂ trapped:    {best['CO2']} t\n"
        f"⚙️  Constructibility index: {best['CI']:.2f}\n"
        f"📐 Bar geometries: {best['Bar_geometries']}"
    )
