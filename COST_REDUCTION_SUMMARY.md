# Cost Reduction Summary

## Files Modified

### Phase 1: Quick Wins

| File | Changes |
|------|---------|
| `config_agent.py` | Added `max_tokens=4096`, prompt caching via `SystemMessage` with `cache_control`, token logger callback |
| `procurement_agent.py` | Added `max_tokens=4096`, prompt caching, token logger callback, added `SystemMessage` import |
| `prodet_agent.py` | Added `max_tokens=4096`, prompt caching, token logger callback, `max_iterations` 40→20, added `SystemMessage` import |
| `scheduling_agent.py` | Added `max_tokens=4096`, prompt caching, token logger callback, added `SystemMessage` import |
| `grouping_optimizer.py` | Added `max_tokens=4096`, prompt caching, token logger callback, `max_iterations` 40→20 |
| `workflows/config_impact.py` | `_get_llm()` now accepts `max_tokens` param; `propose_changes` uses 1024, `narrate_tradeoff` uses 2048; both LLM nodes use cached `SystemMessage` and token logger; added `SystemMessage` import |
| `utils/__init__.py` | Created (empty package init) |
| `utils/token_logger.py` | Created — `TokenCounterCallback` class: logs per-call token usage, cache read tokens, estimated cost; prints session summary on outermost `on_chain_end` |

### Phase 2: Structural Fixes

| File | Changes |
|------|---------|
| `config_agent.py` | **SF-1**: System prompt reduced from ~6,000 to ~2,462 estimated tokens. Removed inline archetype profiles, engineering interpretation guide, parameter reference, and calibre table. Added `get_reference_material` tool (loads from `docs/` JSON on demand). Prompt now instructs model to call the tool for detailed reference data. **SF-2**: `load_config_summary` gained `summary_only` parameter (strips descriptions when True). |
| `procurement_agent.py` | **SF-2**: `review_reinforcement_file` gained `summary_only=True` default — returns condensed output (sheet names, row/error/warning counts, recommendations) without per-column samples or raw validation details. `compare_reinforcement` now caps floor-level comparison to top-5 deltas by absolute value; returns `floor_comparison_top5` + `floor_count` instead of full listing. |
| `prodet_agent.py` | **SF-3**: Removed `load_config_summary` and `update_config` from tools list (9 tools, was 11). Removed their entries from system prompt. Added instruction: "To view or modify ProDet configuration parameters, instruct the user to switch to the Config Agent." Renumbered remaining tools in prompt. Import kept for internal helpers (`_resolve_config_path`, etc.). |
| `workflows/config_impact.py` | **SF-4**: `_get_llm()` now reads `CLAUDE_WORKFLOW_MODEL` env var, defaulting to `claude-haiku-4-5-20251001`. **SF-5**: Added `_narrate_via_batch()` using raw `anthropic` SDK Batch API with polling (5-min timeout, 5s intervals, progress indicator). `narrate_tradeoff` tries batch first, falls back to synchronous LangChain call. Fixed `_format_comparison` to handle renamed `floor_comparison_top5` key. |

## Deviations from Plan

1. **SF-2 `load_config_summary` `summary_only` default**: The plan says "Apply `summary_only=True` as the default when these tools are called from within a ReAct loop." The `summary_only` parameter defaults to `False` (not `True`) because this tool is called explicitly by users and workflows that need full data. Making it default-True would break existing direct calls. The agent can pass `summary_only=True` when it knows it only needs parameter names/values.

