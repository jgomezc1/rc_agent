# Two-Step Workflow Guide: Phase 1 → Phase 2 Transition

## Overview

The RC Agent now supports a **two-step workflow** that mirrors real-world construction project decision-making:

1. **Phase 1: Solution Selection** - Analyze multiple reinforcement solutions and select the optimal one
2. **Phase 2: Execution Planning** - Perform detailed execution planning for the selected solution

This approach is more efficient than uploading all detailed BIM data upfront, as you only need detailed data for the solution you plan to build.

## Workflow Comparison

### Traditional Approach (Still Supported)
```
Upload ALL data → Phase 1 Analysis → Phase 2 Analysis
```
- Requires large unified BIM file with all solutions
- Heavy data upload requirements
- All solutions ready for Phase 2 immediately

### New Two-Step Approach (Recommended)
```
Upload Phase 1 data → Select Solution → Upload specific BIM data → Phase 2 Analysis
```
- Only upload summary data initially
- Select optimal solution using Phase 1 tools
- Upload detailed BIM data only for selected solution
- More efficient and realistic workflow

## Step-by-Step Guide

### Step 1: Initial Setup and Solution Selection

#### 1.1 Upload Phase 1 Data
Place the following file in your `data/` directory:
- **`shop_drawings.json`** - Contains high-level summaries of all solutions

#### 1.2 Start Analysis
```bash
python src/comprehensive_langchain_agent.py
```

#### 1.3 Explore Available Solutions
**Query**: "List available solutions"
- **Tool Used**: `list_available_solutions`
- **Result**: Shows all solutions available for Phase 1 analysis

#### 1.4 Perform Solution Selection
Use Phase 1 tools to find the optimal solution:

**Example Queries**:
- "Select the most cost-effective solution under $450,000"
- "Find solutions with the best constructibility index"
- "Perform Pareto analysis for cost vs duration"
- "Compare top 3 solutions by CO2 emissions"

**Tools Available**:
- `select_solution` - Multi-objective optimization
- `analyze_pareto_frontier` - Trade-off analysis
- `perform_sensitivity_analysis` - Parameter impact analysis
- `what_if_analysis` - Scenario modeling

#### 1.5 Decision Point
After analysis, you'll identify the optimal solution (e.g., "TR_5a8_L10")

### Step 2: Transition to Execution Planning

#### 2.1 Check Phase 2 Data Availability
**Query**: "Check Phase 2 data availability for TR_5a8_L10"
- **Tool Used**: `check_phase2_data_availability`
- **Result**: Shows if detailed BIM data is available for the selected solution

#### 2.2 Get Transition Guidance
**Query**: "Prepare Phase 2 transition for TR_5a8_L10"
- **Tool Used**: `prepare_phase2_transition`
- **Result**: Comprehensive guidance on next steps

#### 2.3 Upload Solution-Specific Data (If Needed)
If Phase 2 data is not available, you'll need to upload:
- **`data/TR_5a8_L10.json`** - Detailed BIM data for the selected solution only

#### 2.4 Perform Execution Planning
Once the specific BIM data is available, use Phase 2 tools:

**Example Queries**:
- "Analyze execution risks for TR_5a8_L10"
- "Generate construction plan for TR_5a8_L10"
- "Optimize procurement for TR_5a8_L10"
- "Validate quality for TR_5a8_L10"
- "Generate comprehensive execution report for TR_5a8_L10"

## File Structure Examples

### Phase 1 Data (`shop_drawings.json`)
```json
{
  "TR_5a8_L10": {
    "steel_tonnage": 92.0,
    "concrete_volume": 3820,
    "steel_cost": 138000,
    "concrete_cost": 305600,
    "manhours": 570,
    "duration_days": 63,
    "co2_tonnes": 510,
    "constructibility_index": 2.3,
    "bar_geometries": 185
  },
  "AG_EM_5a8_L50": {
    // ... other solutions
  }
}
```

