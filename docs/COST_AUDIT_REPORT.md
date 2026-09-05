# Anthropic API Cost Audit Report — RC Agent Platform

**Date:** 2026-03-06
**Branch:** `feature/complete-flow`
**Scope:** All LLM call sites, prompt caching, token controls, agent architecture

---

## 1. Cost Hotspots (Ranked)

### #1 — Config Agent System Prompt: ~8,670 tokens/call

**File:** `config_agent.py:785-1247` (SYSTEM_PROMPT)
**Severity: CRITICAL**

The config agent's system prompt is **34,683 characters (~8,670 tokens)**. This is sent on *every single LLM invocation* — every ReAct loop iteration, every tool call round-trip. In a typical multi-turn conversation with 5 messages and 3-4 tool-use iterations per message, this prompt alone costs:

- Per iteration: ~8,670 input tokens
- Per user turn (3 ReAct loops avg): ~26,010 input tokens just for the system prompt
- Per 5-turn conversation: ~130,050 tokens consumed by the same static text

The prompt contains an entire engineering knowledge base inline: 8 construction dimensions, 6 parameter clusters with Simple/Balanced/Optimized value tables, 6 archetype profiles, interaction warnings, calibre tables, and a 70+ parameter semantic catalog. **None of this uses prompt caching.**

### #2 — No Prompt Caching Anywhere

**Files:** All agent files + `workflows/config_impact.py`
**Severity: CRITICAL**

```
$ grep -r "cache_control\|prompt_caching\|cache_read" *.py
(no results)
```

Zero uses of Anthropic's prompt caching (`cache_control: {"type": "ephemeral"}`). Every system prompt and tool schema is re-processed from scratch on every API call. For reference, cached input tokens cost **90% less** ($0.30/MTok vs $3.00/MTok for Sonnet).

The combined system prompt + tool schema overhead per agent:

| Agent | System Prompt | Tool Schemas | Total Static/Call | Cacheable? |
|-------|--------------|-------------|-------------------|------------|
| Config | ~8,670 | ~1,139 | **~9,809** | Yes — 100% static |
| ProDet | ~2,467 | ~2,416 | **~4,883** | Yes — 100% static |
| Procurement | ~1,503 | ~844 | **~2,347** | Yes — 100% static |
| Scheduling | ~1,129 | ~1,604 | **~2,733** | Yes — 100% static |
| Grouping | ~717 | ~1,546 | **~2,263** | Yes — 100% static |

**All system prompts are 100% static strings** — they never change between calls. This is the ideal prompt caching scenario.

### #3 — No `max_tokens` Constraint on Any Call

**Files:** All 5 agent `__init__` methods, `workflows/config_impact.py:104-106`
**Severity: HIGH**

```python
# config_agent.py:1252
self.llm = ChatAnthropic(model=model, temperature=temperature)
# No max_tokens set

# workflows/config_impact.py:106
return ChatAnthropic(model=model, temperature=0.0)
# No max_tokens set
```

Every `ChatAnthropic` instance is created without `max_tokens`. The Sonnet default is 8,192 output tokens. Without a cap, the model can generate verbose responses that consume unnecessary output tokens. Agent tool-use reasoning messages should rarely need more than 1,024-2,048 tokens.

### #4 — ProDet Agent Has 11 Tools (Highest Tool Schema Overhead)

**File:** `prodet_agent.py:1606-1618`
**Severity: MEDIUM-HIGH**

```python
self.tools = [
    list_projects,              # from prodet_agent
    inspect_project,            # from prodet_agent
    run_prodet,                 # from prodet_agent
    copy_output_to_rc_agent,    # from prodet_agent
    run_data_pipeline,          # from prodet_agent
    load_config_summary,        # IMPORTED from config_agent
    update_config,              # IMPORTED from config_agent
    run_parametric_study,       # from prodet_agent
    generate_structubim_json_tool,  # from prodet_agent
    compose_solution,           # from prodet_agent
    list_solutions,             # from prodet_agent
]
```

11 tools = ~2,416 tokens of tool schemas sent on every call. Two tools (`load_config_summary`, `update_config`) are **duplicated from config_agent** — their full schemas are serialized into both agents' contexts. Additionally, `max_iterations=40` means up to 40 ReAct loops, each re-sending all tool schemas.

### #5 — ReAct Loop Token Amplification (All Agents)

**Files:** All agent `run()` methods
**Severity: HIGH**

LangGraph's `create_react_agent` uses a ReAct loop where each iteration sends:
1. Full system prompt
2. All tool schemas
3. Entire conversation history (including all prior tool calls + results)
4. New reasoning step

Each tool call produces a response that gets appended to the messages array. By iteration N, the context contains N-1 prior reasoning+tool-call+result rounds. For the ProDet agent with `max_iterations=40`:

**Worst case per user turn:** 40 iterations x (4,883 static tokens + growing history) = potentially **200K+ input tokens** for a single question.

