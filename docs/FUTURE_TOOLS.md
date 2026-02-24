# Future Tools for Grouping Optimizer Agent

Ideas for additional tools to enhance the optimization agent's capabilities.

## Recommended Tools

### 1. compare_scenarios
Compare two or more specific scenarios side-by-side, highlighting differences in steel, duration, and trade-offs.

**Use case:** "Compare k=3 vs k=4 for PISO 5 to PISO 15"

**Inputs:**
- List of scenarios to compare (by rank or k value)
- Metrics to highlight

**Output:**
- Side-by-side comparison table
- Delta values (steel saved, time difference)

---

### 2. sensitivity_analysis
Analyze how results change when varying a parameter (e.g., days_first_in_group from 8-12, or different level ranges).

**Use case:** "How does total steel change if I extend the range to PISO 4?"

**Inputs:**
- Parameter to vary
- Range of values to test

**Output:**
- Table/summary showing metric changes across parameter values

---

### 3. export_results
Export optimization results to Excel/CSV for reporting or further analysis.

**Use case:** "Save these results to a file I can share with the team"

**Inputs:**
- Results to export
- Output file path
- Format (xlsx, csv)

**Output:**
- Formatted file with scenarios, groups, and metrics

---

### 4. calculate_savings
Compare optimized grouping vs. baseline (e.g., no grouping, or all levels as one group) to quantify steel/time savings.

**Use case:** "How much steel do I save with k=4 compared to building each floor individually?"

**Inputs:**
- Optimized scenario
- Baseline type (individual levels, single group, custom)

**Output:**
- Steel savings (tonf and %)
- Duration savings (days and %)

---

### 5. visualize_groupings
Generate a simple text-based or ASCII visualization of the grouping scheme.

**Use case:** "Show me a diagram of the recommended grouping"

**Inputs:**
- Scenario to visualize

**Output:**
- ASCII diagram showing floor groups vertically (bottom to top)

---

### 6. what_if_analysis
Quickly test "what if" scenarios by modifying specific group boundaries manually.

**Use case:** "What if I force PISO 5-8 into one group and optimize the rest?"

**Inputs:**
- Fixed group constraints
- Remaining levels to optimize

**Output:**
- Optimization results respecting the constraints

---

## Implementation Priority

| Priority | Tool | Rationale |
|----------|------|-----------|
| 1 | compare_scenarios | Essential for decision-making between options |
| 2 | calculate_savings | Quantifies value of optimization |
| 3 | export_results | Practical for sharing/documentation |
| 4 | sensitivity_analysis | Useful for understanding parameter impact |
| 5 | what_if_analysis | Flexibility for manual adjustments |
| 6 | visualize_groupings | Nice to have for presentations |

---

## Notes

- Tools should follow the same pattern as existing tools (using `@tool` decorator)
- All tools should handle errors gracefully and return informative messages
- Consider adding these incrementally based on actual usage needs
