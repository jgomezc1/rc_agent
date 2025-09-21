import json
from agent_tools import filter_rs, top_n_rs
from action import print_report_tool

# 1) Apply numeric filters
flt = filter_rs.invoke('{"where": "Manhours < 580 and Cost_total < 450000 and CO2 < 500"}')
print("Filtered (preview):", flt[:120], "...")

# 2) Pick the 3 cheapest among those
top = top_n_rs.invoke('{"metric":"Cost_total","n":3}')
print("Top‑3:", top)

# 3) Pretty‑print the best candidate
best = json.loads(top)[0]
print(print_report_tool(json.dumps(best)))
