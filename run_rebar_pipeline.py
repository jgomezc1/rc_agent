#!/usr/bin/env python
"""
run_rebar_pipeline.py

One-step pipeline to go from a ProDet .xlsx reinforcement file to all
derived JSON artifacts used by the scheduling agent:

1) prodet_to_elements.py      -> elements.json
2) ci_tool.py                 -> elements_with_ci.json
3) productivity_tool.py       -> elements_with_prod.json
4) aggregate_workload_tool.py -> work_packages.json
5) schedule_tool.py           -> floor_schedule.json

Adjust the script names if your files are named differently.
"""

import argparse
import logging
import os
import subprocess
import sys
from typing import List


logger = logging.getLogger(__name__)


def run_step(cmd: List[str], description: str) -> None:
    """
    Run a subprocess step and abort the pipeline on failure.
    """
    logger.info("Running %s: %s", description, " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        logger.error("%s failed with return code %s", description, result.returncode)
        sys.exit(result.returncode)
    logger.info("%s completed successfully.", description)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full RC rebar pipeline starting from a ProDet .xlsx file, "
            "producing all intermediate JSON files required by the scheduling agents."
        )
    )

    parser.add_argument(
        "--xlsx",
        "-x",
        required=True,
        help="Path to the input ProDet .xlsx file (reinforcement_solution.xlsx or similar).",
    )
    parser.add_argument(
        "--data-dir",
        "-d",
        default="data",
        help="Directory where JSON artifacts will be written (default: ./data).",
    )
    parser.add_argument(
        "--hours-per-day",
        "-hpd",
        type=float,
        default=None,
        help="Optional override for hours per day for schedule_tool (default: use schedule_tool default).",
    )

    # Optional: override script names if your files are named differently
    parser.add_argument(
        "--xlsx-to-elements-script",
        default="reinforcement_parser.py",
        help="Script that converts the .xlsx file to elements.json (default: reinforcement_parser.py).",
    )
    parser.add_argument(
        "--ci-script",
        default="complexity_index.py",
        help="Script that adds CI to elements.json (default: complexity_index.py).",
    )
    parser.add_argument(
        "--prod-script",
        default="productivity.py",
        help="Script that adds productivity fields to elements_with_ci.json (default: productivity.py).",
    )
    parser.add_argument(
        "--aggregate-script",
        default="work_packages.py",
        help="Script that builds work_packages.json (default: work_packages.py).",
    )
    parser.add_argument(
        "--schedule-script",
        default="floor_schedule.py",
        help="Script that builds floor_schedule.json (default: floor_schedule.py).",
    )

    args = parser.parse_args()

    # Resolve paths
    xlsx_path = os.path.abspath(args.xlsx)
    data_dir = os.path.abspath(args.data_dir)

    if not os.path.exists(xlsx_path):
        logger.error("Input .xlsx file not found: %s", xlsx_path)
        sys.exit(1)

    os.makedirs(data_dir, exist_ok=True)

    elements_json = os.path.join(data_dir, "elements.json")
    elements_ci_json = os.path.join(data_dir, "elements_with_ci.json")
    elements_prod_json = os.path.join(data_dir, "elements_with_prod.json")
    work_packages_json = os.path.join(data_dir, "work_packages.json")
    floor_schedule_json = os.path.join(data_dir, "floor_schedule.json")

    logger.info("Input .xlsx: %s", xlsx_path)
    logger.info("Output directory: %s", data_dir)

    # 1) XLSX -> elements.json
    run_step(
        [
            sys.executable,
            args.xlsx_to_elements_script,
            "--input",
            xlsx_path,
            "--output",
            elements_json,
        ],
        "prodet_to_elements",
    )

    # 2) elements.json -> elements_with_ci.json
    run_step(
        [
            sys.executable,
            args.ci_script,
            "--input",
            elements_json,
            "--output",
            elements_ci_json,
        ],
        "ci_tool",
    )

    # 3) elements_with_ci.json -> elements_with_prod.json
    run_step(
        [
            sys.executable,
            args.prod_script,
            "--input",
            elements_ci_json,
            "--output",
            elements_prod_json,
        ],
        "productivity_tool",
    )

    # 4) elements_with_prod.json -> work_packages.json
    run_step(
        [
            sys.executable,
            args.aggregate_script,
            "--input",
            elements_prod_json,
            "--output",
            work_packages_json,
        ],
        "aggregate_workload_tool",
    )

    # 5) work_packages.json -> floor_schedule.json
    schedule_cmd = [
        sys.executable,
        args.schedule_script,
        "--input",
        work_packages_json,
        "--output",
        floor_schedule_json,
    ]
    if args.hours_per_day is not None:
        schedule_cmd.extend(
            ["--hours-per-day", str(args.hours_per_day)]
        )

    run_step(schedule_cmd, "schedule_tool")

    logger.info("Pipeline completed successfully.")
    logger.info("Final floor schedule: %s", floor_schedule_json)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )
    main()
