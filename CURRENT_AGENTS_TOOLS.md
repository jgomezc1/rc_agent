# Current Agents and Tools Summary

## Overview
The project currently has **2 active agents** with different purposes and capabilities.

---

## 1. Solution Chat Agent
**File:** `solution_chat_agent.py`
**Status:** ✅ Active (kept as foundation)
**Purpose:** Interactive Q&A about a specific design solution

### Data Sources
- `data/solution.json` - Design solution with elements, floors, bar configurations

### Core Capabilities
- Load and analyze solution.json structure
- Answer questions about design elements
- Provide statistics on bar types, floors, elements
- Interactive chat interface with conversation history
- AI-powered analysis using GPT-4o

### Key Methods
```python
__init__(solution_path, api_key)          # Initialize agent
_load_solution(solution_path)              # Load solution.json
_prepare_data_summary()                    # Create AI context summary
ask(question)                              # Process user question
run_interactive()                          # Start chat loop
```

### Example Usage
```bash
./venv/Scripts/python.exe solution_chat_agent.py
```

```
You: How many floors are in this solution?
Agent: This solution has 24 floors...

You: What bar sizes are used?
Agent: The solution uses the following bar diameters: 1/4", 3/8", 1/2", 5/8", 3/4", 7/8", 1"
```

### Technologies
- OpenAI GPT-4o API
- JSON data processing
- Interactive terminal interface

---

## 2. ProDet+StructuBIM Logistics Agent ⭐ **WITH TOOL SCHEMAS**
**File:** `logistics_agent.py`
**Status:** ✅ Fully operational with OpenAI function calling (production-ready)
**Purpose:** High-leverage logistics intelligence for reinforcement construction
**Tool System:** ✅ Formal tool schemas with OpenAI function calling API

### Data Sources
- `data/despiece.xlsx` (116KB) - Bar-by-bar cutting lists, 5 sheets
  - Resumen_Refuerzo: Floor summaries
  - RefLong_PorElemento: 2,496 longitudinal bar entries
  - RefLong_Total: 77 unique bar configurations
  - RefTrans_PorElemento: 339 stirrup entries
  - RefTrans_Total: 12 unique stirrup configurations

- `data/processedAnalysis.json` (459KB) - Engineering metrics
  - 75 bar types across 24 floors
  - 212 detailed elements with complexity scores
  - Element-level data: longitudinal_bars_total, stirrups_total, complexity_score
  - Labor hours modifiers, weights, bar type breakdowns

### Core Capabilities

#### 1. AI-Powered Analysis
- **Congestion Analysis**: Identify most complex/congested elements
- **Floor-by-Floor Planning**: Analyze specific floor ranges (e.g., Floors 1-5)
- **Complexity Scoring**: Rank elements by difficulty
- **Install Sequencing**: Create micro-sequence plans
- **Resource Optimization**: Minimize handling touches, optimize crane utilization

#### 2. Automatic File Generation (4 Types)
All files auto-generate when user requests them in natural language.

**a) Yard Layout Diagram (PDF - 23KB)**
- 2D overhead view of construction yard (30m × 40m default)
- Crane position and coverage circle (25m radius)
- 5 color-coded zones: STORAGE-A, STORAGE-B, AISLE-1, LOADING, STAGING
- Dimensions, labels, professional quality for printing
- **Triggers**: "yard layout", "site layout", "create layout"

**b) Crane Safety Guidelines (PDF - 2.9KB)**
- Crane specifications (radius, capacity, position)
- Safety zones (exclusion, restricted access)
- 8+ safety procedures
- Emergency protocols
- **Triggers**: "crane safety", "safety guidelines", "crane procedures"

**c) Truck Unloading Schedule (Excel - 6.4KB)**
- 3 sheets: Truck Schedule, Unloading Sequence, Summary
- Time-sequenced operations (08:00, 10:30, 14:00 arrivals)
- Uses actual bundle data from despiece.xlsx
- Weight tracking and duration estimates
- **Triggers**: "unloading schedule", "delivery plan", "truck schedule"

**d) Zone Allocation Map (PDF - 2.7KB)**
- Top N most congested elements (configurable, default 20)
- Floor-filtered allocations (e.g., only Floors 1-5)
- Zone summary with utilization percentages
- Bundle-to-zone assignments
- Uses actual complexity data from processedAnalysis.json
- **Triggers**: "zone allocation", "bundle placement", "storage plan"

