# Multi-Agent System Migration Guide

## Overview

This guide helps you transition from the original monolithic RC Agent to the new **Multi-Agent Architecture** with three specialized agents:

1. **Trade-Off Analyst Agent (T-OAA)** - Pre-Construction/Value Finding
2. **Procurement & Logistics Agent (P&L-A)** - Pre-Construction/JIT Planning
3. **Field Adaptability Agent (F-AA)** - Construction/Risk Mitigation

---

## What's New

### Architectural Changes

**Before (Monolithic):**
```
User → Single Agent → All Tools → Response
```

**After (Multi-Agent):**
```
User → Orchestrator → Specialized Agent → Targeted Tools → Response
                ↓
         Context Sharing
```

### Key Benefits

✅ **Role-Based Access** - Each agent serves specific user types
✅ **Specialized Expertise** - Agents have focused domain knowledge
✅ **Phase-Aware Workflow** - Automatic transitions through project phases
✅ **Better Context Management** - Shared context across agents
✅ **Scalable Architecture** - Easy to add new specialized agents

---

## File Structure

### New Files Created

```
rc_agent/
├── src/agents/                          # New agent package
│   ├── __init__.py                     # Package initialization
│   ├── base_agent.py                   # Base agent class
│   ├── tradeoff_analyst_agent.py       # T-OAA implementation
│   ├── procurement_logistics_agent.py  # P&L-A implementation
│   ├── field_adaptability_agent.py     # F-AA implementation
│   └── orchestrator.py                 # Agent coordination
├── multi_agent_cli.py                  # New unified CLI
├── test_multi_agent_system.py          # Integration tests
├── MULTI_AGENT_ARCHITECTURE.md         # Architecture documentation
└── MULTI_AGENT_MIGRATION_GUIDE.md      # This file
```

### Legacy Files (Still Functional)

The following files are **still functional** but will eventually be deprecated:

- `src/rs_nlp_cli.py` - Old Phase 1 CLI
- `src/phase2_nlp_cli.py` - Old Phase 2 CLI
- `src/comprehensive_langchain_agent.py` - Old unified agent

**Migration Path:**
Old functionality has been **refactored** into the new agents, not replaced. The old files will continue to work during the transition period.

---

## Functionality Mapping

### From Old System to New Agents

| **Old Module** | **New Agent** | **New Location** |
|----------------|---------------|------------------|
| `rs_selector.py` | T-OAA | `agents/tradeoff_analyst_agent.py` |
| `selection_engine.py` | T-OAA | `agents/tradeoff_analyst_agent.py` |
| `procurement_system.py` | P&L-A | `agents/procurement_logistics_agent.py` |
| `crew_planner.py` | P&L-A | `agents/procurement_logistics_agent.py` |
| `risk_radar.py` | F-AA | `agents/field_adaptability_agent.py` |
| `qa_qc_engine.py` | F-AA | `agents/field_adaptability_agent.py` |
| `constructibility_engine.py` | F-AA | `agents/field_adaptability_agent.py` |
| `ai_service.py` | All Agents | `agents/base_agent.py` (integrated) |

### Tool Migration

#### Phase 1 Tools → T-OAA Tools

| **Old Tool** | **New T-OAA Tool** |
|--------------|-------------------|
| `select_solution` | `generate_recommendations` |
| `analyze_pareto_frontier` | `identify_pareto_front` |
| `perform_sensitivity_analysis` | `perform_sensitivity_analysis` |
| `what_if_analysis` | `what_if_analysis` |
| `validate_data` | Built into base agent |
| `generate_detailed_report` | `get_solution_details` + `compare_solutions` |

#### Phase 2 Tools → P&L-A and F-AA Tools

| **Old Tool** | **New Agent** | **New Tool** |
|--------------|---------------|--------------|
| `plan_construction_sequence` | P&L-A | `generate_jit_schedule` |
| `optimize_procurement_strategy` | P&L-A | `create_purchase_orders` |
| `generate_execution_report` | P&L-A | `generate_material_breakdown` |
| `analyze_execution_risks` | F-AA | `scan_proactive_risks` |
| `validate_construction_quality` | F-AA | `report_site_event` |
| `analyze_constructibility_insights` | F-AA | `find_alternate_solutions` |

---

## Quick Start Guide

### 1. Installation

No new dependencies required! The multi-agent system uses the same dependencies:

```bash
# Ensure your venv is activated
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Dependencies already installed from requirements.txt
```

