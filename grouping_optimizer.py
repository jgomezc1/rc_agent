"""
Grouping Optimizer v1 - Floor Grouping Optimization Agent

This module implements an AI agent that solves floor-grouping problems for
geometrically identical stories using LangChain Expression Language (LCEL)
with Anthropic as the LLM.

The optimization logic is deterministic (Python-based), while the LLM handles
natural language understanding, tool invocation, and result explanation.
"""

import os
import json
import sys
import shutil
import subprocess
import logging
from typing import List, Dict, Any, Optional, Tuple
from itertools import combinations
from math import comb
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from paths import RC_AGENT_ROOT, RC_AGENT_PROJECTS, project_dir

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class GroupResult(BaseModel):
    """Result for a single group within a scenario."""
    group_id: int = Field(description="Group identifier (1-indexed)")
    level_range: str = Field(description="Level range string (e.g., 'L5-L7')")
    levels: List[str] = Field(description="List of level identifiers in this group")
    envelope_steel_per_level: float = Field(description="Envelope steel per level [tonf]")
    group_steel_total: float = Field(description="Total steel for this group [tonf]")
    group_duration_days: float = Field(description="Duration for this group [days]")


class ScenarioResult(BaseModel):
    """Result for a complete grouping scenario."""
    k: int = Field(description="Number of groups")
    groups: List[GroupResult] = Field(description="Details for each group")
    total_steel_tonf: float = Field(description="Total steel consumption [tonf]")
    total_duration_days: float = Field(description="Total duration [days]")
    total_duration_months: float = Field(description="Total duration [months]")
    rank: int = Field(default=0, description="Rank in the shortlist (1 = best)")


# =============================================================================
# Core Optimization Logic (Deterministic)
# =============================================================================