#### 3. Detailed Element Data Access
- **Dynamic Data Injection**: Automatically includes detailed element data when user asks for analysis
- **Floor Range Filtering**: Extracts elements from specific floor ranges (e.g., "Floors 1–5" → PISO 2-5)
- **Top N Selection**: Identifies most congested elements based on:
  - `complexity_score`
  - `longitudinal_bars_total`
  - `stirrups_total`
  - `total_rebar_weight`
  - `bar_types`
  - `labor_hours_modifier`

#### 4. Site Configuration
**SiteParameters** dataclass with:
- Yard dimensions (width, depth)
- Crane specs (position, radius, capacity)
- Stacking rules (max height, max weight)
- Crew configuration (size, shifts, working hours)
- Safety buffers
- Gate time windows
- Aisle widths

### Key Methods

#### Data Loading & Processing
```python
__init__(despiece_path, analysis_path, site_params, api_key)
_load_despiece(path)                      # Load all 5 Excel sheets
_load_analysis(path)                      # Load processedAnalysis.json
_prepare_logistics_summary()              # Create AI context
_get_detailed_elements_data(floors)       # Extract element-level data for floors
```

#### File Generation
```python
generate_yard_layout(zones, filename)                    # PDF: Yard layout
generate_unloading_schedule(trucks, bundles, filename)   # Excel: Schedule
generate_zone_allocation(zones, allocations, filename)   # PDF: Zone map
generate_crane_safety(filename)                          # PDF: Safety docs
```

#### Helper Methods
```python
_create_default_zones()                            # 5 default yard zones
_create_sample_unloading_data()                    # Generate trucks/bundles from data
_create_sample_allocations(top_n, floor_range)     # Top N congested elements
```

#### User Interaction
```python
ask(user_prompt)                          # Process question, auto-generate files
run_interactive()                         # Start chat loop
_show_help()                              # Display usage examples
_show_site_params()                       # Display current site config
```

### Intelligent Features

#### 1. Keyword Detection
Automatically detects when user needs:
- Detailed element analysis (triggers data injection)
- File generation (triggers PDF/Excel creation)
- Floor range filtering (parses "Floors 1-5")
- Top N selection (parses "top 10")

#### 2. Auto-Generation Logic
```python
# User asks naturally:
"Generate a zone allocation for top 10 congested elements on Floors 1-5"

# Agent:
1. Detects keywords: "top 10", "Floors 1-5", "zone allocation"
2. Includes detailed element data in AI context
3. AI analyzes and identifies top 10 elements
4. AI includes keyword: GENERATE_ZONE_ALLOCATION
5. System detects keyword
6. Generates zone allocation with top_n=10, floor_range=(1,5)
7. Saves PDF to logistics_outputs/
8. Shows filepath in response
```

#### 3. Data-Driven Generation
Files use **actual project data**, not generic templates:
- Unloading schedule: Real bar weights from RefLong_Total sheet
- Zone allocation: Real complexity scores from by_element structure
- Floor filtering: Matches actual floor names (PISO 2, PISO 3, etc.)
- Element selection: Sorts by actual complexity_score

### Example Capabilities

**Congestion Analysis:**
```
You: Identify the top 10 most congested elements on Floors 1-5

Agent: Based on processedAnalysis.json:
       1. PISO 4 - V-8: 69 longitudinal bars, 227 stirrups, complexity 3.87
       2. PISO 3 - V-8: 76 longitudinal bars, 222 stirrups, complexity 3.84
       ...
       [Auto-generates zone allocation PDF]
```

**Install Sequencing:**
```
You: Create a micro-sequence install plan for tomorrow

Agent: [Analyzes element complexity and dependencies]
       Install sequence:
       1. PISO 2 - V-8 (07:30-09:00) - Lower complexity, foundation work
       2. PISO 2 - V-3 (09:00-11:00) - Same floor, minimize handling
       ...
       [Auto-generates unloading schedule and zone allocation]
```

**Complete Package:**
```
You: I need all logistics documents for the project

Agent: [Generates all 4 files simultaneously]
       - yard_layout.pdf
       - crane_safety_guidelines.pdf
       - unloading_schedule.xlsx
       - zone_allocation.pdf
```

### Technologies
- **AI**: OpenAI GPT-4o API
- **Data Processing**: pandas, numpy, json
- **PDF Generation**: matplotlib (layouts), reportlab (documents)
- **Excel Generation**: openpyxl
- **File Management**: pathlib, datetime timestamps

