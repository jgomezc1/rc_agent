# File Generation Capabilities - Logistics Agent

## Overview

The ProDet+StructuBIM Logistics Agent can now generate 4 types of professional documents for construction planning:

1. **Yard Layout Diagram (PDF)** - Visual 2D layout with zones and crane coverage
2. **Truck Unloading Schedule (Excel)** - Detailed schedules with multiple sheets
3. **Zone Allocation Map (PDF)** - Bundle assignments with utilization metrics
4. **Crane Operation Safety Guidelines (PDF)** - Comprehensive safety procedures

---

## Generated Files

### 1. Yard Layout Diagram (PDF)

**Purpose**: Visual representation of construction yard layout

**Contains**:
- Yard boundaries and dimensions
- Crane position and coverage radius
- Storage zones (color-coded)
- Loading/staging zones
- Aisles and access routes
- Safety buffers
- Zone labels and measurements

**Visual Features**:
- 2D overhead view
- Color-coded zones (green=storage, yellow=loading, coral=staging, gray=aisle)
- Crane coverage circle (blue)
- Grid lines for scale reference
- Legend explaining symbols

**File Size**: ~20-25KB
**Example**: `yard_layout_demo.pdf`

---

### 2. Truck Unloading Schedule (Excel)

**Purpose**: Detailed scheduling for deliveries and unloading operations

**Contains 3 Sheets**:

**Sheet 1: Truck Schedule**
- Truck ID
- Arrival time
- Capacity (tonnes)
- Sorted by arrival time

**Sheet 2: Unloading Sequence**
- Bundle ID
- Truck ID
- Weight (kg)
- Destination zone
- Unload sequence number
- Estimated duration (minutes)

**Sheet 3: Summary**
- Total trucks
- Total bundles
- Total weight
- Estimated unload time
- First arrival / last bundle times

**File Size**: ~6-7KB
**Example**: `unloading_schedule_demo.xlsx`

---

### 3. Zone Allocation Map (PDF)

**Purpose**: Bundle placement planning with weight distribution

**Contains**:

**Allocation Summary Table**:
- Zone ID
- Zone type
- Number of bundles
- Total weight
- Utilization percentage

**Detailed Allocations by Floor**:
- Grouped by floor level
- Bundle ID → Zone mapping
- Individual bundle weights
- Easy-to-read tables

**File Size**: ~2-3KB
**Example**: `zone_allocation_demo.pdf`

---

### 4. Crane Operation Safety Guidelines (PDF)

**Purpose**: Safety procedures and operational guidelines

**Contains**:

**Crane Specifications**:
- Maximum radius
- Lift capacity
- Boom center coordinates
- Safety buffer distances

**Safety Zones**:
- Exclusion Zone (no personnel)
- Restricted Access Zone (authorized only)
- Controlled Access Zone (with awareness)
- Descriptions and restrictions for each

**Safety Procedures** (numbered list):
- Pre-operation inspections
- Load verification
- Personnel clearance
- Communication protocols
- Rigging inspection
- Weather monitoring
- Emergency procedures
- Daily briefings

**File Size**: ~3-4KB
**Example**: `crane_safety_demo.pdf`

---

## How to Use

### Option 1: Run the Demo

```bash
./venv/Scripts/python.exe demo_file_generation.py
```

This generates sample files showing all capabilities.

### Option 2: Generate Files Programmatically

```python
from file_generators import FileGenerator

generator = FileGenerator(output_dir="logistics_outputs")

# Generate yard layout
zones = [
    {'id': 'Z1', 'x': 2, 'y': 2, 'width': 8, 'depth': 10, 'type': 'storage'},
    # ... more zones
]

pdf_path = generator.generate_yard_layout_pdf(
    yard_width=30,
    yard_depth=40,
    crane_x=15,
    crane_y=20,
    crane_radius=25,
    zones=zones,
    filename="my_yard_layout.pdf"
)
```

### Option 3: Through the Logistics Agent (Coming Soon)

The logistics agent will automatically generate these files when you request plans:

```
You: Create a yard layout for tomorrow's delivery

Agent: [Analyzes data and generates yard_layout_20251108.pdf]
       I've created an optimized yard layout...
       Download: logistics_outputs/yard_layout_20251108.pdf
```

---

## File Locations

All generated files are saved in:
```
logistics_outputs/
├── yard_layout_demo.pdf
├── unloading_schedule_demo.xlsx
├── zone_allocation_demo.pdf
└── crane_safety_demo.pdf
```

---

## Customization Options

### Yard Layout
- Yard dimensions (any size)
- Multiple cranes
- Custom zone types
- No-go zones
- Custom colors

### Unloading Schedule
- Any number of trucks
- Any number of bundles
- Custom time windows
- Different capacity units

### Zone Allocation
- Flexible zone definitions
- Multi-floor grouping
- Weight/capacity limits
- Custom metrics

### Safety Guidelines
- Custom safety zones
- Project-specific procedures
- Multiple languages (future)
- Company branding (future)

---

## Technical Details

### Dependencies
- `matplotlib` - Yard layout diagrams
- `reportlab` - PDF generation
- `openpyxl` - Excel file creation
- `pandas` - Data manipulation
- `numpy` - Calculations

### File Formats
- **PDF**: Professional, print-ready, portable
- **Excel**: Editable, analyzable, compatible with MS Excel

### Quality
- PDFs: 150 DPI (suitable for printing)
- Tables: Clean styling with headers
- Colors: Professional construction industry palette

---

## Example Output Descriptions

### Yard Layout PDF
```
┌─────────────────────────────────────────────┐
│         YARD LAYOUT PLAN                     │
│                                              │
│  [Storage-A]  [Aisle]  [Storage-B]          │
│                                              │
│              ◉ Crane                         │
│         (25m radius)                         │
│                                              │
│  [────── Loading Zone ──────]               │
│                                              │
│  Legend: □ Storage  □ Loading  ■ Aisle      │
└─────────────────────────────────────────────┘
```

### Unloading Schedule Excel
```
Sheet: Truck Schedule
┌──────────┬──────────────┬──────────┐
│ Truck ID │ Arrival Time │ Capacity │
├──────────┼──────────────┼──────────┤
│ T-001    │ 08:00        │ 20t      │
│ T-002    │ 10:30        │ 20t      │
│ T-003    │ 14:00        │ 15t      │
└──────────┴──────────────┴──────────┘

Sheet: Unloading Sequence
┌───────────┬──────────┬────────┬──────┬──────┬──────────┐
│ Bundle ID │ Truck ID │ Weight │ Zone │ Seq  │ Duration │
├───────────┼──────────┼────────┼──────┼──────┼──────────┤
│ B-F5-L01  │ T-001    │ 480kg  │ Z1   │ 1    │ 12min    │
│ B-F5-L02  │ T-001    │ 520kg  │ Z1   │ 2    │ 15min    │
└───────────┴──────────┴────────┴──────┴──────┴──────────┘
```

---

## Future Enhancements

Planned features:
- [ ] Multi-language support (Spanish, English)
- [ ] Company branding/logos
- [ ] Interactive PDF forms
- [ ] 3D yard visualizations
- [ ] Real-time updates
- [ ] Mobile-friendly formats
- [ ] Integration with project management tools

---

## Summary

The file generation system provides:
- ✅ Professional, print-ready documents
- ✅ Multiple formats (PDF, Excel)
- ✅ Customizable and extensible
- ✅ Production-ready quality
- ✅ Easy to integrate with logistics agent

**All files are generated programmatically and can be customized for any project!**