### Phase 2 Data (`TR_5a8_L10.json`)
```json
{
  "by_element": {
    "Level_1": {
      "V-001": {
        "bars_by_diameter": {
          "3/4\"": {"n": 12, "w": 180.5},
          "5/8\"": {"n": 8, "w": 45.2}
        },
        "stirrups_by_diameter": {
          "3/8\"": {"n": 120, "w": 89.4}
        },
        "complexity_score": 2.4,
        "labor_hours_modifier": 1.2,
        "surface_area": 12.5,
        "vol_concreto": 3.1,
        "total_rebar_weight": 315.1
      }
    }
  }
}
```

## Supported File Naming Patterns

The system supports multiple file naming approaches:

### Option 1: Solution-Specific Files (Recommended)
- `data/TR_5a8_L10.json` - Individual solution file
- `data/AG_EM_5a8_L50.json` - Another individual solution file

### Option 2: Unified BIM File (Traditional)
- `data/shop_drawings_structuBIM.json` - Contains all solutions

### Option 3: Mixed Approach
- Some solutions in unified file
- Some solutions in individual files
- System checks individual files first, then falls back to unified file

## Data Loading Priority

When you request Phase 2 analysis for solution "TR_5a8_L10":

1. **First**: Look for `data/TR_5a8_L10.json`
2. **Second**: Look for solution in `data/shop_drawings_structuBIM.json`
3. **Error**: Provide clear guidance on what file to upload

## Workflow Management Tools

### `list_available_solutions`
- Shows all solutions in Phase 1 and Phase 2 data
- Indicates which solutions are ready for each phase
- Helps you understand your data landscape

### `check_phase2_data_availability(rs_id)`
- Checks if Phase 2 data exists for a specific solution
- Shows both individual file and unified file status
- Provides clear next steps

### `prepare_phase2_transition(rs_id)`
- Shows summary of selected solution from Phase 1
- Provides Phase 2 readiness status
- Gives specific tool recommendations
- Explains file format requirements if data upload needed

## Example Complete Workflow

```
User: "List available solutions"
Agent: [Lists 15 solutions available for Phase 1 analysis]

User: "Select the most cost-effective solution with good constructibility"
Agent: [Runs optimization, recommends "TR_5a8_L10"]

User: "Prepare Phase 2 transition for TR_5a8_L10"
Agent: [Shows solution summary, indicates need for TR_5a8_L10.json file]

User: [Uploads TR_5a8_L10.json to data/ directory]

User: "Check Phase 2 data availability for TR_5a8_L10"
Agent: [Confirms data is now available, lists Phase 2 tools]

User: "Generate comprehensive execution report for TR_5a8_L10"
Agent: [Runs all Phase 2 engines, provides detailed execution plan]
```

## Benefits of Two-Step Approach

### 1. **Efficiency**
- Only upload detailed data for solutions you plan to build
- Faster Phase 1 analysis with smaller data files
- Reduced storage and transfer requirements

### 2. **Realistic Workflow**
- Mirrors real construction decision-making process
- Select first, then plan execution
- Matches how architects and engineers actually work

### 3. **Flexibility**
- Can still use unified files if preferred
- Mix and match individual and unified approaches
- Easy to add new solutions incrementally

### 4. **Better Organization**
- Clear separation between selection and planning phases
- Individual files are easier to manage and version
- Clearer data lineage and responsibility

## Error Handling and Guidance

The system provides helpful error messages and guidance:

### When Phase 2 Data is Missing
```
Phase B data not found. Tried:
1. Solution-specific file: data/TR_5a8_L10.json
2. Unified BIM file: data/shop_drawings_structuBIM.json
Please upload either 'TR_5a8_L10.json' or 'shop_drawings_structuBIM.json'
```

### When Solution Not Found
```
Solution TR_5a8_L10 not found in Phase 1 data.
Available solutions: AG_EM_5a8_L50, EM_6a6_L100, ...
```

This two-step workflow makes the RC Agent more practical for real-world use while maintaining full backward compatibility with existing data files.