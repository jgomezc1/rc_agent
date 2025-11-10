# Quick Start Guide - Logistics Agent

## Getting Started in 3 Steps

### 1. Start the Agent
```bash
./venv/Scripts/python.exe logistics_agent.py
```

### 2. Ask Questions Naturally
The agent automatically generates professional files when you ask for:

- **"Create a yard layout"** → Generates PDF with 2D site layout
- **"I need crane safety guidelines"** → Generates PDF with safety procedures
- **"Show me the unloading schedule"** → Generates Excel with delivery timeline
- **"Generate zone allocation plan"** → Generates PDF with storage assignments
- **"I need all logistics documents"** → Generates all 4 files at once

### 3. Get Your Files
All files saved to `logistics_outputs/` with timestamps:
```
logistics_outputs/
├── yard_layout_20251108_125507.pdf (23KB)
├── crane_safety_guidelines_20251108_125508.pdf (2.9KB)
├── unloading_schedule_20251108_125508.xlsx (6.4KB)
└── zone_allocation_20251108_125508.pdf (2.7KB)
```

---

## Example Conversations

### Get Yard Layout
```
You: Create a yard layout for the project site

Agent: [Explains layout considerations...]

       ============================================================
       GENERATED FILES:
       ============================================================
       [OK] Yard Layout: logistics_outputs\yard_layout_20251108_125507.pdf
```

### Get Safety Guidelines
```
You: Generate crane safety guidelines for tomorrow

Agent: [Lists safety protocols...]

       ============================================================
       GENERATED FILES:
       ============================================================
       [OK] Crane Safety Guidelines: logistics_outputs\crane_safety_guidelines_20251108_125508.pdf
```

### Get Complete Package
```
You: I need all logistics documents for the project

Agent: [Explains each document...]

       ============================================================
       GENERATED FILES:
       ============================================================
       [OK] Yard Layout: logistics_outputs\yard_layout_20251108_125507.pdf
       [OK] Crane Safety Guidelines: logistics_outputs\crane_safety_guidelines_20251108_125508.pdf
       [OK] Unloading Schedule: logistics_outputs\unloading_schedule_20251108_125508.xlsx
       [OK] Zone Allocation Map: logistics_outputs\zone_allocation_20251108_125508.pdf
```

---

## What You Can Ask

### Yard Planning
- "How should I organize the yard?"
- "Create an optimal yard layout"
- "I need a site layout diagram"
- "Show me crane coverage"

### Safety
- "What are the crane safety procedures?"
- "Generate safety guidelines"
- "I need safety documentation for the team"

### Scheduling
- "When should deliveries arrive?"
- "Create an unloading schedule"
- "I need a delivery timeline"
- "How many trucks do we need?"

### Storage
- "Where should bundles go?"
- "Show me zone allocations"
- "How much space do we need?"
- "What's the storage plan?"

### General Questions
- "What's the total rebar weight?"
- "How many floors are there?"
- "What bar diameters are used?"
- "How many different bar types?"

---

## File Contents

### Yard Layout PDF (23KB)
- 2D overhead view of 30m × 40m yard
- Crane position and 25m coverage circle
- 5 color-coded zones (storage, loading, staging, aisles)
- Dimensions and labels
- Professional quality for printing

### Crane Safety PDF (2.9KB)
- Crane specifications (radius, capacity, position)
- Safety zones (exclusion, restricted access)
- 8 safety procedures
- Emergency protocols
- Ready for team distribution

### Unloading Schedule Excel (6.4KB)
- **Sheet 1**: Truck schedule with arrival times
- **Sheet 2**: Bundle unloading sequence
- **Sheet 3**: Summary statistics
- Based on actual project data
- Editable for adjustments

### Zone Allocation PDF (2.7KB)
- Zone summary table with utilization
- Floor-by-floor bundle assignments
- Weight distribution
- Based on actual project floors and bundles

---

## Data Sources

The agent uses actual project data:
- **despiece.xlsx**: Bar weights, configurations, cutting lists
- **processedAnalysis.json**: Floor data, complexity scores, element metrics

All generated files reflect real project parameters.

---

## Tips

1. **Be Natural**: Just ask in plain English, the agent understands
2. **Multiple Requests**: Ask for multiple files at once
3. **Follow-ups**: Ask follow-up questions for clarification
4. **Timestamped Files**: Each generation creates new files (no overwrites)
5. **Professional Quality**: All files are print-ready and shareable

---

## Troubleshooting

**Q: Files not generating?**
A: Check that `logistics_outputs/` folder exists

**Q: Can't find files?**
A: Look for timestamps in filenames (YYYYMMDD_HHMMSS)

**Q: Need custom data?**
A: Edit despiece.xlsx or processedAnalysis.json before running

**Q: Agent not responding?**
A: Check .env file has valid OPENAI_API_KEY

---

## What's Next?

After generating files, you can:
1. **Print** yard layout for site posting
2. **Distribute** safety guidelines to team
3. **Edit** Excel schedule as needed
4. **Share** zone allocation with crew leads
5. **Ask more questions** about logistics planning

---

**The agent combines AI intelligence with professional documentation. Just ask naturally and get production-ready files!**
