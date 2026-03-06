#!/usr/bin/env python3
"""
Workflow 1: Config Impact Analysis — StateGraph

Automates the loop: load baseline → propose config changes (LLM) →
user confirmation (interrupt) → create variant → run ProDet → compare
reinforcement → narrate trade-off (LLM).

Usage:
    from workflows.config_impact import build_config_impact_workflow

    workflow = build_config_impact_workflow()
    # First invoke runs until interrupt
    result = workflow.invoke(
        {"project_name": "mokara", "user_intent": "simplify for speed"},
        config={"configurable": {"thread_id": "1"}},
    )
    # Resume after user confirmation
    from langgraph.types import Command
    result = workflow.invoke(
        Command(resume=True),
        config={"configurable": {"thread_id": "1"}},
    )
"""

import os
import logging
from typing import TypedDict, Dict, List, Any, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# State Schema
# =============================================================================

class ConfigImpactState(TypedDict, total=False):
    # Inputs
    project_name: str
    user_intent: str

    # After load_baseline
    config_summary: Dict[str, Any]
    element_types: List[str]
    baseline_has_output: Dict[str, bool]

    # After propose_changes (LLM)
    archetype_target: str
    proposed_changes: Dict[str, Any]
    rationale: str
    expected_impact: str
    variant_suffix: str

    # After user confirmation (interrupt resume value)
    user_confirmed: bool

    # After create_variant
    variant_name: str
    variant_config_result: Dict[str, Any]

    # After run_prodet + run_pipeline
    prodet_results: Dict[str, Dict[str, Any]]
    pipeline_results: Dict[str, Dict[str, Any]]

    # After compare
    comparison: Dict[str, Any]

    # After narrate (LLM)
    narrative: str

    # After generate_structubim
    structubim_output: Optional[List[str]]

    # Status tracking
    messages: List[str]
    error: Optional[str]


# =============================================================================
# Pydantic model for structured LLM output
# =============================================================================

class ProposedChanges(BaseModel):
    """Structured output from the propose_changes LLM node."""
    archetype_target: str = Field(description="Target archetype name (e.g. 'Simple/Robust', 'Speed-Focused')")
    rationale: str = Field(description="Why these changes address the user's intent")
    changes: Dict[str, Any] = Field(description="Dot-path keyed config changes (e.g. {'vigas.param_despiece.calibre_max': 5})")
    expected_impact: str = Field(description="Qualitative prediction of the impact on steel and construction")
    variant_suffix: str = Field(description="Short suffix for the variant project name (e.g. 'speed', 'simple')")


# =============================================================================
# LLM Setup
# =============================================================================

def _get_llm() -> ChatAnthropic:
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    return ChatAnthropic(model=model, temperature=0.0)


# =============================================================================
# Node: load_baseline
# =============================================================================

def load_baseline(state: ConfigImpactState) -> dict:
    """Load the baseline project config and detect available element types."""
    from config_agent import load_config_summary as _load_config_summary
    from procurement_agent import _resolve_reinforcement_file

    project_name = state["project_name"]
    messages = list(state.get("messages", []))

    # Load config summary (call the raw function, not the @tool wrapper)
    config_summary = _load_config_summary.invoke({"config_path": project_name})
    if "error" in config_summary:
        return {"error": config_summary["error"], "messages": messages + [f"Error: {config_summary['error']}"]}

    messages.append(f"Loaded config for project '{project_name}'")

    # Detect element types from the CONFIG (which sections exist),
    # not from existing output files. If the config defines vigas and
    # nervios, both must be run through ProDet.
    config_element_types = list(config_summary.get("element_types", {}).keys())
    # Only include types that ProDet can process (vigas, nervios)
    element_types = [et for et in config_element_types if et in ("vigas", "nervios")]
    if not element_types:
        element_types = ["vigas"]

    messages.append(f"Element types from config: {element_types}")

    # Check which types already have reinforcement output (to skip
    # redundant baseline ProDet runs)
    baseline_has_output: Dict[str, bool] = {}
    for etype in element_types:
        xlsx = _resolve_reinforcement_file(project_name, etype)
        baseline_has_output[etype] = xlsx is not None

    missing = [et for et, has in baseline_has_output.items() if not has]
    if missing:
        messages.append(f"Baseline missing output for: {missing} — ProDet will run for these.")

    return {
        "config_summary": config_summary,
        "element_types": element_types,
        "baseline_has_output": baseline_has_output,
        "messages": messages,
    }