### 2. Environment Setup

Same as before - ensure your `.env` file has the OpenAI API key:

```bash
# .env file
OPENAI_API_KEY=your_api_key_here
```

### 3. Run the Multi-Agent CLI

**Interactive Mode:**
```bash
python multi_agent_cli.py --interactive
```

**With Specific Phase:**
```bash
python multi_agent_cli.py --interactive --phase optimization
```

### 4. Test the System

```bash
python test_multi_agent_system.py
```

---

## Usage Examples

### Example 1: Optimization Phase (T-OAA)

```bash
$ python multi_agent_cli.py --interactive

[OPTIMIZATION] You: Find the most cost-effective solution under $450,000

[T-OAA]: I'll analyze all solutions with that budget constraint...
[Tool Executions]:
  📋 filter_solutions_by_constraints
  📋 generate_recommendations

Based on the analysis, I recommend Solution TR_5a8_L10:
- Total Cost: $443,600 (under budget)
- Duration: 63 days
- CO₂: 510 tonnes
...

[OPTIMIZATION] You: select TR_5a8_L10

✓ Solution TR_5a8_L10 selected
  Transitioned to implementation phase
```

### Example 2: Implementation Phase (P&L-A)

```bash
[IMPLEMENTATION] You: Generate purchase orders for the selected solution

[P&L-A]: I'll create the procurement plan...
[Tool Executions]:
  📋 retrieve_solution_details
  📋 generate_material_breakdown
  📋 create_purchase_orders

Purchase Order Summary:
- Total Orders: 8
- Total Weight: 92.5 tonnes
- Delivery Schedule: By story (14-day lead time)
...
```

### Example 3: Crisis Response (F-AA)

```bash
[IMPLEMENTATION] You: crisis

Report Site Crisis
Event type: material_shortage
Description: 7/8" bar delayed 2 weeks
Affected story: Level_5

✓ Crisis logged
Switched to Field Adaptability Agent (F-AA)

[ADAPTATION] You: Find alternate solutions avoiding 7/8" bar

[F-AA]: Analyzing alternatives...
[Tool Executions]:
  📋 find_alternate_solutions
  📋 calculate_net_impact

Recommended: Switch Level_5 to Solution AG_EM_6_L50
- Uses 3/4" bar (available on site)
- Cost Impact: +$3,200
- Time Saved: 5 days (avoids delay)
...
```

---

## Command Reference

### System Commands

| Command | Description | Example |
|---------|-------------|---------|
| `status` | Show project status | `status` |
| `switch <phase>` | Switch to different phase | `switch implementation` |
| `select <solution>` | Select solution & transition | `select TR_5a8_L10` |
| `crisis` | Report site crisis | `crisis` |
| `help` | Show help message | `help` |
| `exit` | Exit system | `exit` |

### Phase-Specific Queries

**Optimization Phase (T-OAA):**
- "Find solutions under $500k"
- "Show Pareto optimal solutions"
- "Compare TR_5a8_L10 vs AG_EM_5a8_L50"
- "What if steel costs increase 15%?"

**Implementation Phase (P&L-A):**
- "Generate material breakdown"
- "Create JIT delivery schedule"
- "Optimize procurement consolidation"
- "Generate purchase orders"

**Adaptation Phase (F-AA):**
- "Scan for high-risk elements"
- "Find alternate solutions avoiding 7/8 bar"
- "Calculate impact of switching Floor 5 to RS-12"
- "Recommend mixed-solution plan"

---

## API Reference

### Using Orchestrator Programmatically

```python
from agents.orchestrator import AgentOrchestrator, ProjectPhase

# Initialize
orchestrator = AgentOrchestrator(
    project_id="my_project",
    api_key="your_key"
)

# Query active agent
response = orchestrator.query("Find cheapest solution")

# Select solution
orchestrator.select_solution("TR_5a8_L10")

# Switch phases
orchestrator.transition_to_phase(ProjectPhase.IMPLEMENTATION)

# Report crisis
orchestrator.report_crisis(
    event_type="material_shortage",
    description="7/8 bar unavailable",
    severity="high"
)

# Get status
status = orchestrator.get_project_status()
```

### Using Individual Agents

