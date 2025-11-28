"""
Grouping Optimizer v1 - Floor Grouping Optimization Agent

This module implements an AI agent that solves floor-grouping problems for
geometrically identical stories using LangChain Expression Language (LCEL)
with OpenAI as the LLM.

The optimization logic is deterministic (Python-based), while the LLM handles
natural language understanding, tool invocation, and result explanation.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from itertools import combinations

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

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
def inspect_data_file(
    file_path: str,
    level_col: Optional[str] = None,
    steel_col: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inspect a data file to see available levels and steel values.

    Use this tool to explore the contents of a dataset before running optimization.
    It shows all available levels, their steel values, and column information.

    Args:
        file_path: Path to Excel (.xlsx) or CSV file with level data
        level_col: Column name for level/floor identifier (auto-detected if None)
        steel_col: Column name for steel total per level (auto-detected if None)

    Returns:
        Dictionary containing:
        - levels: List of all level identifiers in the file
        - steel_values: Steel value for each level [tonf]
        - columns: Available columns in the file
        - row_count: Number of data rows
    """
    try:
        optimizer = GroupingOptimizer()

        # Load and prepare data
        df = optimizer.load_data(file_path, level_col, steel_col)
        raw_columns = list(df.columns)

        df = optimizer.validate_and_prepare_data(df, level_col, steel_col)

        # Build level-steel mapping
        levels = df['level'].astype(str).tolist()
        steel_values = df['steel_total_per_level'].tolist()

        level_data = [
            {"level": lvl, "steel_tonf": round(steel, 2)}
            for lvl, steel in zip(levels, steel_values)
        ]

        return {
            "file": file_path,
            "columns_detected": raw_columns,
            "row_count": len(df),
            "levels_available": levels,
            "level_data": level_data,
            "note": "Levels are listed from top to bottom as in the file. Optimization will reorder to bottom-to-top (construction sequence)."
        }

    except Exception as e:
        logger.error(f"File inspection failed: {str(e)}")
        return {"error": str(e)}


@tool
def grouping_optimizer_v1(
    file_path: str,
    start_level: str,
    end_level: str,
    candidate_k_values: List[int],
    days_first_in_group: float = 10.0,
    days_repeated: float = 7.0,
    workdays_per_month: float = 21.725,
    top_n: int = 5,
    level_col: Optional[str] = None,
    steel_col: Optional[str] = None
) -> Dict[str, Any]:
    """
    Optimize floor groupings to minimize steel consumption.

    This tool analyzes a dataset of floor levels with steel quantities and finds
    optimal contiguous groupings that minimize total steel while considering
    construction duration.

    Args:
        file_path: Path to Excel (.xlsx) or CSV file with level data
        start_level: Starting level identifier for the range to optimize
        end_level: Ending level identifier for the range to optimize
        candidate_k_values: List of candidate values for number of groups (k)
        days_first_in_group: Workdays for first level in each group (default: 10)
        days_repeated: Workdays for each repeated level in group (default: 7)
        workdays_per_month: Workdays per month for conversion (default: 21.725)
        top_n: Number of top scenarios to return (default: 5)
        level_col: Column name for level/floor identifier (auto-detected if None)
        steel_col: Column name for steel total per level (auto-detected if None)

    Returns:
        Dictionary containing:
        - scenarios: Ranked list of grouping scenarios with steel/duration metrics
        - recommendation: Brief explanation of trade-offs
        - imputations_log: List of any data imputations performed
    """
    try:
        # Initialize optimizer with productivity parameters
        optimizer = GroupingOptimizer(
            days_first_in_group=days_first_in_group,
            days_repeated=days_repeated,
            workdays_per_month=workdays_per_month
        )

        # Load and prepare data
        df = optimizer.load_data(file_path, level_col, steel_col)
        df = optimizer.validate_and_prepare_data(df, level_col, steel_col)

        # Filter to specified level range
        df = optimizer.filter_level_range(df, start_level, end_level)

        # Impute any missing values
        df = optimizer.impute_missing_values(df)

        # Run optimization
        all_scenarios = optimizer.optimize(df, candidate_k_values)

        # Get top N scenarios
        top_scenarios = all_scenarios[:top_n]

        # Format output
        result = {
            "scenarios": [s.model_dump() for s in top_scenarios],
            "total_scenarios_evaluated": len(all_scenarios),
            "levels_analyzed": len(df),
            "level_range": f"{df['level'].iloc[0]} to {df['level'].iloc[-1]}",
            "imputations_log": optimizer.imputations_log,
            "parameters": {
                "days_first_in_group": days_first_in_group,
                "days_repeated": days_repeated,
                "workdays_per_month": workdays_per_month
            }
        }

        return result

    except Exception as e:
        logger.error(f"Optimization failed: {str(e)}")
        return {"error": str(e)}