# =============================================================================
# Node: propose_changes (LLM)
# =============================================================================

PROPOSE_SYSTEM_PROMPT = """You are a senior reinforced concrete construction engineer specializing in ProDet configuration optimization.

Given a project's current config summary and the user's intent, propose specific config changes that shift the design toward the appropriate archetype.

== ARCHETYPE SELECTION LOGIC ==

Primary signals:
- "speed/schedule/deadline/fast-track" → Speed-Focused (ARCH-05)
- "cost/budget/minimize steel/economical" → Cost-Optimized (ARCH-03)
- "simple/easy/errors/inexperienced/reliable" → Simple/Robust (ARCH-01)
- "prefab/cage/factory/off-site" → Prefab-Ready (ARCH-06)
- "tall building/high-rise/tower/15+ floors" → High-Rise Repetitive (ARCH-04)
- "balanced/standard/typical/normal" → Balanced (ARCH-02)

== KEY PARAMETER DOT-PATHS ==

Cluster A (Bar Complexity): vigas.param_despiece.calibre_min, vigas.param_despiece.calibre_max, vigas.param_despiece.dif_max_cal
Cluster B (Splice): vigas.param_despiece.empalmar_siempre, vigas.param_despiece.zonas_empalme
Cluster C (Stirrups): vigas.estribos.calibre_est_ext_min, vigas.estribos.calibre_est_ext_max, vigas.estribos.calibre_est_int_min, vigas.estribos.calibre_est_int_max
Cluster D (Merging): vigas.param_despiece.tol_union, vigas.param_despiece.long_homog, vigas.param_despiece.maxva, vigas.param_despiece.max_long_NE

Same paths apply to nervios (replace "vigas" with "nervios") when the project has nervios.

== CALIBRE INDEX TABLE ==
0='1/4"', 1='3/8"', 2='1/2"', 3='5/8"', 4='3/4"', 5='7/8"', 6='1"', 7='1-1/4"'

== LONG_HOMOG VALUES ==
0 = 0.10m rounding (finest), 1 = 0.50m (standard), 2 = 1.00m (coarsest)

== CRITICAL RULES ==
- Always use integer indices for calibre fields (not strings like '3/4"')
- Only propose changes to parameters that EXIST in the config summary
- Keep the variant_suffix short (3-8 chars, lowercase, no spaces)
- If the project has nervios, apply matching changes to nervios too
- Never push Cluster A and E toward Optimized simultaneously"""


