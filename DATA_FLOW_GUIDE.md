# RC Agent Data Flow Guide

## Overview
The RC Agent system operates with a **two-phase data flow** that corresponds to different stages of the construction decision-making process.

## Data Directory Structure

```
project_root/
├── data/                              # Main data directory
│   ├── shop_drawings.json             # Phase A data (solution selection)
│   ├── shop_drawings_structuBIM.json  # Phase B data (execution planning)
│   └── [other optional files]
├── src/                              # Source code
└── [other project files]
```

## Phase 1 (Solution Selection) - Phase A Data

### File: `data/shop_drawings.json`
**Purpose**: Contains high-level solution summaries for optimization and selection

### Data Structure:
```json
{
  "RS_ID_1": {
    "steel_tonnage": 98.5,
    "concrete_volume": 3850,
    "steel_cost": 147750,
    "concrete_cost": 308000,
    "manhours": 600,
    "duration_days": 68,
    "co2_tonnes": 534,
    "constructibility_index": 2.7,
    "bar_geometries": 240
  },
  "RS_ID_2": {
    // ... similar structure
  }
}
```

### Key Fields:
- **steel_tonnage**: Total steel weight in tonnes
- **concrete_volume**: Total concrete volume in m³
- **steel_cost**: Steel material cost
- **concrete_cost**: Concrete material cost
- **manhours**: Estimated labor hours
- **duration_days**: Construction duration
- **co2_tonnes**: Carbon footprint
- **constructibility_index**: Complexity rating (lower = easier)
- **bar_geometries**: Number of unique bar shapes

### Used By:
- Solution selection and ranking
- Multi-objective optimization
- Pareto frontier analysis
- Cost-benefit analysis
- Constraint validation

## Phase 2 (Execution Planning) - Phase B Data

### File: `data/shop_drawings_structuBIM.json`
**Purpose**: Contains detailed BIM element data for construction planning

### Data Structure:
```json
{
  "RS_ID_1": {
    "bar_types": 59,
    "by_element": {
      "Level_Name": {
        "Element_ID": {
          "bar_types": 3,
          "bars_by_diameter": {
            "3/4\"": {"n": 8, "w": 120.69},
            "5/8\"": {"n": 8, "w": 24.832}
          },
          "stirrups_by_diameter": {
            "3/8\"": {"n": 110, "w": 83.677}
          },
          "complexity_score": 1.94,
          "complexity_modifier": 1.0,
          "labor_hours_modifier": -0.024,
          "surface_area": 8.388,
          "vol_concreto": 2.097,
          "total_rebar_weight": 229.199
        }
      }
    }
  }
}
```

### Key Structure:
- **Top Level**: Reinforcement Solution IDs
- **by_element**: Organized by construction levels/floors
- **Element Details**: Individual structural elements (beams, columns, etc.)

### Element-Level Data:
- **Bar specifications**: Detailed rebar information by diameter
- **Complexity metrics**: Scoring and modifiers
- **Geometric properties**: Areas, volumes, weights
- **Labor modifiers**: Complexity-adjusted labor factors

### Used By:
- Risk assessment and bottleneck identification
- Crew planning and resource allocation
- Procurement optimization
- Quality control validation
- Constructibility analysis

## Data Access Patterns

### 1. Automatic File Detection
The system automatically detects the correct data directory:
```python
# DataRouter finds project_root/data/ automatically
data_router = DataRouter()  # Uses default "data" directory
```

### 2. Phase A Data Loading
```python
# Loads all scenarios from shop_drawings.json
phase_a_data = data_router.load_phase_a_data()
# Returns: Dict[rs_id, ScenarioSummary]
```

### 3. Phase B Data Loading
```python
# Loads specific solution from shop_drawings_structuBIM.json
phase_b_data = data_router.load_phase_b_data("RS_ID_001")
# Returns: Dict with BIM element structure
```

### 4. Intelligent Routing
```python
# System automatically determines data type
data_type = data_router.detect_data_type(input_data)
# Returns: "phase_a", "phase_b", or "unknown"
```

## File Naming Requirements

### ✅ Required File Names:
- **Phase A**: `shop_drawings.json` (exact name required)
- **Phase B**: `shop_drawings_structuBIM.json` (exact name required)

### ✅ Required Directory:
- **Data Directory**: `data/` (relative to project root)

### ❌ **Important**:
- File names are **case-sensitive**
- File names must match exactly
- Files must be in JSON format
- Files must be in the `data/` directory

## Solution ID Format

### Naming Convention:
- Solution IDs should be consistent between Phase A and Phase B files
- Common format: `"AG_EM_5a8_L50"`, `"EM_6a6_L100"`, etc.
- Can include alphanumeric characters and underscores

### Example Matching:
```json
// shop_drawings.json
{
  "AG_EM_5a8_L50": { /* Phase A data */ }
}

// shop_drawings_structuBIM.json
{
  "AG_EM_5a8_L50": { /* Phase B data */ }
}
```

## User Upload Process

### Step 1: Prepare Data Files
1. Ensure you have both Phase A and Phase B data
2. Format data according to the schemas above
3. Use consistent Solution IDs across both files

### Step 2: File Placement
1. Place files in the `data/` directory of the project
2. Name files exactly as specified:
   - `shop_drawings.json`
   - `shop_drawings_structuBIM.json`

### Step 3: Validation
The system will automatically validate:
- File existence and format
- JSON structure validity
- Required field presence
- Data type consistency

## Error Handling

### Common Issues:
1. **File Not Found**: Check file names and directory location
2. **JSON Parse Error**: Validate JSON syntax
3. **Missing Solution ID**: Ensure ID exists in Phase B data
4. **Schema Mismatch**: Verify required fields are present

### Example Error Messages:
```
FileNotFoundError: Phase A data file not found: /path/to/data/shop_drawings.json
ValueError: RS ID AG_EM_5a8_L50 not found in BIM data
```

## Data Flow Summary

```
User Files → DataRouter → Phase Detection → Engine Routing → Analysis
     ↓              ↓              ↓              ↓             ↓
Phase A Data → Solution Selection → Optimization → Ranking → Reports
Phase B Data → Execution Planning → Risk Analysis → Crew Planning → Reports
```

## Best Practices

1. **Consistent Naming**: Use the same Solution IDs in both files
2. **Complete Data**: Ensure all required fields are present
3. **Valid JSON**: Use JSON validators before uploading
4. **Backup Files**: Keep originals before modifying
5. **Test Small**: Start with a subset of solutions for testing

This structure allows the RC Agent to seamlessly transition from high-level solution selection to detailed execution planning using the appropriate data for each phase.