### Configuration
**Configurable via SiteParameters:**
```python
site = SiteParameters(
    yard_width=30.0,              # meters
    yard_depth=40.0,              # meters
    crane_center_x=15.0,          # meters
    crane_center_y=20.0,          # meters
    crane_max_radius=25.0,        # meters
    crane_capacity=10.0,          # tonnes
    max_stack_height=3,           # bundles
    max_stack_weight=5.0,         # tonnes
    crew_size=8,                  # workers
    working_hours=("07:00", "17:00"),
    safety_buffer=2.0             # meters
)

agent = LogisticsAgent(site_params=site)
```

---

## 3. File Generators Module
**File:** `file_generators.py`
**Status:** ✅ Production-ready
**Purpose:** Reusable file generation engine

### Key Methods
```python
FileGenerator.__init__(output_dir)

generate_yard_layout_pdf(yard_width, yard_depth, crane_x, crane_y,
                         crane_radius, zones, aisle_width, filename)

generate_unloading_schedule_excel(trucks, bundles, filename)

generate_zone_allocation_pdf(zones, allocations, filename)

generate_crane_safety_pdf(crane_params, safety_zones, procedures, filename)
```

### Features
- Timestamped filenames (prevents overwrites)
- Professional styling and formatting
- Print-ready quality (150 DPI for PDFs)
- Editable Excel files
- Customizable templates

---

## File Locations

### Generated Files
```
logistics_outputs/
├── yard_layout_YYYYMMDD_HHMMSS.pdf
├── crane_safety_guidelines_YYYYMMDD_HHMMSS.pdf
├── unloading_schedule_YYYYMMDD_HHMMSS.xlsx
└── zone_allocation_YYYYMMDD_HHMMSS.pdf
```

### Source Code
```
rc_agent/
├── solution_chat_agent.py          # Solution Q&A agent
├── logistics_agent.py               # Main logistics agent
├── file_generators.py               # File generation module
├── data/
│   ├── despiece.xlsx                # Cutting lists (116KB)
│   ├── processedAnalysis.json       # Engineering metrics (459KB)
│   └── solution.json                # Design solution
└── logistics_outputs/               # Generated files
```

---

## Comparison

| Feature | Solution Chat Agent | Logistics Agent |
|---------|-------------------|-----------------|
| **Data Sources** | solution.json | despiece.xlsx + processedAnalysis.json |
| **Primary Use** | Design Q&A | Construction planning |
| **File Generation** | ❌ No | ✅ 4 types (PDF + Excel) |
| **Detailed Analysis** | Basic | Advanced (element-level) |
| **Floor Filtering** | ❌ No | ✅ Yes (configurable) |
| **Complexity Scoring** | ❌ No | ✅ Yes (from data) |
| **Site Configuration** | ❌ No | ✅ Yes (SiteParameters) |
| **Auto-Generation** | ❌ No | ✅ Yes (keyword-based) |
| **Production Ready** | ✅ Yes | ✅ Yes |

---

## Usage Examples

### Solution Chat Agent
```bash
./venv/Scripts/python.exe solution_chat_agent.py
```

### Logistics Agent
```bash
./venv/Scripts/python.exe logistics_agent.py
```

**Interactive mode:**
```
You: Identify top 10 congested elements on Floors 1-5
Agent: [Analysis + auto-generates zone allocation PDF]

You: Create unloading schedule
Agent: [Analysis + auto-generates Excel schedule]

You: site
Agent: [Shows current yard dimensions, crane specs, etc.]

You: help
Agent: [Shows usage examples and commands]
```

---

## Summary

### Active Agents: 2
1. **Solution Chat Agent** - Design solution Q&A
2. **Logistics Agent** - Production planning with file generation

### Total Tools/Methods: ~25+
- Data loading: 3 methods
- File generation: 4 methods
- Helper methods: 6 methods
- Analysis methods: 5 methods
- User interaction: 4 methods

### File Types Generated: 4
1. Yard Layout PDF (matplotlib + reportlab)
2. Crane Safety PDF (reportlab)
3. Unloading Schedule Excel (openpyxl)
4. Zone Allocation PDF (reportlab)

### Data Integration: Full
- ✅ Reads Excel (5 sheets)
- ✅ Reads JSON (nested structures)
- ✅ Extracts element-level details
- ✅ Filters by floor range
- ✅ Sorts by complexity
- ✅ Uses actual weights and metrics

**The logistics agent is the primary production tool with comprehensive file generation and analysis capabilities!**
