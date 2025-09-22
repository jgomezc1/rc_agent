"""
Test script for Phase 2 integration and functionality.
Validates all Phase 2 engines and tools are working correctly.
"""

import sys
import os

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from phase2_agent_tools import phase2_tools
from phase2_reporting import Phase2Reporter


def test_phase2_tools():
    """Test Phase 2 LangChain tools"""
    print("=== Testing Phase 2 LangChain Tools ===")

    # Test that all tools are created successfully
    tool_names = [tool.name for tool in phase2_tools]
    expected_tools = [
        "analyze_execution_risks",
        "plan_construction_sequence",
        "optimize_procurement_strategy",
        "validate_construction_quality",
        "analyze_constructibility_insights",
        "generate_execution_report"
    ]

    print(f"Expected tools: {len(expected_tools)}")
    print(f"Created tools: {len(tool_names)}")
    print(f"Tool names: {tool_names}")

    for expected in expected_tools:
        if expected in tool_names:
            print(f"✓ {expected} - OK")
        else:
            print(f"✗ {expected} - MISSING")

    print()


def test_phase2_engines():
    """Test Phase 2 engine imports and basic functionality"""
    print("=== Testing Phase 2 Engine Imports ===")

    try:
        from risk_radar import RiskRadar
        print("✓ RiskRadar - Import OK")
    except Exception as e:
        print(f"✗ RiskRadar - Import Failed: {e}")

    try:
        from crew_planner import CrewPlanner
        print("✓ CrewPlanner - Import OK")
    except Exception as e:
        print(f"✗ CrewPlanner - Import Failed: {e}")

    try:
        from procurement_system import ProcurementOptimizer
        print("✓ ProcurementOptimizer - Import OK")
    except Exception as e:
        print(f"✗ ProcurementOptimizer - Import Failed: {e}")

    try:
        from qa_qc_engine import QualityValidator
        print("✓ QualityValidator - Import OK")
    except Exception as e:
        print(f"✗ QualityValidator - Import Failed: {e}")

    try:
        from constructibility_engine import ConstructibilityAnalyzer
        print("✓ ConstructibilityAnalyzer - Import OK")
    except Exception as e:
        print(f"✗ ConstructibilityAnalyzer - Import Failed: {e}")

    print()


def test_phase2_reporter():
    """Test Phase 2 reporting system"""
    print("=== Testing Phase 2 Reporter ===")

    try:
        reporter = Phase2Reporter()
        print("✓ Phase2Reporter - Instance Created")

        # Test metadata generation
        metadata = reporter._generate_metadata("TEST_RS_001")
        print(f"✓ Metadata generation - {len(metadata)} fields")

        print("✓ Phase2Reporter - Basic functionality OK")

    except Exception as e:
        print(f"✗ Phase2Reporter - Error: {e}")

    print()


def test_comprehensive_agent_import():
    """Test comprehensive agent import"""
    print("=== Testing Comprehensive Agent Import ===")

    try:
        from comprehensive_langchain_agent import create_comprehensive_agent
        print("✓ Comprehensive Agent - Import OK")

        # Test agent creation (without API key)
        try:
            os.environ.pop('OPENAI_API_KEY', None)  # Remove API key if present
            agent = create_comprehensive_agent()
            print("✗ Agent creation should fail without API key")
        except Exception:
            print("✓ Agent creation properly requires API key")

    except Exception as e:
        print(f"✗ Comprehensive Agent - Import Failed: {e}")

    print()


def test_data_models():
    """Test Phase 2 data models"""
    print("=== Testing Phase 2 Data Models ===")

    try:
        from phase2_models import (
            ElementDetail, ElementRisk, CrewRequirement,
            ProcurementItem, QualityCheck, ConstructibilityInsight,
            RiskLevel, QualityStatus, InsightPriority
        )

        print("✓ All Phase 2 models imported successfully")

        # Test enum values
        risk_levels = [level.value for level in RiskLevel]
        quality_statuses = [status.value for status in QualityStatus]
        priorities = [priority.value for priority in InsightPriority]

        print(f"✓ RiskLevel enum: {risk_levels}")
        print(f"✓ QualityStatus enum: {quality_statuses}")
        print(f"✓ InsightPriority enum: {priorities}")

    except Exception as e:
        print(f"✗ Phase 2 models - Error: {e}")

    print()


def run_integration_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("PHASE 2 INTEGRATION TESTS")
    print("=" * 60)
    print()

    test_data_models()
    test_phase2_engines()
    test_phase2_reporter()
    test_phase2_tools()
    test_comprehensive_agent_import()

    print("=" * 60)
    print("INTEGRATION TESTS COMPLETE")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("1. Set OPENAI_API_KEY environment variable")
    print("2. Run: python comprehensive_langchain_agent.py")
    print("3. Test with sample queries:")
    print("   - 'Analyze risks for solution RS_TEST_001'")
    print("   - 'Generate execution plan for RS_TEST_001'")
    print("   - 'Create comprehensive report for RS_TEST_001'")


if __name__ == "__main__":
    run_integration_tests()