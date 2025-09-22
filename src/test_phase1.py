"""
Test script for RC Agent Phase 1 implementation.
Verifies core functionality without running the full agent.
"""

import sys
import os

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core_services import DataRouter, ConstraintManager, DataValidator
from selection_engine import SelectionEngine, SensitivityAnalyzer
from data_models import OptimizationObjective


def test_data_loading():
    """Test data loading functionality"""
    print("Testing data loading...")

    router = DataRouter()

    try:
        # Test Phase A data loading
        scenarios = router.load_phase_a_data()
        print(f"PASS Phase A: Loaded {len(scenarios)} scenarios")
        print(f"   RS IDs: {list(scenarios.keys())}")

        # Test Phase B data loading
        first_rs = list(scenarios.keys())[0]
        bim_data = router.load_phase_b_data(first_rs)
        print(f"PASS Phase B: Loaded BIM data for {first_rs}")
        print(f"   Building levels: {list(bim_data.get('by_element', {}).keys())}")

    except Exception as e:
        print(f"FAIL Data loading failed: {e}")
        return False

    return True


def test_validation():
    """Test data validation"""
    print("\nTesting data validation...")

    router = DataRouter()
    validator = DataValidator()

    try:
        # Validate Phase A data
        scenarios = router.load_phase_a_data()
        report = validator.validate_phase_a_data(scenarios)

        print(f"PASS Phase A validation: {'Valid' if report.is_valid else 'Invalid'}")
        if report.errors:
            print(f"   Errors: {len(report.errors)}")
        if report.warnings:
            print(f"   Warnings: {len(report.warnings)}")

        # Test validation summary
        print(f"   Summary: {report.data_summary.get('total_scenarios', 0)} scenarios")

    except Exception as e:
        print(f"FAIL Validation failed: {e}")
        return False

    return True


def test_selection():
    """Test solution selection"""
    print("\nTesting solution selection...")

    try:
        router = DataRouter()
        engine = SelectionEngine()
        manager = ConstraintManager()

        # Load data
        scenarios = router.load_phase_a_data()
        engine.load_scenarios(scenarios)

        # Create optimization spec
        spec = manager.create_optimization_spec(
            primary_objective="cost",
            constraints=["duration <= 70"],
            weights={"cost": 0.4, "co2": 0.3, "duration": 0.3}
        )

        # Perform selection
        result = engine.select_solution(spec)

        print(f"PASS Selection completed")
        print(f"   Recommended: {result.recommended_solution}")
        print(f"   Feasible solutions: {len([s for s in result.all_scores if s.is_feasible])}")
        print(f"   Pareto optimal: {len(result.pareto_optimal)}")

    except Exception as e:
        print(f"FAIL Selection failed: {e}")
        return False

    return True


def test_sensitivity():
    """Test sensitivity analysis"""
    print("\nTesting sensitivity analysis...")

    try:
        router = DataRouter()
        engine = SelectionEngine()
        manager = ConstraintManager()

        # Load data
        scenarios = router.load_phase_a_data()
        engine.load_scenarios(scenarios)

        # Create spec
        spec = manager.create_optimization_spec(primary_objective="cost")

        # Run sensitivity analysis
        analyzer = SensitivityAnalyzer(engine)
        result = analyzer.analyze_parameter_sensitivity(spec, "steel_cost", 0.1)

        print(f"PASS Sensitivity analysis completed")
        print(f"   Parameter: {result.parameter}")
        print(f"   Impact score: {result.impact_score:.3f}")
        print(f"   Ranking changes: {len([c for c in result.ranking_changes.values() if c != 0])}")

    except Exception as e:
        print(f"FAIL Sensitivity analysis failed: {e}")
        return False

    return True


def test_enhanced_tools():
    """Test enhanced agent tools"""
    print("\nTesting enhanced tools...")

    try:
        from enhanced_agent_tools import _select_solution, _validate_data

        # Test selection tool
        result = _select_solution("cost", ["duration <= 70"])
        print(f"PASS Selection tool: {len(result)} characters returned")

        # Test validation tool
        result = _validate_data("phase_a")
        print(f"PASS Validation tool: {len(result)} characters returned")

    except Exception as e:
        print(f"FAIL Enhanced tools failed: {e}")
        return False

    return True


def main():
    """Run all tests"""
    print("RC Agent Phase 1 - Test Suite")
    print("=" * 50)

    tests = [
        test_data_loading,
        test_validation,
        test_selection,
        test_sensitivity,
        test_enhanced_tools
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            print(f"FAIL Test failed: {test.__name__}")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} passed")

    if passed == total:
        print("All tests passed! Phase 1 implementation is ready.")
        return True
    else:
        print("Some tests failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)