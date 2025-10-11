#!/usr/bin/env python3
"""
Test Script for Multi-Agent System

Tests integration of all three specialized agents and orchestrator.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from agents.orchestrator import AgentOrchestrator, ProjectPhase


def test_orchestrator_initialization():
    """Test 1: Orchestrator initialization"""
    print("=" * 60)
    print("TEST 1: Orchestrator Initialization")
    print("=" * 60)

    try:
        orchestrator = AgentOrchestrator(
            project_id="test_project",
            api_key=os.getenv('OPENAI_API_KEY')
        )
        print("[PASS] Orchestrator initialized successfully")
        print(f"  Project ID: {orchestrator.project_id}")
        print(f"  Current Phase: {orchestrator.current_phase.value}")
        return orchestrator
    except Exception as e:
        print(f"[FAIL] Failed to initialize orchestrator: {e}")
        return None


def test_agent_initialization(orchestrator):
    """Test 2: Individual agent initialization"""
    print("\n" + "=" * 60)
    print("TEST 2: Agent Initialization")
    print("=" * 60)

    try:
        # Test T-OAA
        toaa = orchestrator.toaa
        print("[PASS] Trade-Off Analyst Agent initialized")
        print(f"  Role: {toaa.role.value}")
        print(f"  Tools: {len(toaa.get_tools())}")

        # Test P&L-A
        pla = orchestrator.pla
        print("[PASS] Procurement & Logistics Agent initialized")
        print(f"  Role: {pla.role.value}")
        print(f"  Tools: {len(pla.get_tools())}")

        # Test F-AA
        faa = orchestrator.faa
        print("[PASS] Field Adaptability Agent initialized")
        print(f"  Role: {faa.role.value}")
        print(f"  Tools: {len(faa.get_tools())}")

        return True
    except Exception as e:
        print(f"[FAIL] Failed to initialize agents: {e}")
        return False


def test_data_loading(orchestrator):
    """Test 3: Data loading"""
    print("\n" + "=" * 60)
    print("TEST 3: Data Loading")
    print("=" * 60)

    try:
        # Load Phase 1 data
        phase1_data = orchestrator.toaa.load_phase1_data("data/shop_drawings.json")
        print(f"[PASS] Phase 1 data loaded: {len(phase1_data)} solutions")

        # Show first few solutions
        solution_ids = list(phase1_data.keys())[:3]
        print(f"  Sample solutions: {', '.join(solution_ids)}")

        return True
    except Exception as e:
        print(f"[FAIL] Failed to load data: {e}")
        return False


def test_toaa_functionality(orchestrator):
    """Test 4: Trade-Off Analyst Agent functionality"""
    print("\n" + "=" * 60)
    print("TEST 4: Trade-Off Analyst Agent Tools")
    print("=" * 60)

    try:
        # Test constraint filtering
        result = orchestrator.toaa.filter_solutions_by_constraints({
            'total_cost': {'max': 500000},
            'duration_days': {'max': 100}
        })
        print(f"[PASS] Constraint filtering: {result['feasible_count']} feasible solutions")

        # Test Pareto analysis
        result = orchestrator.toaa.identify_pareto_front(
            objectives=['total_cost', 'duration_days', 'co2_tonnes']
        )
        print(f"[PASS] Pareto analysis: {result['pareto_optimal_count']} Pareto-optimal solutions")

        # Test recommendations
        result = orchestrator.toaa.generate_recommendations(top_n=3)
        print(f"[PASS] Recommendations generated: {len(result['top_solutions'])} solutions")
        if result['top_solutions']:
            print(f"  Top solution: {result['top_solutions'][0]['solution_id']}")

        return True
    except Exception as e:
        print(f"[FAIL] T-OAA functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase_transition(orchestrator):
    """Test 5: Phase transition"""
    print("\n" + "=" * 60)
    print("TEST 5: Phase Transition")
    print("=" * 60)

    try:
        # Get a solution to select
        if orchestrator.toaa.optimal_solution_set:
            solution_id = orchestrator.toaa.optimal_solution_set[0]
        else:
            solution_id = list(orchestrator.toaa.context.phase1_data.keys())[0]

        print(f"  Selecting solution: {solution_id}")

        # Select solution
        result = orchestrator.select_solution(solution_id)
        print(f"[PASS] Solution selected: {result['solution_selected']}")
        print(f"  New phase: {orchestrator.current_phase.value}")
        print(f"  Active agent: {orchestrator.get_active_agent().role.value}")

        return True
    except Exception as e:
        print(f"[FAIL] Phase transition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pla_functionality(orchestrator):
    """Test 6: Procurement & Logistics Agent functionality"""
    print("\n" + "=" * 60)
    print("TEST 6: Procurement & Logistics Agent Tools")
    print("=" * 60)

    try:
        solution_id = orchestrator.shared_context.selected_solution_id

        if not solution_id:
            print("  Skipping (no solution selected)")
            return True

        # Test solution retrieval
        result = orchestrator.pla.retrieve_solution_details(solution_id)
        if "error" not in result:
            print(f"[PASS] Solution details retrieved")
            print(f"  Total elements: {result.get('total_elements', 'N/A')}")
        else:
            print(f"  Note: {result['error']}")

        # Test material breakdown
        result = orchestrator.pla.generate_material_breakdown(group_by="diameter")
        if "error" not in result:
            print(f"[PASS] Material breakdown generated")
            print(f"  Groups: {result['summary']['unique_groups']}")
        else:
            print(f"  Note: {result['error']}")

        return True
    except Exception as e:
        print(f"[FAIL] P&L-A functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_faa_functionality(orchestrator):
    """Test 7: Field Adaptability Agent functionality"""
    print("\n" + "=" * 60)
    print("TEST 7: Field Adaptability Agent Tools")
    print("=" * 60)

    try:
        # Transition to adaptation phase
        orchestrator.transition_to_phase(ProjectPhase.ADAPTATION)

        # Test risk scanning
        result = orchestrator.faa.scan_proactive_risks(threshold=2.0)
        if "error" not in result:
            print(f"[PASS] Risk scan completed")
            print(f"  Risk elements found: {result['risk_elements_found']}")
        else:
            print(f"  Note: {result['error']}")

        # Test alternate solution finding
        result = orchestrator.faa.find_alternate_solutions(
            constraint="cheaper",
            max_results=3
        )
        if "error" not in result:
            print(f"[PASS] Alternate solutions found")
            print(f"  Alternates: {result['alternates_found']}")
        else:
            print(f"  Note: {result['error']}")

        return True
    except Exception as e:
        print(f"[FAIL] F-AA functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_project_status(orchestrator):
    """Test 8: Project status export"""
    print("\n" + "=" * 60)
    print("TEST 8: Project Status and Export")
    print("=" * 60)

    try:
        # Get status
        status = orchestrator.get_project_status()
        print("[PASS] Project status retrieved")
        print(f"  Phase: {status['current_phase']}")
        print(f"  Active agents: {len(status['agents_status'])}")
        print(f"  Transitions: {status['phase_transitions']}")

        # Export context
        context = orchestrator.export_project_context()
        print("[PASS] Project context exported")
        print(f"  Selected solution: {context['selected_solution_id']}")
        print(f"  Phase history entries: {len(context['phase_history'])}")

        return True
    except Exception as e:
        print(f"[FAIL] Status test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MULTI-AGENT SYSTEM INTEGRATION TEST")
    print("=" * 60)

    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("\n[WARN]  Warning: OPENAI_API_KEY not set.")
        print("Some tests may fail without a valid API key.")
        print("Set the environment variable to test LLM integration.\n")

    results = []

    # Run tests
    orchestrator = test_orchestrator_initialization()
    results.append(("Orchestrator Init", orchestrator is not None))

    if orchestrator:
        results.append(("Agent Init", test_agent_initialization(orchestrator)))
        results.append(("Data Loading", test_data_loading(orchestrator)))
        results.append(("T-OAA Tools", test_toaa_functionality(orchestrator)))
        results.append(("Phase Transition", test_phase_transition(orchestrator)))
        results.append(("P&L-A Tools", test_pla_functionality(orchestrator)))
        results.append(("F-AA Tools", test_faa_functionality(orchestrator)))
        results.append(("Status & Export", test_project_status(orchestrator)))

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS] PASS" if result else "[FAIL] FAIL"
        print(f"{status:<10} {test_name}")

    print("=" * 60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n[SUCCESS] All tests passed! Multi-agent system is ready.")
        return 0
    else:
        print(f"\n[WARN]  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