Even with the CLI's 5-pair sliding window (`cli.py:231-233`), each pair includes full tool call chains from `create_react_agent`, which include verbose tool results.

### #6 — Chat History Includes Tool Call Artifacts

**File:** `cli.py:228-233`

```python
chat_history.append(HumanMessage(content=message))
chat_history.append(AIMessage(content=response))
```

The `response` from `agent.run()` is just the final text, but the **internal** LangGraph state includes all tool calls and results. The `chat_history` passed back is the outer HumanMessage/AIMessage pairs, which is correct. But inside each `agent.invoke()`, the full ReAct chain accumulates within a single turn.

### #7 — Workflow Creates 2 Fresh LLM Instances Per Run

**File:** `workflows/config_impact.py:104-106, 199-204, 683-701`

```python
def _get_llm() -> ChatAnthropic:
    return ChatAnthropic(model=model, temperature=0.0)
```

Called separately in `propose_changes` (line 203) and `narrate_tradeoff` (line 687). Each creates a new `ChatAnthropic` instance — no connection pooling or session reuse. Neither LLM call benefits from the other's prompt cache, and neither uses caching at all.

### #8 — Large Tool Results Fed Back Into Context

**Files:** `procurement_agent.py`, `prodet_agent.py`
**Severity: MEDIUM**

Tool results that get appended to the ReAct message history can be large:

- `review_reinforcement_file` -> returns `FileReviewResult.model_dump()` with per-sheet validation, column info with sample values, data summaries — easily **2,000-5,000 tokens** per call
- `compare_reinforcement` -> returns baseline stats + variant stats + deltas + diameter comparison + floor-level comparison — **1,000-3,000 tokens**
- `inspect_project` -> returns file listings, config summary, solution metadata — **500-1,500 tokens**
- `load_config_summary` -> returns full parameter summary for all element types — **800-2,000 tokens**
- `run_parametric_study` -> returns per-variant results — **unbounded**, grows linearly with variant count

These results persist in the message history and get re-sent on every subsequent ReAct iteration.

---

## 2. Root Cause Analysis

| Hotspot | Root Cause |
|---------|-----------|
| Giant config prompt | Domain knowledge (archetypes, parameter catalog, impact matrix) embedded directly in system prompt instead of being loaded on-demand via tools |
| No prompt caching | LangChain's `ChatAnthropic` supports `cache_control` via message metadata, but it was never configured |
| No max_tokens | Default `ChatAnthropic()` constructor used without output limits |
| Tool duplication | ProDet agent imports config_agent tools for convenience, paying double schema cost |
| ReAct amplification | `create_react_agent` is the correct pattern, but no mitigation (token budgets, result summarization) is applied |
| No cost tracking | No `callbacks`, no token counting, no per-call logging — impossible to identify regressions |

---

## 3. Quick Wins (<1 hour each)

### QW-1: Add `max_tokens` to all ChatAnthropic instances

**Impact: ~15-25% output cost reduction**

Every agent constructor and `_get_llm()` call should specify `max_tokens`:
- Agent ReAct reasoning: `max_tokens=4096` (generous but bounded)
- Workflow `propose_changes`: `max_tokens=1024` (structured output, small)
- Workflow `narrate_tradeoff`: `max_tokens=2048` (400-word narrative)

Files to change:
- `config_agent.py:1252`
- `procurement_agent.py:2149`
- `prodet_agent.py:1602`
- `scheduling_agent.py:608`
- `grouping_optimizer.py:919`
- `workflows/config_impact.py:106`

### QW-2: Enable prompt caching on system prompts

**Impact: ~40-60% input cost reduction on multi-turn conversations**

LangChain-Anthropic supports prompt caching via message metadata. For each agent, the system prompt should use `cache_control`. Since all system prompts are 100% static and >= 1,024 tokens (the caching minimum), every agent qualifies. The config agent's 8,670-token prompt would save ~$0.0075 per cached hit vs uncached.

### QW-3: Lower `max_iterations` on ProDet and Grouping agents

**Impact: Prevents runaway costs**

- `prodet_agent.py:1630`: `max_iterations=40` -> `max_iterations=20`
- `grouping_optimizer.py:936`: `max_iterations=40` -> `max_iterations=20`

40 iterations is extreme — if an agent hasn't converged in 20 loops, it's likely stuck. This is a safety cap, not an optimization, but prevents catastrophic token burn.

### QW-4: Add token usage logging

**Impact: Enables ongoing cost monitoring**

Add a LangChain callback handler that logs `usage_metadata` from each LLM response. This is zero-cost and provides visibility:

```python
# In each agent's run() method, or globally via callback
result = self.agent.invoke(
    {"messages": messages},
    config={"recursion_limit": max_iterations, "callbacks": [TokenCounterCallback()]},
)
```

---

## 4. Structural Fixes

### SF-1: Extract Config Agent Knowledge Base Into Tool-Retrievable Documents

**Impact: ~70% reduction on config agent input costs**
**Effort: 4-6 hours**