```python
from agents.tradeoff_analyst_agent import TradeOffAnalystAgent
from agents.base_agent import AgentContext

# Create agent
context = AgentContext(project_id="my_project")
agent = TradeOffAnalystAgent(api_key="your_key", context=context)

# Load data
agent.load_phase1_data()

# Use tools directly
result = agent.filter_solutions_by_constraints({
    'total_cost': {'max': 450000}
})

result = agent.identify_pareto_front(
    objectives=['total_cost', 'duration_days', 'co2_tonnes']
)

# Query with LLM
response = agent.process_query("Find the best cost-effective solution")
```

---

## Migration Checklist

### Phase 1: Testing (Week 1)

- [ ] Install/update multi-agent system
- [ ] Run `test_multi_agent_system.py`
- [ ] Verify all 8 tests pass
- [ ] Test interactive CLI with sample queries
- [ ] Compare outputs with old system

### Phase 2: Parallel Operation (Weeks 2-3)

- [ ] Run both old and new systems in parallel
- [ ] Validate consistency of results
- [ ] Train users on new CLI commands
- [ ] Document any discrepancies
- [ ] Gather user feedback

### Phase 3: Transition (Week 4)

- [ ] Switch primary operations to new system
- [ ] Keep old system as backup
- [ ] Monitor for issues
- [ ] Address user questions
- [ ] Update documentation

### Phase 4: Retirement (Week 5+)

- [ ] Confirm new system stability
- [ ] Archive old system files
- [ ] Remove old CLI commands
- [ ] Update all documentation
- [ ] Final user training

---

## Troubleshooting

### Common Issues

**Issue: "OpenAI API key not provided"**
```bash
# Solution: Set environment variable
export OPENAI_API_KEY=your_key_here

# Or pass directly
python multi_agent_cli.py --api-key your_key_here
```

**Issue: "Phase 1 data not loaded"**
```bash
# Solution: Ensure data file exists
ls data/shop_drawings.json

# Check file path in code
# Default: data/shop_drawings.json
```

**Issue: "Phase 2 data not found for solution"**
```bash
# Solution 1: Create solution-specific file
data/TR_5a8_L10.json

# Solution 2: Use unified BIM file
data/shop_drawings_structuBIM.json
```

**Issue: Agent not responding correctly**
```bash
# Check agent initialization
python test_multi_agent_system.py

# Verify API key is valid
echo $OPENAI_API_KEY

# Check model availability (GPT-4 required)
```

### Getting Help

1. **Check test results**: `python test_multi_agent_system.py`
2. **Review logs**: Enable verbose mode in CLI
3. **Consult architecture doc**: `MULTI_AGENT_ARCHITECTURE.md`
4. **Check existing issues**: Review error messages carefully

---

## Advanced Features

### Context Sharing Between Agents

```python
# Export context from one agent
toaa_context = orchestrator.toaa.export_context()

# Import to another agent
orchestrator.faa.import_context(toaa_context)
```

### Save/Load Project State

```python
# Export entire project
project_data = orchestrator.export_project_context()

# Save to file
import json
with open('project_state.json', 'w') as f:
    json.dump(project_data, f)

# Load later
with open('project_state.json', 'r') as f:
    project_data = json.load(f)

orchestrator.import_project_context(project_data)
```

### Custom Agent Configuration

```python
# Create orchestrator with custom model
orchestrator = AgentOrchestrator(
    project_id="custom_project",
    api_key=api_key,
    model="gpt-4-turbo"  # Use different model
)

# Access specific agent and customize
agent = orchestrator.toaa
agent.model = "gpt-4-turbo"
```

---

## Future Enhancements

The multi-agent architecture is designed for extensibility. Future agents could include:

- **Cost Estimation Agent** - Detailed cost breakdown and forecasting
- **Sustainability Agent** - Environmental impact analysis
- **Compliance Agent** - Code and regulation checking
- **Scheduling Agent** - Advanced timeline optimization

---

## Support

For questions or issues:
1. Review this migration guide
2. Check `MULTI_AGENT_ARCHITECTURE.md`
3. Run test suite: `python test_multi_agent_system.py`
4. Examine example queries in this document

---

## Summary

The multi-agent system provides:
- ✅ Better separation of concerns
- ✅ Role-based user experience
- ✅ Phase-aware workflow management
- ✅ Improved scalability and maintainability
- ✅ Backward compatibility during transition

Start with the interactive CLI to explore the new system, then gradually migrate your workflows as you become comfortable with the new architecture.

**Next Steps:**
1. Run `python test_multi_agent_system.py`
2. Try `python multi_agent_cli.py --interactive`
3. Experiment with each agent's capabilities
4. Begin transition planning for your team

Good luck with the migration! 🚀
