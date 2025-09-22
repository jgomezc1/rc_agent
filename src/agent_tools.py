import json
import pandas as pd
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool
from typing import Optional

# Simulated data loading
def _df_rs():
    import os
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(script_dir, "data", "simulated_rs_data.json")
    with open(data_path, "r") as f:
        return pd.DataFrame(json.load(f))

# ---- Tool Input Schemas ----

class ListRsInput(BaseModel):
    """Input for list_rs tool - no parameters needed"""
    pass

class FilterRsInput(BaseModel):
    """Input for filter_rs tool"""
    where: str = Field(description="Filter condition like 'Manhours < 580' or 'Cost_total < 450000'")

class TopNRsInput(BaseModel):
    """Input for top_n_rs tool"""
    metric: str = Field(description="Metric to sort by (e.g., 'Cost_total', 'Manhours', 'CO2')")
    n: int = Field(default=3, description="Number of top results to return")

class PrintReportInput(BaseModel):
    """Input for print_report tool"""
    rs_json: str = Field(description="JSON string of RS data to generate report for")

# ---- Tool Functions ----

def _list_rs() -> str:
    """Lists all Reinforcement Solution (RS) IDs."""
    return json.dumps(_df_rs()["RS_ID"].tolist())

def _filter_rs(where: str) -> str:
    """Filters RS data using a condition string."""
    df = _df_rs()
    return df.query(where).to_json(orient="records")

def _top_n_rs(metric: str, n: int = 3) -> str:
    """Ranks top N RSs by a given metric."""
    df = _df_rs().sort_values(by=metric).head(n)
    return df.to_json(orient="records")

def _print_report(rs_json: str) -> str:
    """Generates a readable summary report for a single RS JSON object."""
    best = json.loads(rs_json)
    return (
        f"RS:            {best['RS_ID']}\n"
        f"Steel tonnage:  {best['Steel_tonnage']:.1f} t\n"
        f"Man-hours:      {best['Manhours']}\n"
        f"Material cost:  ${best['Cost_total']:,}\n"
        f"Duration:       {best['Duration_days']} days\n"
        f"CO2 trapped:    {best['CO2']} t\n"
        f"Constructibility index: {best['CI']:.2f}\n"
        f"Bar geometries: {best['Bar_geometries']}"
    )

# ---- Structured Tools ----

list_rs = StructuredTool.from_function(
    func=_list_rs,
    name="list_rs",
    description="Lists all Reinforcement Solution (RS) IDs",
    args_schema=ListRsInput
)

filter_rs = StructuredTool.from_function(
    func=_filter_rs,
    name="filter_rs",
    description="Filters RS data using a condition string on columns like Manhours, Cost_total, CO2, etc.",
    args_schema=FilterRsInput
)

top_n_rs = StructuredTool.from_function(
    func=_top_n_rs,
    name="top_n_rs",
    description="Ranks top N RSs by a given metric like Cost_total, Manhours, CO2",
    args_schema=TopNRsInput
)

print_report_tool = StructuredTool.from_function(
    func=_print_report,
    name="print_report_tool",
    description="Generates a readable summary report for a single RS JSON object",
    args_schema=PrintReportInput
)