class GroupingOptimizer:
    """
    Core optimizer for floor grouping problems.

    Computes optimal contiguous floor groupings that minimize steel consumption
    while respecting build order and productivity constraints.

    All calculations are deterministic - no LLM involvement in the math.
    """

    def __init__(
        self,
        days_first_in_group: float = 10.0,
        days_repeated: float = 7.0,
        workdays_per_month: float = 21.725
    ):
        self.days_first_in_group = days_first_in_group
        self.days_repeated = days_repeated
        self.workdays_per_month = workdays_per_month
        self.imputations_log: List[str] = []

    def load_data(
        self,
        file_path: str,
        level_col: Optional[str] = None,
        steel_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load data from Excel or CSV file.

        Attempts to auto-detect the header row and column names.
        Supports both English and Spanish column naming conventions.
        """
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            # Try to auto-detect header row
            df_preview = pd.read_excel(file_path, header=None, nrows=5)
            header_row = self._detect_header_row(df_preview, level_col, steel_col)
            df = pd.read_excel(file_path, header=header_row)
        elif file_path.endswith('.csv'):
            df_preview = pd.read_csv(file_path, header=None, nrows=5)
            header_row = self._detect_header_row(df_preview, level_col, steel_col)
            df = pd.read_csv(file_path, header=header_row)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # Normalize column names (strip whitespace, handle NaN column names)
        df.columns = [str(c).strip() if pd.notna(c) else f'col_{i}'
                      for i, c in enumerate(df.columns)]

        return df

    def _detect_header_row(
        self,
        df_preview: pd.DataFrame,
        level_col: Optional[str] = None,
        steel_col: Optional[str] = None
    ) -> int:
        """
        Auto-detect which row contains the headers.

        Looks for common column name patterns in the first few rows.
        """
        # Keywords to look for (both English and Spanish)
        level_keywords = ['nivel', 'level', 'floor', 'piso', 'story']
        steel_keywords = ['steel', 'acero', 'total por nivel', 'steel_total', 'total_por_nivel']

        # Add user-specified column names to keywords if provided
        if level_col:
            level_keywords.append(level_col.lower())
        if steel_col:
            steel_keywords.append(steel_col.lower())

        for row_idx in range(min(10, len(df_preview))):
            row_values = [str(v).lower().strip() for v in df_preview.iloc[row_idx] if pd.notna(v)]

            # Check if this row has both level and steel indicators
            has_level = any(any(kw in val for kw in level_keywords) for val in row_values)
            has_steel = any(any(kw in val for kw in steel_keywords) for val in row_values)

            # Also check that it's not a unit row (containing only 'tonf')
            is_unit_row = all(val in ['tonf', 'ton', '-', 'kg', 'm3'] for val in row_values if val)

            if has_level and has_steel and not is_unit_row:
                return row_idx

        # Default to first row if no pattern detected
        return 0

    def validate_and_prepare_data(
        self,
        df: pd.DataFrame,
        level_col: Optional[str] = None,
        steel_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Validate required columns and prepare data.

        Auto-detects column names if not specified, supporting both
        English and Spanish naming conventions.
        """
        # Column name mappings (normalized -> original)
        col_lower_map = {str(c).lower().strip(): c for c in df.columns}

        # Auto-detect level column if not specified
        if level_col is None:
            level_col = self._find_column(col_lower_map, ['nivel', 'level', 'floor', 'piso'])
        else:
            # Normalize user-provided column name
            level_col_lower = level_col.lower().strip()
            if level_col_lower in col_lower_map:
                level_col = col_lower_map[level_col_lower]
            elif level_col not in df.columns:
                raise ValueError(f"Level column '{level_col}' not found. Available: {list(df.columns)}")

        # Auto-detect steel column if not specified
        if steel_col is None:
            steel_col = self._find_column(col_lower_map,
                ['steel_total_per_level', 'total_por_nivel', 'total por nivel',
                 'steel_total', 'acero_total', 'total'])
        else:
            steel_col_lower = steel_col.lower().strip()
            if steel_col_lower in col_lower_map:
                steel_col = col_lower_map[steel_col_lower]
            elif steel_col not in df.columns:
                raise ValueError(f"Steel column '{steel_col}' not found. Available: {list(df.columns)}")

        if level_col is None:
            raise ValueError(f"Could not auto-detect level column. Available: {list(df.columns)}")
        if steel_col is None:
            raise ValueError(f"Could not auto-detect steel column. Available: {list(df.columns)}")

        logger.info(f"Using columns: level='{level_col}', steel='{steel_col}'")

        # Create working copy with standardized column names
        result = pd.DataFrame()
        result['level'] = df[level_col]
        result['steel_total_per_level'] = pd.to_numeric(df[steel_col], errors='coerce')

        # Filter out rows with invalid/missing level identifiers
        result = result[result['level'].notna()]
        result = result[result['level'].astype(str).str.strip() != '']
        result = result[~result['level'].astype(str).str.lower().isin(
            ['nan', '-', 'totales', 'total', 'tonf', 'ton', 'kg', 'm3']
        )]

        # Filter out rows with invalid steel values
        result = result[result['steel_total_per_level'].notna()]
        result = result[result['steel_total_per_level'] > 0]

        # Reset index after filtering
        result = result.reset_index(drop=True)

        return result

    def _find_column(self, col_map: Dict[str, str], candidates: List[str]) -> Optional[str]:
        """Find the first matching column from a list of candidates."""
        for candidate in candidates:
            candidate_lower = candidate.lower().strip()
            if candidate_lower in col_map:
                return col_map[candidate_lower]
            # Also try partial matching
            for col_lower, col_orig in col_map.items():
                if candidate_lower in col_lower:
                    return col_orig
        return None

    def filter_level_range(
        self,
        df: pd.DataFrame,
        start_level: str,
        end_level: str
    ) -> pd.DataFrame:
        """
        Filter data to specified contiguous level range.

        Returns data ordered bottom-to-top (construction order).
        """
        # Convert levels to string for matching
        df = df.copy()
        df['level'] = df['level'].astype(str)
        levels = df['level'].tolist()

        start_level_str = str(start_level)
        end_level_str = str(end_level)

        try:
            start_idx = levels.index(start_level_str)
        except ValueError:
            available = ', '.join(levels)
            raise ValueError(f"Start level '{start_level}' not found. Available levels: {available}")

        try:
            end_idx = levels.index(end_level_str)
        except ValueError:
            available = ', '.join(levels)
            raise ValueError(f"End level '{end_level}' not found. Available levels: {available}")

        # Ensure proper slicing order
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        filtered = df.iloc[start_idx:end_idx + 1].reset_index(drop=True)

        # Reverse to get bottom-to-top order (construction sequence)
        # Assumes input data is ordered top-to-bottom (roof first)
        filtered = filtered.iloc[::-1].reset_index(drop=True)

        return filtered

    def impute_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Impute missing steel values by averaging immediate neighbors.
        Logs all imputations explicitly.
        """
        self.imputations_log = []
        result = df.copy()

        for idx in range(len(result)):
            if pd.isna(result.loc[idx, 'steel_total_per_level']):
                level = result.loc[idx, 'level']
                neighbors = []

                # Get previous neighbor
                if idx > 0 and not pd.isna(result.loc[idx - 1, 'steel_total_per_level']):
                    neighbors.append(result.loc[idx - 1, 'steel_total_per_level'])

                # Get next neighbor
                if idx < len(result) - 1 and not pd.isna(result.loc[idx + 1, 'steel_total_per_level']):
                    neighbors.append(result.loc[idx + 1, 'steel_total_per_level'])

                if neighbors:
                    imputed_value = sum(neighbors) / len(neighbors)
                    result.loc[idx, 'steel_total_per_level'] = imputed_value

                    log_msg = (
                        f"Level '{level}': steel_total_per_level imputed as "
                        f"{imputed_value:.2f} tonf (average of {len(neighbors)} neighbor(s))"
                    )
                    self.imputations_log.append(log_msg)
                    logger.warning(f"IMPUTATION: {log_msg}")
                else:
                    raise ValueError(
                        f"Cannot impute steel for level '{level}': no valid neighbors available"
                    )

        return result

    def generate_partitions(self, n_levels: int, k: int) -> List[List[int]]:
        """
        Generate all ways to partition n_levels into k contiguous groups.

        Returns list of partition schemes, where each scheme is a list of
        group sizes summing to n_levels.
        """
        if k == 1:
            return [[n_levels]]
        if k > n_levels:
            return []

        partitions = []

        # Use combinations to place k-1 dividers in n_levels-1 possible positions
        for dividers in combinations(range(1, n_levels), k - 1):
            partition = []
            prev = 0
            for div in dividers:
                partition.append(div - prev)
                prev = div
            partition.append(n_levels - prev)
            partitions.append(partition)

        return partitions

    def compute_scenario(
        self,
        df: pd.DataFrame,
        partition: List[int],
        k: int
    ) -> ScenarioResult:
        """Compute steel and duration for a specific partition scheme."""
        groups = []
        total_steel = 0.0
        total_duration = 0.0

        current_idx = 0
        for group_id, group_size in enumerate(partition, start=1):
            group_df = df.iloc[current_idx:current_idx + group_size]
            levels = group_df['level'].tolist()
            steel_values = group_df['steel_total_per_level'].tolist()

            # Envelope = max steel in group
            envelope_steel = max(steel_values)
            group_steel = envelope_steel * group_size

            # Duration: first level + repeated levels
            group_duration = self.days_first_in_group + (group_size - 1) * self.days_repeated

            # Format level range
            if len(levels) == 1:
                level_range = str(levels[0])
            else:
                level_range = f"{levels[0]}-{levels[-1]}"

            groups.append(GroupResult(
                group_id=group_id,
                level_range=level_range,
                levels=[str(l) for l in levels],
                envelope_steel_per_level=round(envelope_steel, 2),
                group_steel_total=round(group_steel, 2),
                group_duration_days=round(group_duration, 2)
            ))

            total_steel += group_steel
            total_duration += group_duration
            current_idx += group_size

        return ScenarioResult(
            k=k,
            groups=groups,
            total_steel_tonf=round(total_steel, 2),
            total_duration_days=round(total_duration, 2),
            total_duration_months=round(total_duration / self.workdays_per_month, 2)
        )

    def optimize(
        self,
        df: pd.DataFrame,
        candidate_k_values: List[int]
    ) -> List[ScenarioResult]:
        """
        Run optimization for all candidate k values.

        Returns scenarios sorted by:
        1. Lowest total steel (primary)
        2. Shortest duration (secondary, for ties)
        """
        n_levels = len(df)
        all_scenarios = []

        for k in candidate_k_values:
            if k > n_levels:
                logger.warning(f"Skipping k={k}: exceeds number of levels ({n_levels})")
                continue

            partitions = self.generate_partitions(n_levels, k)

            for partition in partitions:
                scenario = self.compute_scenario(df, partition, k)
                all_scenarios.append(scenario)

        # Sort by steel (ascending), then by duration (ascending)
        all_scenarios.sort(key=lambda s: (s.total_steel_tonf, s.total_duration_days))

        # Assign ranks
        for rank, scenario in enumerate(all_scenarios, start=1):
            scenario.rank = rank

        return all_scenarios


# =============================================================================
# LangChain Tool Definitions
# =============================================================================

@tool
def load_baseline_steel(
    project_name: str,
    element_type: str = "vigas",
) -> Dict[str, Any]:
    """
    Load floor-level steel totals from an existing project's ProDet output.

    Starting point for the grouping workflow. Reads the Resumen_Refuerzo sheet
    from the project's reinforcement Excel file and returns per-floor steel data.

    Args:
        project_name: Name of the project folder (e.g. "mokara").
        element_type: Element type to load (default: "vigas").
                      Options: vigas, nervios, columnas.

    Returns:
        Dictionary with project info, per-floor steel values, total steel,
        config floor names, and whether a project.config exists.
    """
    try:
        from procurement_agent import (
            _resolve_reinforcement_file,
            _load_resumen,
            _extract_resumen_totals,
        )

        xlsx_path = _resolve_reinforcement_file(project_name, element_type)
        if not xlsx_path:
            return {
                "error": (
                    f"No reinforcement file found for project '{project_name}' "
                    f"(element_type={element_type}). Run ProDet first."
                )
            }

        df = _load_resumen(xlsx_path)
        totals = _extract_resumen_totals(df)

        # Load config floor names if config exists
        from config_agent import _resolve_config_path, _extract_floor_names

        config_floor_names: List[str] = []
        has_config = False
        try:
            config_path = _resolve_config_path(project_name)
            if os.path.isfile(config_path):
                has_config = True
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                config_floor_names = _extract_floor_names(config)
        except Exception:
            pass

        floors = totals.get("floors", [])
        total_steel = totals.get("total_tonf", 0.0)

        return {
            "project_name": project_name,
            "element_type": element_type,
            "xlsx_file": xlsx_path,
            "floors": floors,
            "total_steel_tonf": round(total_steel, 2),
            "floor_count": len(floors),
            "config_floor_names": config_floor_names,
            "has_config": has_config,
        }

    except Exception as e:
        logger.error(f"load_baseline_steel failed: {e}")
        return {"error": str(e)}


@tool
def estimate_groupings(
    project_name: str,
    element_type: str,
    start_level: str,
    end_level: str,
    candidate_k_values: List[int],
    days_first_in_group: float = 10.0,
    days_repeated: float = 7.0,
    workdays_per_month: float = 21.725,
    top_n: int = 5,
) -> Dict[str, Any]:
    """
    Run the combinatorial optimizer on an existing project's ProDet data.

    Loads Resumen_Refuerzo from the project's reinforcement xlsx, runs the
    GroupingOptimizer, and computes deltas vs the ungrouped baseline.

    IMPORTANT: These are ESTIMATES based on envelope_steel = max(steel) * group_size.
    Actual ProDet results will differ by 1-3%. Use apply_grouping to get real numbers.

    Args:
        project_name: Name of the project folder (e.g. "mokara").
        element_type: Element type (e.g. "vigas", "nervios").
        start_level: First level in the range to optimize (e.g. "PISO 5").
        end_level: Last level in the range to optimize (e.g. "PISO 15").
        candidate_k_values: List of group counts to try (e.g. [2, 3, 4]).
        days_first_in_group: Workdays for first level in each group (default: 10).
        days_repeated: Workdays for each repeated level in group (default: 7).
        workdays_per_month: Workdays per month for conversion (default: 21.725).
        top_n: Number of top scenarios to return (default: 5).

    Returns:
        Dictionary with baseline steel, ranked scenarios with deltas, and
        estimation parameters.
    """
    try:
        from procurement_agent import _resolve_reinforcement_file, _load_resumen

        xlsx_path = _resolve_reinforcement_file(project_name, element_type)
        if not xlsx_path:
            return {
                "error": (
                    f"No reinforcement file found for project '{project_name}' "
                    f"(element_type={element_type}). Run ProDet first."
                )
            }

        # Load data via GroupingOptimizer (reads Resumen_Refuerzo)
        optimizer = GroupingOptimizer(
            days_first_in_group=days_first_in_group,
            days_repeated=days_repeated,
            workdays_per_month=workdays_per_month,
        )
        df = optimizer.load_data(xlsx_path)
        df = optimizer.validate_and_prepare_data(df)
        df = optimizer.filter_level_range(df, start_level, end_level)
        df = optimizer.impute_missing_values(df)

        # Baseline = sum of actual steel for the filtered range (no grouping)
        baseline_total = round(df["steel_total_per_level"].sum(), 2)

        # Safeguard: cap k values
        MAX_K = 6
        MAX_PARTITIONS = 50000
        n_levels = len(df)
        filtered_k_values = []
        estimated_partitions = 0

        for k in sorted(candidate_k_values):
            if k > MAX_K:
                logger.warning(f"Skipping k={k}: exceeds maximum allowed ({MAX_K})")
                continue
            if k > n_levels:
                logger.warning(f"Skipping k={k}: exceeds number of levels ({n_levels})")
                continue
            k_partitions = comb(n_levels - 1, k - 1)
            if estimated_partitions + k_partitions > MAX_PARTITIONS:
                logger.warning(f"Skipping k={k}: would exceed max partition limit")
                continue
            filtered_k_values.append(k)
            estimated_partitions += k_partitions

        if not filtered_k_values:
            return {
                "error": (
                    f"No valid k values after filtering. Requested: {candidate_k_values}, "
                    f"max allowed: {MAX_K}, levels: {n_levels}"
                )
            }

        logger.info(f"Optimizing with k={filtered_k_values}, estimated partitions: {estimated_partitions}")
        all_scenarios = optimizer.optimize(df, filtered_k_values)
        top_scenarios = all_scenarios[:top_n]

        # Enrich scenarios with delta vs baseline
        scenarios_out = []
        for s in top_scenarios:
            d = s.model_dump()
            d["delta_tonf"] = round(s.total_steel_tonf - baseline_total, 2)
            d["delta_pct"] = round(
                (s.total_steel_tonf - baseline_total) / baseline_total * 100, 1
            ) if baseline_total > 0 else 0.0
            scenarios_out.append(d)

        return {
            "project_name": project_name,
            "element_type": element_type,
            "baseline_steel_tonf": baseline_total,
            "level_range": f"{df['level'].iloc[0]} to {df['level'].iloc[-1]}",
            "levels_analyzed": n_levels,
            "scenarios": scenarios_out,
            "total_scenarios_evaluated": len(all_scenarios),
            "imputations_log": optimizer.imputations_log,
            "parameters": {
                "days_first_in_group": days_first_in_group,
                "days_repeated": days_repeated,
                "workdays_per_month": workdays_per_month,
            },
            "note": "These are ESTIMATES. Actual results require running ProDet with apply_grouping.",
        }

    except Exception as e:
        logger.error(f"estimate_groupings failed: {e}")
        return {"error": str(e)}


@tool
def apply_grouping(
    project_name: str,
    element_type: str,
    groups_json: str,
    identical_range_start: str,
    identical_range_end: str,
    variant_suffix: str = "grouped",
    timeout_seconds: int = 900,
) -> Dict[str, Any]:
    """
    End-to-end: create config with floor groups, run ProDet, run pipeline, compare.

    Creates a new project variant with grupos_niveles set, runs ProDet to compute
    actual reinforcement, runs the data pipeline, and compares results against
    the ungrouped baseline.

    Args:
        project_name: Baseline project name (e.g. "mokara").
        element_type: Element type to run: "vigas", "nervios", "columnas", or
                      "ambos" (runs both vigas and nervios).
        groups_json: JSON list of floor groups (e.g.
                     '[["PISO 5","PISO 6","PISO 7"],["PISO 8","PISO 9","PISO 10"]]').
        identical_range_start: First floor in the user-declared identical range.
        identical_range_end: Last floor in the user-declared identical range.
        variant_suffix: Suffix for variant folder (default: "grouped").
        timeout_seconds: ProDet timeout per element type in seconds (default: 900).

    Returns:
        Dictionary with variant info, ProDet results, pipeline results, and
        comparison data vs baseline.
    """
    try:
        # Step 1: Create config variant with floor groups
        from config_agent import set_floor_groups

        variant_project = f"{project_name}_{variant_suffix}"
        groups_result = set_floor_groups.invoke({
            "config_path": project_name,
            "groups_json": groups_json,
            "identical_range_start": identical_range_start,
            "identical_range_end": identical_range_end,
            "output_path": variant_project,
        })

        if not groups_result.get("success"):
            return {
                "success": False,
                "error": f"Floor group validation failed: {groups_result.get('error', groups_result)}",
                "validation_details": groups_result,
            }

        variant_dir = groups_result.get("output_dir", project_dir(variant_project))
        groups_applied = json.loads(groups_json)

        # Determine element types to run
        if element_type == "ambos":
            element_types_to_run = ["vigas", "nervios"]
        else:
            element_types_to_run = [element_type]

        # Step 2: Run ProDet for each element type
        from prodet_agent import _run_prodet_single

        prodet_results = {}
        xlsx_paths = []

        for etype in element_types_to_run:
            logger.info(f"Running ProDet for {variant_project} ({etype})...")
            prodet_res = _run_prodet_single(variant_dir, etype, timeout_seconds)
            prodet_results[etype] = {
                "success": prodet_res.get("success", False),
                "elapsed_seconds": prodet_res.get("elapsed_seconds"),
                "output_file": prodet_res.get("output_file"),
            }

            if not prodet_res.get("success"):
                return {
                    "success": False,
                    "variant_project": variant_project,
                    "variant_dir": variant_dir,
                    "groups_applied": groups_applied,
                    "error": f"ProDet failed for {etype}: {prodet_res.get('error', 'unknown')}",
                    "prodet_results": prodet_results,
                }

            # Copy cantidades
            from structubim_handler import copy_cantidades_after_run
            copy_cantidades_after_run(variant_dir, etype)

            # Copy output to reinforcement_solution.xlsx
            output_path = prodet_res.get("output_file")
            if output_path and os.path.isfile(output_path):
                dest = os.path.join(variant_dir, "reinforcement_solution.xlsx")
                if os.path.abspath(output_path) != os.path.abspath(dest):
                    shutil.copy2(output_path, dest)
                xlsx_paths.append(output_path)

        # Step 3: Run data pipeline
        pipeline_result = {"success": False}
        if xlsx_paths:
            pipeline_script = os.path.join(RC_AGENT_ROOT, "run_rebar_pipeline.py")
            cmd = [sys.executable, pipeline_script, "-x"] + xlsx_paths + ["-d", variant_dir]
            try:
                pipe_proc = subprocess.run(
                    cmd,
                    cwd=RC_AGENT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                pipeline_result["success"] = pipe_proc.returncode == 0
                if pipe_proc.returncode != 0:
                    pipeline_result["stderr"] = pipe_proc.stderr[:500]
            except subprocess.TimeoutExpired:
                pipeline_result["error"] = "Pipeline timed out after 120s"
            except Exception as e:
                pipeline_result["error"] = str(e)

            # Check artifacts
            from prodet_agent import PIPELINE_ARTIFACTS
            found = [a for a in PIPELINE_ARTIFACTS if os.path.isfile(os.path.join(variant_dir, a))]
            pipeline_result["artifacts"] = found

        # Step 4: Auto-generate StructuBim JSON (saved to source project folder)
        from prodet_agent import _auto_generate_structubim

        structubim_results = {}
        for etype in element_types_to_run:
            try:
                structubim_results[etype] = _auto_generate_structubim(variant_project, etype)
            except Exception as sb_err:
                logger.warning(f"StructuBim auto-generation failed for {etype}: {sb_err}")
                structubim_results[etype] = {"success": False, "error": str(sb_err)}

        # Step 5: Compare with baseline
        from procurement_agent import compare_reinforcement

        comparison = {}
        for etype in element_types_to_run:
            cmp_result = compare_reinforcement.invoke({
                "baseline_project": project_name,
                "variant_project": variant_project,
                "element_type": etype,
            })
            comparison[etype] = cmp_result

        return {
            "success": True,
            "variant_project": variant_project,
            "variant_dir": variant_dir,
            "groups_applied": groups_applied,
            "prodet_results": prodet_results,
            "pipeline": pipeline_result,
            "structubim": structubim_results,
            "comparison": comparison,
        }

    except Exception as e:
        logger.error(f"apply_grouping failed: {e}")
        return {"success": False, "error": str(e)}


@tool
def compare_grouping_results(
    baseline_project: str,
    grouped_project: str,
    element_type: str = "vigas",
) -> Dict[str, Any]:
    """
    Compare reinforcement between a baseline and a grouped project.

    Wrapper around compare_reinforcement that also loads the grouped project's
    grupos_niveles for context. Useful for re-examining results after
    apply_grouping, or comparing different grouped variants.

    Args:
        baseline_project: Name of the ungrouped baseline project (e.g. "mokara").
        grouped_project: Name of the grouped variant project (e.g. "mokara_grouped").
        element_type: Element type to compare (default: "vigas").

    Returns:
        Dictionary with reinforcement comparison data enriched with grouping info.
    """
    try:
        from procurement_agent import compare_reinforcement

        cmp_result = compare_reinforcement.invoke({
            "baseline_project": baseline_project,
            "variant_project": grouped_project,
            "element_type": element_type,
        })

        # Load grouped project's grupos_niveles for context
        grupos_niveles = []
        try:
            from config_agent import _resolve_config_path
            config_path = _resolve_config_path(grouped_project)
            if os.path.isfile(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                grupos_niveles = config.get("grupos_niveles", [])
        except Exception:
            pass

        cmp_result["grupos_niveles"] = grupos_niveles
        cmp_result["baseline_project"] = baseline_project
        cmp_result["grouped_project"] = grouped_project

        return cmp_result

    except Exception as e:
        logger.error(f"compare_grouping_results failed: {e}")
        return {"error": str(e)}


# =============================================================================
# LCEL Agent Pipeline
# =============================================================================

class GroupingOptimizerAgent:
    """
    End-to-end floor grouping agent.

    Orchestrates the full grouping workflow: load baseline → estimate groupings →
    user selects → create config → run ProDet → compare results. Uses deterministic
    tools for computation and the LLM for reasoning and user interaction.
    """

    SYSTEM_PROMPT = """You are an expert structural engineering assistant specializing in floor grouping optimization for high-rise reinforced concrete construction.

== WORKFLOW ==

Follow these steps in order. Do NOT skip steps or proceed without user input where indicated.

Step 1: Call load_baseline_steel to see floor-level steel for the project.
        Present the floor list and total steel to the user.

Step 2: ASK the user which floors are geometrically identical (same structural layout and spans).
        NEVER assume floors are identical — the user must confirm.
        NOTE: loads naturally vary from floor to floor — that is expected. Geometric
        identity refers to the structural layout (beam spans, column grid, slab geometry),
        NOT the loads. When floors are grouped, ProDet computes the force envelope across
        the group and assigns reinforcement for the worst case in each location.
        Typical identical ranges: typical tower floors (e.g. PISO 5 to PISO 20).
        NOT identical: transfer floors, mezzanines, roof, podium, ground floor.

Step 3: Call estimate_groupings with the user-confirmed identical range and candidate k values.
        Present ranked scenarios as a table with:
        - Rank, k, group ranges
        - Estimated total steel [tonf]
        - Delta vs ungrouped baseline [tonf and %]
        - Total duration [days and months]
        ALWAYS state clearly: "These are estimates. Actual results require running ProDet."

Step 4: ASK the user to select a specific grouping scenario before proceeding.
        Do NOT call apply_grouping without explicit user selection.

Step 5: Call apply_grouping with the selected groups. This creates a new config variant,
        runs ProDet, runs the data pipeline, and compares actual results vs baseline.
        This step takes several minutes — warn the user.

Step 6: Report actual results:
        - Actual steel delta [tonf and %] vs baseline
        - Unique bar type reduction (if available in comparison)
        - How estimate compared to actual
        - Suggest next steps: use Procurement agent for detailed bar lists,
          Scheduling agent for installation planning.

== RULES ==
- NEVER invent data — only use data from tools
- Keep units explicit: tonf for steel, days/months for time
- Groups must be CONTIGUOUS (adjacent floors only)
- Always present both estimated and actual deltas when available
- Default candidate k values: [2, 3, 4] (unless user specifies otherwise)
- Default productivity: days_first_in_group=10, days_repeated=7

== TOOLS ==
1. load_baseline_steel — Load floor-level steel from existing ProDet output
2. estimate_groupings — Run combinatorial optimizer, report estimated deltas
3. apply_grouping — Create config variant, run ProDet, compare actual results
4. compare_grouping_results — Re-examine or compare different grouped variants"""

    def __init__(self, model_name: str = "claude-sonnet-4-6", temperature: float = 0.0):
        """Initialize the agent with specified Anthropic model."""
        self.llm = ChatAnthropic(
            model=model_name,
            temperature=temperature,
            max_tokens=4096,
        )
        self.tools = [
            load_baseline_steel,
            estimate_groupings,
            apply_grouping,
            compare_grouping_results,
        ]
        self.system_message = SystemMessage(
            content=self.SYSTEM_PROMPT,
            additional_kwargs={"cache_control": {"type": "ephemeral"}},
        )
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.system_message,
        )

    def run(self, user_input: str, chat_history: Optional[List] = None, max_iterations: int = 20, token_callback=None) -> str:
        """
        Execute the agent with user input.

        Args:
            user_input: User's request/query
            chat_history: Optional conversation history
            max_iterations: Maximum agent iterations (default: 20)
            token_callback: Optional shared TokenCounterCallback for session tracking.

        Returns:
            Agent's response string
        """
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append(HumanMessage(content=user_input))

        if token_callback:
            token_callback.set_current_agent("grouping", model=self.llm.model)
            token_cb = token_callback
        else:
            from utils.token_logger import TokenCounterCallback
            token_cb = TokenCounterCallback(agent_name="grouping")

        result = self.agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations, "callbacks": [token_cb]},
        )

        if result.get("messages"):
            return result["messages"][-1].content
        return str(result)


# =============================================================================
# Standalone Functions for Direct Use
# =============================================================================

def run_optimization(
    file_path: str,
    start_level: str,
    end_level: str,
    candidate_k_values: List[int],
    days_first_in_group: float = 10.0,
    days_repeated: float = 7.0,
    workdays_per_month: float = 21.725,
    top_n: int = 5
) -> Dict[str, Any]:
    """
    Run optimization directly without the LLM agent.

    Useful for programmatic access or testing.
    """
    try:
        optimizer = GroupingOptimizer(
            days_first_in_group=days_first_in_group,
            days_repeated=days_repeated,
            workdays_per_month=workdays_per_month,
        )
        df = optimizer.load_data(file_path)
        df = optimizer.validate_and_prepare_data(df)
        df = optimizer.filter_level_range(df, start_level, end_level)
        df = optimizer.impute_missing_values(df)

        all_scenarios = optimizer.optimize(df, candidate_k_values)
        top_scenarios = all_scenarios[:top_n]

        return {
            "scenarios": [s.model_dump() for s in top_scenarios],
            "total_scenarios_evaluated": len(all_scenarios),
            "levels_analyzed": len(df),
            "level_range": f"{df['level'].iloc[0]} to {df['level'].iloc[-1]}",
            "imputations_log": optimizer.imputations_log,
            "parameters": {
                "days_first_in_group": days_first_in_group,
                "days_repeated": days_repeated,
                "workdays_per_month": workdays_per_month,
            },
        }

    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        return {"error": str(e)}


def format_results_summary(results: Dict[str, Any]) -> str:
    """Format optimization results as a readable summary."""
    if "error" in results:
        return f"Error: {results['error']}"

    lines = []
    lines.append("=" * 60)
    lines.append("FLOOR GROUPING OPTIMIZATION RESULTS")
    lines.append("=" * 60)
    lines.append(f"Level range analyzed: {results['level_range']}")
    lines.append(f"Levels analyzed: {results['levels_analyzed']}")
    lines.append(f"Total scenarios evaluated: {results['total_scenarios_evaluated']}")
    lines.append("")

    # Log imputations if any
    if results['imputations_log']:
        lines.append("DATA IMPUTATIONS:")
        for imp in results['imputations_log']:
            lines.append(f"  - {imp}")
        lines.append("")

    lines.append("TOP SCENARIOS (ranked by steel, then duration):")
    lines.append("-" * 60)

    for scenario in results['scenarios']:
        lines.append(f"\nRank #{scenario['rank']} - k={scenario['k']} groups")
        lines.append(f"  Total Steel: {scenario['total_steel_tonf']:.2f} tonf")
        lines.append(f"  Total Duration: {scenario['total_duration_days']:.1f} days "
                    f"({scenario['total_duration_months']:.2f} months)")
        lines.append("  Groups:")

        for group in scenario['groups']:
            lines.append(f"    Group {group['group_id']}: {group['level_range']}")
            lines.append(f"      Envelope: {group['envelope_steel_per_level']:.2f} tonf/level")
            lines.append(f"      Group total: {group['group_steel_total']:.2f} tonf")
            lines.append(f"      Duration: {group['group_duration_days']:.1f} days")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    print("Grouping Optimizer v1")
    print("=" * 40)

    # Check if a file path was provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]

        # Example: Direct optimization (without LLM)
        print("\nRunning direct optimization...")
        results = run_optimization(
            file_path=file_path,
            start_level="L1",  # Adjust based on your data
            end_level="L10",   # Adjust based on your data
            candidate_k_values=[2, 3, 4, 5],
            top_n=5
        )

        print(format_results_summary(results))
    else:
        print("\nUsage: python grouping_optimizer.py <path_to_data_file>")
        print("\nOr use programmatically:")
        print("  from grouping_optimizer import GroupingOptimizerAgent")
        print("  agent = GroupingOptimizerAgent()")
        print("  result = agent.optimize_from_file(...)")