The 8,670-token system prompt contains ~6,000 tokens of reference material (parameter catalog, archetype profiles, impact matrix) that's already in `docs/` as JSON files. Restructure:

1. Slim the system prompt to ~2,500 tokens (reasoning framework + rules only)
2. Add a `get_reference_material(topic)` tool that returns the relevant section on demand
3. Topics: "archetypes", "parameter_catalog", "impact_matrix", "calibre_table"

The LLM would call this tool only when needed rather than carrying the entire knowledge base on every iteration. Net savings: ~6,000 tokens x N iterations per turn.

### SF-2: Summarize Tool Results Before Re-injection

**Impact: ~20-30% reduction on multi-step conversations**
**Effort: 2-3 hours**

After each tool call, the full JSON result persists in the message history. For large results (file reviews, comparisons), add a post-processing step:

- Truncate `review_reinforcement_file` results to summary-only mode (drop per-column sample values, full validation details)
- Cap `compare_reinforcement` floor comparison to top-5 deltas + totals
- Add a `result_summary` field to tool returns that's a concise text version

### SF-3: Remove Duplicated Tools from ProDet Agent

**Impact: ~500 tokens saved per ProDet call**
**Effort: 30 minutes**

Remove `load_config_summary` and `update_config` from `prodet_agent.py:1612-1613`. If ProDet needs config operations, it should instruct the user to switch to the Config Agent, or the CLI should route config-related sub-tasks to the Config Agent internally.

### SF-4: Use Haiku for Classification/Routing Tasks

**Impact: ~80% cost reduction on specific calls**
**Effort: 2-3 hours**

The workflow's `propose_changes` node (`workflows/config_impact.py:199`) uses Sonnet for a structured classification task (pick archetype + list dot-path changes). This is a constrained output space that Haiku 4.5 could handle at ~10x lower cost. Similarly, `narrate_tradeoff` could use Haiku for the 400-word summary.

### SF-5: Batch API for Non-Interactive Workflows

**Impact: 50% cost reduction on workflow runs**
**Effort: 4-6 hours**

The Config Impact workflow is non-interactive after user confirmation. The `run_prodet_all -> compare_all -> generate_structubim -> narrate_tradeoff` chain could use the Batch API (50% discount) since it doesn't need real-time responses. The user is already waiting for ProDet subprocess execution (minutes), so batch latency is negligible.

---

## 5. Estimated Impact Summary

| Fix | Type | Cost Reduction | Effort |
|-----|------|---------------|--------|
| QW-1: Add max_tokens | Quick | ~15-25% output | 15 min |
| QW-2: Prompt caching | Quick | ~40-60% input (multi-turn) | 30 min |
| QW-3: Lower max_iterations | Quick | Prevents runaways | 5 min |
| QW-4: Token logging | Quick | Enables monitoring | 30 min |
| SF-1: Externalize config KB | Structural | ~70% config agent input | 4-6 hrs |
| SF-2: Summarize tool results | Structural | ~20-30% multi-step | 2-3 hrs |
| SF-3: Deduplicate ProDet tools | Structural | ~10% ProDet agent | 30 min |
| SF-4: Haiku for workflow LLM | Structural | ~80% workflow LLM calls | 2-3 hrs |
| SF-5: Batch API for workflows | Structural | ~50% workflow cost | 4-6 hrs |

**Combined quick wins (QW-1 through QW-4): ~40-50% overall cost reduction with ~1 hour of work.**

**Combined all fixes: ~60-75% overall cost reduction.**

The single highest-ROI change is **QW-2 (prompt caching)** — it requires minimal code changes and saves the most on the biggest cost driver (repeated static system prompts across ReAct iterations).

---

## Appendix: LLM Call Inventory

### Agent Call Sites

| Agent | File | LLM Init Line | System Prompt Lines | Tools | max_iterations |
|-------|------|---------------|--------------------|----- -|----------------|
| Config | `config_agent.py` | 1252 | 785-1247 | 3 | 15 |
| Procurement | `procurement_agent.py` | 2149 | 1989-2145 | 5 | 15 |
| ProDet | `prodet_agent.py` | 1602 | 1371-1598 | 11 | 40 |
| Scheduling | `scheduling_agent.py` | 608 | 489-604 | 3 | 15 |
| Grouping | `grouping_optimizer.py` | 919 | 863-915 | 4 | 40 |

### Workflow Call Sites

| Node | File | Line | Type | Prompt Tokens |
|------|------|------|------|---------------|
| propose_changes | `workflows/config_impact.py` | 203-217 | Structured output | ~484 system + ~800 user |
| narrate_tradeoff | `workflows/config_impact.py` | 687-702 | Free-form generation | ~266 system + ~1,500 user |

### Missing Controls

- `cache_control`: Not used in any file
- `max_tokens`: Not set on any ChatAnthropic instance
- Token logging/callbacks: None configured
- Batch API: Not used
- Model tiering (Haiku vs Sonnet): All calls use Sonnet