2. **SF-5 Batch scope**: Only `narrate_tradeoff` uses the Batch API. `propose_changes` runs before user confirmation (interactive, can't be batched). The post-confirmation chain has only one LLM call (`narrate_tradeoff`), so there's no multi-request batch to collect. The implementation submits a single-item batch, which still benefits from the 50% Batch API discount when it works.

3. **SF-2 `compare_reinforcement` key rename**: Changed the return key from `floor_comparison` to `floor_comparison_top5` to make the truncation semantically clear. Updated `workflows/config_impact.py` `_format_comparison` to handle both keys for backward compatibility.

## Risks and Regressions

1. **Prompt caching effectiveness**: `cache_control: ephemeral` on `SystemMessage` requires the `langchain-anthropic` library to pass this through to the Anthropic API. If the library strips `additional_kwargs`, caching won't activate. No functional regression — just no cost savings from caching. Verify by checking `cache_read_input_tokens` in token logger output.

2. **Config agent tool-calling increase**: The slimmed system prompt means the agent will make additional tool calls (`get_reference_material`) to retrieve data that was previously inline. This trades prompt tokens (saved every call) for tool-call tokens (incurred only when reference data is needed). Net savings depend on usage patterns — agents that rarely need archetype details save significantly; agents that always need them save less.

3. **Haiku for workflow LLM nodes**: `propose_changes` uses structured output (`with_structured_output`). Haiku is capable of structured output but may produce lower-quality archetype selections for edge cases. Override with `CLAUDE_WORKFLOW_MODEL=claude-sonnet-4-6` if quality issues emerge.

4. **Batch API availability**: The Batch API fallback ensures no functional regression if the `anthropic` package isn't installed or the API is unavailable. However, if the Batch API is available but slow (>5 min), the fallback kicks in after timeout, adding ~5 min latency. Adjust timeout in `_narrate_via_batch` if needed.

5. **ProDet agent config tools removed**: The ProDet agent can no longer directly inspect or modify configs. Workflows that internally import `load_config_summary` from `config_agent` (e.g., `config_impact.py`) are unaffected since they import the function directly, not through the agent's tool list.

6. **Pre-existing test failure**: `test_optimizer.py` fails due to missing `projects/summary.xlsx` fixture — this is pre-existing and unrelated to our changes.

## Recommended Next Steps

1. **Verify prompt caching**: Run any agent, check token logger output for `cache_read` > 0 on the second call in the same session.
2. **Monitor token usage**: Use the token logger output over several sessions to establish baseline costs and measure savings.
3. **Tune `max_tokens`**: The 4096 cap is conservative. If typical responses are shorter, reduce to 2048 for further savings.
4. **Add `CLAUDE_WORKFLOW_MODEL` to `.env.example`**: Document the new environment variable.
5. **Consider streaming for narration**: The batch API adds latency for a single request. Streaming might provide better UX for the narration node.

## Verification Results

### Automated Tests (`pytest tests/test_cost_controls.py -v`)

| Test | Status | Description |
|------|--------|-------------|
| V-1 (×5) | PASS | `max_tokens` set on all 5 ChatAnthropic instances |
| V-2 (×5) | PASS | `cache_control: ephemeral` present on all 5 SystemMessages |
| V-3 (×4) | PASS | TokenCounterCallback extracts usage from generations, llm_output fallback, per-agent tracking, receipt formatting |
| V-4 (×3) | PASS | Config prompt < 2500 est. tokens, correct tool list, ProDet agent excludes config tools |
| V-5 (×5) | PASS | max_iterations ≤ 20 for prodet/grouping, ≤ 15 for config/scheduling/procurement |

**22/22 tests passed.**

### Dry-Run Caching Verification (`python scripts/verify_caching.py --dry-run`)

**7/7 checks passed.** All agents have `cache_control: {"type": "ephemeral"}` on SystemMessage, token logger per-agent tracking works, receipt formatting works.

### Session Cost Receipt (CR-1, CR-2, CR-3)

- `cli.py` creates a single shared `TokenCounterCallback` at session start
- All 5 agent `run()` methods accept optional `token_callback` parameter
- Shared callback is passed through interactive and single-query modes
- Receipt prints on all exit paths: normal exit, quit/exit command, Ctrl+C, EOFError
- Receipt shows per-agent breakdown with model display names (Sonnet 4.6, Haiku 4.5)