def propose_changes(state: ConfigImpactState) -> dict:
    """Use LLM to propose config changes based on user intent."""
    messages = list(state.get("messages", []))

    llm = _get_llm()
    structured_llm = llm.with_structured_output(ProposedChanges)

    config_summary = state["config_summary"]
    user_intent = state["user_intent"]
    element_types = state["element_types"]

    user_msg = (
        f"Project: {config_summary.get('project_name', state['project_name'])}\n"
        f"Element types: {element_types}\n"
        f"User intent: {user_intent}\n\n"
        f"Current config summary:\n{_format_config_summary(config_summary)}"
    )

    result = structured_llm.invoke([
        {"role": "system", "content": PROPOSE_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])

    messages.append(f"Proposed archetype: {result.archetype_target}")
    messages.append(f"Changes: {len(result.changes)} parameter modifications")

    return {
        "archetype_target": result.archetype_target,
        "proposed_changes": result.changes,
        "rationale": result.rationale,
        "expected_impact": result.expected_impact,
        "variant_suffix": result.variant_suffix,
        "messages": messages,
    }


def _format_config_summary(summary: Dict[str, Any]) -> str:
    """Format config summary for the LLM prompt (concise text)."""
    lines = []
    lines.append(f"Project: {summary.get('project_name', 'Unknown')}")
    lines.append(f"Seismic demand: {summary.get('seismic_demand', 'Unknown')}")
    lines.append(f"Modo: {summary.get('modo', 'Unknown')}")

    for etype, edata in summary.get("element_types", {}).items():
        lines.append(f"\n--- {etype} ---")
        if "rebar_range" in edata:
            rr = edata["rebar_range"]
            lines.append(f"  Rebar range: {rr.get('min')} to {rr.get('max')} (idx {rr.get('min_idx')}-{rr.get('max_idx')})")
        if "detailing" in edata:
            d = edata["detailing"]
            lines.append(f"  Cutting rounding (long_homog): {d.get('cutting_length_rounding', {}).get('value', '?')}")
            lines.append(f"  Max bar length: {d.get('max_bar_length_m', '?')}m")
            lines.append(f"  Max calibre jump: {d.get('max_caliber_jump', '?')}")
            lines.append(f"  Always splice: {d.get('always_splice', '?')}")
            lines.append(f"  Splice zones: {d.get('splice_zones', '?')}")
            lines.append(f"  Moment redistribution: {d.get('moment_redistribution', {}).get('active', '?')}")
            lines.append(f"  Headed bars: {d.get('headed_bars', '?')}")
        if "stirrups" in edata:
            s = edata["stirrups"]
            lines.append(f"  Stirrup ext range: {s.get('calibre_range_exterior', '?')}")
            lines.append(f"  Stirrup int range: {s.get('calibre_range_interior', '?')}")
            lines.append(f"  Min stirrups: {s.get('min_count', '?')}")

    groups = summary.get("floor_groups", [])
    if groups:
        lines.append(f"\nFloor groups: {len(groups)} groups defined")
    else:
        lines.append("\nFloor groups: none")

    return "\n".join(lines)


# =============================================================================
# Node: confirm_with_user (interrupt)
# =============================================================================

def confirm_with_user(state: ConfigImpactState) -> dict:
    """Interrupt to ask the user for confirmation of proposed changes."""
    proposal = {
        "archetype_target": state.get("archetype_target", ""),
        "proposed_changes": state.get("proposed_changes", {}),
        "rationale": state.get("rationale", ""),
        "expected_impact": state.get("expected_impact", ""),
        "variant_suffix": state.get("variant_suffix", ""),
    }

    # interrupt() pauses the graph and returns this value to the caller.
    # The caller resumes with Command(resume=<value>).
    user_response = interrupt(proposal)

    # user_response is whatever the caller passed via Command(resume=...)
    confirmed = bool(user_response)
    messages = list(state.get("messages", []))
    messages.append(f"User confirmation: {confirmed}")

    return {"user_confirmed": confirmed, "messages": messages}


# =============================================================================
# Node: create_variant
# =============================================================================

def create_variant(state: ConfigImpactState) -> dict:
    """Create a variant project folder with the proposed config changes."""
    from prodet_agent import _create_variant_config

    project_name = state["project_name"]
    suffix = state["variant_suffix"]
    changes = state["proposed_changes"]
    messages = list(state.get("messages", []))

    result = _create_variant_config(project_name, suffix, changes)

    if not result.get("success"):
        return {
            "error": result.get("error", "Failed to create variant config"),
            "messages": messages + [f"Error creating variant: {result.get('error')}"],
        }

    variant_name = result["variant_project"]
    messages.append(f"Created variant project: {variant_name}")

    return {
        "variant_name": variant_name,
        "variant_config_result": result,
        "messages": messages,
    }


# =============================================================================
# Node: run_prodet_all
# =============================================================================

ELEMENT_TYPE_SUFFIX = {"vigas": "_V", "nervios": "_N"}


def _copy_prodet_output(project_path: str, prodet_result: Dict[str, Any], element_type: str) -> Optional[str]:
    """Copy ProDet output xlsx with type-specific name.

    Returns the destination path on success, None on failure.
    """
    import shutil
    output_path = prodet_result.get("output_file")
    if not output_path or not os.path.isfile(output_path):
        return None
    suffix = ELEMENT_TYPE_SUFFIX.get(element_type, "")
    dest = os.path.join(project_path, f"reinforcement_solution{suffix}.xlsx")
    if os.path.abspath(output_path) != os.path.abspath(dest):
        shutil.copy2(output_path, dest)
    return dest


def _run_data_pipeline(project_name: str, xlsx_paths: List[str]) -> Dict[str, Any]:
    """Run the rebar data pipeline with one or more xlsx files for a project.

    Generates elements.json → elements_with_ci.json → elements_with_prod.json
    → work_packages.json → floor_schedule.json, which are needed by the
    procurement and scheduling agents.
    """
    import sys
    import subprocess
    from paths import RC_AGENT_ROOT, project_dir
    from prodet_agent import PIPELINE_ARTIFACTS

    data_dir = project_dir(project_name)
    pipeline_script = os.path.join(RC_AGENT_ROOT, "run_rebar_pipeline.py")

    if not os.path.isfile(pipeline_script):
        return {"success": False, "error": f"Pipeline script not found: {pipeline_script}"}

    try:
        cmd = [sys.executable, pipeline_script]
        cmd.extend(["-x"] + xlsx_paths)
        cmd.extend(["-d", data_dir])

        result = subprocess.run(
            cmd,
            cwd=RC_AGENT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        artifacts = {}
        for name in PIPELINE_ARTIFACTS:
            artifacts[name] = os.path.isfile(os.path.join(data_dir, name))

        return {
            "success": result.returncode == 0 and all(artifacts.values()),
            "return_code": result.returncode,
            "artifacts": artifacts,
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Pipeline timed out after 120s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_prodet_all(state: ConfigImpactState) -> dict:
    """Run ProDet for baseline (if needed) and variant, for each element type.

    Phase 1: Run ProDet for all element types and collect xlsx paths.
    Phase 2: Run the data pipeline ONCE per project with all xlsx files,
    producing a single merged elements.json.
    """
    from prodet_agent import (
        _run_prodet_single, _find_prodet_output,
        PRODET_PROJECTS,
    )
    from procurement_agent import _resolve_reinforcement_file
    from structubim_handler import copy_cantidades_after_run

    project_name = state["project_name"]
    variant_name = state["variant_name"]
    element_types = state["element_types"]
    baseline_has_output = state.get("baseline_has_output", {})
    messages = list(state.get("messages", []))

    prodet_results: Dict[str, Dict[str, Any]] = {}
    pipeline_results: Dict[str, Dict[str, Any]] = {}

    # Phase 1: Run ProDet for all element types, collect xlsx paths
    baseline_xlsx_paths: List[str] = []
    variant_xlsx_paths: List[str] = []

    for etype in element_types:
        etype_results: Dict[str, Any] = {}

        # --- Baseline ---
        if not baseline_has_output.get(etype, False):
            baseline_path = os.path.join(PRODET_PROJECTS, project_name)
            msg = f"Running ProDet for baseline ({project_name}/{etype})..."
            messages.append(msg)
            print(f"  {msg}")
            base_res = _run_prodet_single(baseline_path, etype, timeout_seconds=900)
            etype_results["baseline_run"] = base_res
            if base_res.get("success"):
                messages.append(f"  Baseline {etype} completed in {base_res.get('elapsed_seconds', '?')}s")
                copy_cantidades_after_run(baseline_path, etype)
                dest = _copy_prodet_output(baseline_path, base_res, etype)
                if dest:
                    baseline_xlsx_paths.append(dest)
            else:
                messages.append(f"  Baseline {etype} FAILED: {base_res.get('error', 'unknown')}")
                etype_results["baseline_error"] = base_res.get("error", "unknown")
        else:
            # Find existing output file
            existing = _resolve_reinforcement_file(project_name, etype)
            if existing:
                baseline_xlsx_paths.append(existing)

        # --- Variant ---
        variant_path = os.path.join(PRODET_PROJECTS, variant_name)
        msg = f"Running ProDet for variant ({variant_name}/{etype})..."
        messages.append(msg)
        print(f"  {msg}")
        var_res = _run_prodet_single(variant_path, etype, timeout_seconds=900)
        etype_results["variant_run"] = var_res
        if var_res.get("success"):
            messages.append(f"  Variant {etype} completed in {var_res.get('elapsed_seconds', '?')}s")
            copy_cantidades_after_run(variant_path, etype)
            dest = _copy_prodet_output(variant_path, var_res, etype)
            if dest:
                variant_xlsx_paths.append(dest)
        else:
            messages.append(f"  Variant {etype} FAILED: {var_res.get('error', 'unknown')}")
            etype_results["variant_error"] = var_res.get("error", "unknown")

        prodet_results[etype] = etype_results

    # Phase 2: Run pipeline ONCE per project with all xlsx files
    if baseline_xlsx_paths:
        msg = f"Running data pipeline for baseline ({project_name}) with {len(baseline_xlsx_paths)} xlsx file(s)..."
        messages.append(msg)
        print(f"  {msg}")
        pipe_res = _run_data_pipeline(project_name, baseline_xlsx_paths)
        pipeline_results["baseline"] = pipe_res
        if pipe_res.get("success"):
            messages.append(f"  Baseline pipeline complete")
        else:
            messages.append(f"  Baseline pipeline warning: {pipe_res.get('error', 'partial')}")

    if variant_xlsx_paths:
        msg = f"Running data pipeline for variant ({variant_name}) with {len(variant_xlsx_paths)} xlsx file(s)..."
        messages.append(msg)
        print(f"  {msg}")
        pipe_res = _run_data_pipeline(variant_name, variant_xlsx_paths)
        pipeline_results["variant"] = pipe_res
        if pipe_res.get("success"):
            messages.append(f"  Variant pipeline complete")
        else:
            messages.append(f"  Variant pipeline warning: {pipe_res.get('error', 'partial')}")

    return {
        "prodet_results": prodet_results,
        "pipeline_results": pipeline_results,
        "messages": messages,
    }


# =============================================================================
# Node: compare_all
# =============================================================================

def compare_all(state: ConfigImpactState) -> dict:
    """Compare reinforcement between baseline and variant for all element types."""
    from procurement_agent import compare_reinforcement

    project_name = state["project_name"]
    variant_name = state["variant_name"]
    element_types = state["element_types"]
    messages = list(state.get("messages", []))

    if len(element_types) == 1:
        # Single element type — straightforward comparison
        result = compare_reinforcement.invoke({
            "baseline_project": project_name,
            "variant_project": variant_name,
            "element_type": element_types[0],
        })
        if "error" in result:
            return {
                "error": result["error"],
                "messages": messages + [f"Comparison error: {result['error']}"],
            }
        messages.append(f"Comparison complete for {element_types[0]}")
        return {"comparison": result, "messages": messages}

    # Multiple element types — compare each and merge
    comparisons = {}
    for etype in element_types:
        result = compare_reinforcement.invoke({
            "baseline_project": project_name,
            "variant_project": variant_name,
            "element_type": etype,
        })
        if "error" in result:
            messages.append(f"Comparison error for {etype}: {result['error']}")
            continue
        comparisons[etype] = result

    if not comparisons:
        return {
            "error": "No successful comparisons",
            "messages": messages + ["All comparisons failed"],
        }

    # Merge: sum weights and bar types across element types
    merged = _merge_comparisons(comparisons)
    messages.append(f"Merged comparison across {list(comparisons.keys())}")
    return {"comparison": merged, "messages": messages}


def _merge_comparisons(comparisons: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Merge comparison results from multiple element types."""
    # Use the first comparison as the base structure
    merged_baseline = {"total_weight_tonf": 0, "longitudinal_tonf": 0, "transverse_tonf": 0,
                       "unique_bar_types_total": 0, "diameters_used": set()}
    merged_variant = {"total_weight_tonf": 0, "longitudinal_tonf": 0, "transverse_tonf": 0,
                      "unique_bar_types_total": 0, "diameters_used": set()}

    all_diameter_comparison: Dict[str, Dict[str, float]] = {}
    all_floor_comparison: List[Dict[str, Any]] = []
    element_types = []

    for etype, comp in comparisons.items():
        element_types.append(etype)
        base = comp.get("baseline", {})
        var = comp.get("variant", {})

        for key in ("total_weight_tonf", "longitudinal_tonf", "transverse_tonf", "unique_bar_types_total"):
            merged_baseline[key] += base.get(key, 0)
            merged_variant[key] += var.get(key, 0)

        merged_baseline["diameters_used"].update(base.get("diameters_used", []))
        merged_variant["diameters_used"].update(var.get("diameters_used", []))

        for dia, vals in comp.get("diameter_comparison", {}).items():
            if dia not in all_diameter_comparison:
                all_diameter_comparison[dia] = {"baseline_tonf": 0, "variant_tonf": 0, "delta_tonf": 0}
            for k in ("baseline_tonf", "variant_tonf", "delta_tonf"):
                all_diameter_comparison[dia][k] += vals.get(k, 0)

    # Convert sets to sorted lists
    merged_baseline["diameters_used"] = sorted(merged_baseline["diameters_used"])
    merged_variant["diameters_used"] = sorted(merged_variant["diameters_used"])

    # Compute merged deltas
    delta_weight = merged_variant["total_weight_tonf"] - merged_baseline["total_weight_tonf"]
    delta_bar_types = merged_variant["unique_bar_types_total"] - merged_baseline["unique_bar_types_total"]

    merged_delta = {
        "total_weight_tonf": round(delta_weight, 4),
        "total_weight_pct": round(delta_weight / merged_baseline["total_weight_tonf"] * 100, 1)
            if merged_baseline["total_weight_tonf"] != 0 else 0,
        "longitudinal_tonf": round(merged_variant["longitudinal_tonf"] - merged_baseline["longitudinal_tonf"], 4),
        "transverse_tonf": round(merged_variant["transverse_tonf"] - merged_baseline["transverse_tonf"], 4),
        "unique_bar_types": delta_bar_types,
        "unique_bar_types_pct": round(delta_bar_types / merged_baseline["unique_bar_types_total"] * 100, 1)
            if merged_baseline["unique_bar_types_total"] != 0 else 0,
    }

    # Add notes to diameter comparison
    for dia, vals in all_diameter_comparison.items():
        for k in ("baseline_tonf", "variant_tonf", "delta_tonf"):
            vals[k] = round(vals[k], 4)
        if vals["baseline_tonf"] > 0 and vals["variant_tonf"] == 0:
            vals["note"] = "eliminated"
        elif vals["baseline_tonf"] == 0 and vals["variant_tonf"] > 0:
            vals["note"] = "introduced"

    return {
        "element_types": element_types,
        "baseline": merged_baseline,
        "variant": merged_variant,
        "delta": merged_delta,
        "diameter_comparison": all_diameter_comparison,
        "per_element_type": comparisons,
    }


# =============================================================================
# Node: generate_structubim
# =============================================================================

def generate_structubim(state: ConfigImpactState) -> dict:
    """Generate per-element-type StructuBim JSON files for baseline + variant."""
    from structubim_handler import find_cantidades, generate_structubim_json
    from prodet_agent import PRODET_PROJECTS

    project_name = state["project_name"]
    variant_name = state["variant_name"]
    element_types = state["element_types"]
    messages = list(state.get("messages", []))

    baseline_path = os.path.join(PRODET_PROJECTS, project_name)
    variant_path = os.path.join(PRODET_PROJECTS, variant_name)

    output_paths = []
    for etype in element_types:
        etype_project_paths = {}
        for name, path in [(project_name, baseline_path), (variant_name, variant_path)]:
            data = find_cantidades(path, [etype])
            if data:
                etype_project_paths[name] = path

        if not etype_project_paths:
            messages.append(f"No cantidades.json found for {etype} — skipping")
            continue

        out = os.path.join(variant_path, f"{etype}.json")
        result = generate_structubim_json(etype_project_paths, out, [etype])
        if result.get("success"):
            output_paths.append(out)
            messages.append(f"StructuBim JSON generated: {out}")
        else:
            messages.append(f"StructuBim generation warning for {etype}: {result.get('error', 'unknown')}")

    return {
        "structubim_output": output_paths if output_paths else None,
        "messages": messages,
    }


# =============================================================================
# Node: narrate_tradeoff (LLM)
# =============================================================================

NARRATE_SYSTEM_PROMPT = """You are a senior construction engineering advisor writing a trade-off analysis for a structural engineer.

Given the baseline config, proposed changes, and measured comparison data, write a concise but specific narrative. Include:

1. **What changed**: Which archetype shift was made and why (1-2 sentences)
2. **Quantitative impact**: Steel weight delta (kg and %), unique bar types delta (count and %), diameter distribution shift. Use the exact numbers from the comparison data.
3. **Construction implications**: What this means for the crew, using the 8 construction dimensions:
   - D1 Material Cost, D2 Piece Count, D3 Field Error Risk, D4 Installation Speed,
   - D5 Required Skill, D6 Drawing Clarity, D7 Inspection Complexity, D8 Adaptability
4. **Recommendation**: Is this trade-off worth it given the user's stated intent? Be specific.

Format: Use markdown with headers. Keep it under 400 words. Use bold for key numbers.
Convert tonf to kg where it makes the number more intuitive (multiply by 1000).
Always state both absolute and percentage changes."""


def narrate_tradeoff(state: ConfigImpactState) -> dict:
    """Use LLM to narrate the trade-off based on comparison data."""
    messages = list(state.get("messages", []))

    llm = _get_llm()
    comparison = state["comparison"]
    config_summary = state.get("config_summary", {})

    user_msg = (
        f"User intent: {state.get('user_intent', '')}\n\n"
        f"Archetype shift: {state.get('archetype_target', '')}\n"
        f"Rationale: {state.get('rationale', '')}\n\n"
        f"Proposed changes:\n{_format_changes(state.get('proposed_changes', {}))}\n\n"
        f"Comparison data:\n{_format_comparison(comparison)}"
    )

    result = llm.invoke([
        {"role": "system", "content": NARRATE_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])

    narrative = result.content
    messages.append("Trade-off narrative generated")

    return {"narrative": narrative, "messages": messages}


def _format_changes(changes: Dict[str, Any]) -> str:
    lines = []
    for path, val in changes.items():
        lines.append(f"  {path} = {val}")
    return "\n".join(lines) if lines else "  (none)"


def _format_comparison(comparison: Dict[str, Any]) -> str:
    lines = []
    delta = comparison.get("delta", {})
    lines.append(f"Weight delta: {delta.get('total_weight_tonf', 0)} tonf ({delta.get('total_weight_pct', 0):+.1f}%)")
    lines.append(f"  Longitudinal: {delta.get('longitudinal_tonf', 0):+.4f} tonf")
    lines.append(f"  Transverse: {delta.get('transverse_tonf', 0):+.4f} tonf")
    lines.append(f"Bar types delta: {delta.get('unique_bar_types', 0):+d} ({delta.get('unique_bar_types_pct', 0):+.1f}%)")

    base = comparison.get("baseline", {})
    var = comparison.get("variant", {})
    lines.append(f"\nBaseline total: {base.get('total_weight_tonf', 0)} tonf, {base.get('unique_bar_types_total', 0)} unique bar types")
    lines.append(f"Variant total: {var.get('total_weight_tonf', 0)} tonf, {var.get('unique_bar_types_total', 0)} unique bar types")

    dia_comp = comparison.get("diameter_comparison", {})
    if dia_comp:
        lines.append("\nDiameter breakdown:")
        for dia, vals in dia_comp.items():
            note = f" ({vals['note']})" if "note" in vals else ""
            lines.append(f"  {dia}: baseline {vals['baseline_tonf']} → variant {vals['variant_tonf']} tonf (delta {vals['delta_tonf']:+.4f}){note}")

    floor_comp = comparison.get("floor_comparison", [])
    if floor_comp:
        lines.append("\nFloor-level (first 5):")
        for fc in floor_comp[:5]:
            lines.append(f"  {fc['floor']}: {fc['baseline_tonf']} → {fc['variant_tonf']} tonf ({fc['delta_pct']:+.1f}%)")

    return "\n".join(lines)


# =============================================================================
# Graph Construction
# =============================================================================

def build_config_impact_workflow():
    """Build and compile the Config Impact Analysis StateGraph."""
    from langgraph.checkpoint.memory import MemorySaver

    graph = StateGraph(ConfigImpactState)

    graph.add_node("load_baseline", load_baseline)
    graph.add_node("propose_changes", propose_changes)
    graph.add_node("confirm_with_user", confirm_with_user)
    graph.add_node("create_variant", create_variant)
    graph.add_node("run_prodet_all", run_prodet_all)
    graph.add_node("compare_all", compare_all)
    graph.add_node("generate_structubim", generate_structubim)
    graph.add_node("narrate_tradeoff", narrate_tradeoff)

    graph.add_edge(START, "load_baseline")
    graph.add_edge("load_baseline", "propose_changes")
    graph.add_edge("propose_changes", "confirm_with_user")
    graph.add_conditional_edges(
        "confirm_with_user",
        lambda s: "create_variant" if s.get("user_confirmed") else "__end__",
    )
    graph.add_edge("create_variant", "run_prodet_all")
    graph.add_edge("run_prodet_all", "compare_all")
    graph.add_edge("compare_all", "generate_structubim")
    graph.add_edge("generate_structubim", "narrate_tradeoff")
    graph.add_edge("narrate_tradeoff", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["confirm_with_user"])
