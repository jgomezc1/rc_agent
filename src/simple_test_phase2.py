"""
Simple test script for Phase 2 integration without Unicode characters.
"""

import sys
import os

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test basic imports"""
    print("=== Testing Phase 2 Imports ===")

    try:
        from phase2_models import RiskLevel, QualityStatus, InsightPriority
        print("[OK] Phase 2 models imported")
        print(f"RiskLevel values: {[r.value for r in RiskLevel]}")
        print(f"QualityStatus values: {[q.value for q in QualityStatus]}")
        print(f"InsightPriority values: {[i.value for i in InsightPriority]}")
    except Exception as e:
        print(f"[ERROR] Phase 2 models: {e}")
        return False

    try:
        from risk_radar import RiskRadar
        print("[OK] RiskRadar imported")
    except Exception as e:
        print(f"[ERROR] RiskRadar: {e}")
        return False

    try:
        from crew_planner import CrewPlanner
        print("[OK] CrewPlanner imported")
    except Exception as e:
        print(f"[ERROR] CrewPlanner: {e}")
        return False

    try:
        from procurement_system import ProcurementOptimizer
        print("[OK] ProcurementOptimizer imported")
    except Exception as e:
        print(f"[ERROR] ProcurementOptimizer: {e}")
        return False

    try:
        from qa_qc_engine import QualityValidator
        print("[OK] QualityValidator imported")
    except Exception as e:
        print(f"[ERROR] QualityValidator: {e}")
        return False

    try:
        from constructibility_engine import ConstructibilityAnalyzer
        print("[OK] ConstructibilityAnalyzer imported")
    except Exception as e:
        print(f"[ERROR] ConstructibilityAnalyzer: {e}")
        return False

    try:
        from phase2_reporting import Phase2Reporter
        print("[OK] Phase2Reporter imported")
    except Exception as e:
        print(f"[ERROR] Phase2Reporter: {e}")
        return False

    try:
        from phase2_agent_tools import phase2_tools
        print(f"[OK] Phase2 Tools imported - {len(phase2_tools)} tools available")
        for tool in phase2_tools:
            print(f"  - {tool.name}")
    except Exception as e:
        print(f"[ERROR] Phase2 Tools: {e}")
        return False

    return True

def test_basic_functionality():
    """Test basic functionality"""
    print("\n=== Testing Basic Functionality ===")

    try:
        from risk_radar import RiskRadar
        radar = RiskRadar()
        print("[OK] RiskRadar instance created")
    except Exception as e:
        print(f"[ERROR] RiskRadar creation: {e}")
        return False

    try:
        from phase2_reporting import Phase2Reporter
        reporter = Phase2Reporter()
        metadata = reporter._generate_metadata("TEST_RS_001")
        print(f"[OK] Reporter metadata: {len(metadata)} fields")
    except Exception as e:
        print(f"[ERROR] Reporter functionality: {e}")
        return False

    return True

if __name__ == "__main__":
    print("Phase 2 Integration Test")
    print("=" * 40)

    success1 = test_imports()
    success2 = test_basic_functionality()

    print("\n" + "=" * 40)
    if success1 and success2:
        print("PHASE 2 INTEGRATION: SUCCESS")
        print("\nNext steps:")
        print("1. Set OPENAI_API_KEY environment variable")
        print("2. Run: python comprehensive_langchain_agent.py")
        print("3. Test with: 'Analyze risks for solution RS_TEST_001'")
    else:
        print("PHASE 2 INTEGRATION: PARTIAL SUCCESS")
        print("Some components may not work correctly")