# =============================================================================
# LCEL Agent Pipeline
# =============================================================================

class GroupingOptimizerAgent:
    """
    LCEL-based agent for floor grouping optimization.

    Orchestrates the optimization workflow using LangChain Expression Language
    with OpenAI as the reasoning engine. The LLM handles:
    - Natural language understanding
    - Tool invocation decisions
    - Result formatting and explanation

    The actual optimization is deterministic Python code.
    """

    SYSTEM_PROMPT = """You are an expert structural engineering assistant specializing in floor grouping optimization for high-rise construction.

Your task is to help users optimize floor groupings to minimize steel consumption while considering construction duration trade-offs.

AVAILABLE TOOLS:
1. inspect_data_file - Use this to see available levels and steel values in a file
2. grouping_optimizer_v1 - Use this to run the optimization

IMPORTANT:
- If the user asks about file contents, levels, or data - use inspect_data_file
- When the user provides enough information to run an optimization, IMMEDIATELY call grouping_optimizer_v1. Do NOT ask for confirmation.
- If the user does not specify a file path, USE "data/summary.xlsx" as the default file.
- If the user does not specify start/end levels, first use inspect_data_file to discover available levels, then use the full range.

DEFAULT VALUES (use these if user doesn't specify):
- file_path: "data/summary.xlsx"
- start_level: Use inspect_data_file to find available levels, or ask user
- end_level: Use inspect_data_file to find available levels, or ask user
- days_first_in_group: 10 (workdays for first level in a group)
- days_repeated: 7 (workdays for repeated levels)
- workdays_per_month: 21.725
- candidate_k_values: [2, 3, 4, 5]
- top_n: 5

RULES:
1. NEVER invent data - only use data from the dataset
2. Respect bottom-to-top build order
3. Keep units explicit: tonf for steel, days/months for time
4. Groups must be CONTIGUOUS

After receiving results, present a clear summary with:
- Group ranges (e.g., PISO 5-PISO 7)
- Per-group envelope steel [tonf/level]
- Total steel [tonf]
- Total duration [days and months]

End with a 2-3 line recommendation on the trade-off between steel savings and construction efficiency."""

    def __init__(self, model_name: str = "gpt-4.1-mini", temperature: float = 0.0):
        """Initialize the agent with specified OpenAI model."""
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature
        )
        self.tools = [inspect_data_file, grouping_optimizer_v1]

        # Build the agent using langgraph's create_react_agent
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.SYSTEM_PROMPT
        )

    def run(self, user_input: str, chat_history: Optional[List] = None) -> str:
        """
        Execute the agent with user input.

        Args:
            user_input: User's request/query
            chat_history: Optional conversation history

        Returns:
            Agent's response string
        """
        # Build messages list
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append(HumanMessage(content=user_input))

        # Invoke the agent
        result = self.agent.invoke({"messages": messages})

        # Extract the final response
        if result.get("messages"):
            return result["messages"][-1].content
        return str(result)

    def optimize_from_file(
        self,
        file_path: str,
        start_level: str,
        end_level: str,
        candidate_k_values: List[int],
        days_first_in_group: float = 10.0,
        days_repeated: float = 7.0,
        workdays_per_month: float = 21.725,
        top_n: int = 5
    ) -> str:
        """
        Convenience method to run optimization directly.

        Constructs the appropriate prompt and invokes the agent.
        """
        prompt = f"""Please analyze the floor grouping optimization for the following:

File: {file_path}
Level range: {start_level} to {end_level}
Candidate k values (number of groups): {candidate_k_values}

Productivity parameters:
- Days for first level in group: {days_first_in_group}
- Days for repeated levels: {days_repeated}
- Workdays per month: {workdays_per_month}

Please provide the top {top_n} scenarios ranked by lowest steel consumption (with duration as tiebreaker), and include your recommendation on the optimal trade-off."""

        return self.run(prompt)


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
    return grouping_optimizer_v1.invoke({
        "file_path": file_path,
        "start_level": start_level,
        "end_level": end_level,
        "candidate_k_values": candidate_k_values,
        "days_first_in_group": days_first_in_group,
        "days_repeated": days_repeated,
        "workdays_per_month": workdays_per_month,
        "top_n": top_n
    })


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
