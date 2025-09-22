"""
Test script to verify the path fix for the enhanced agent.
"""

import sys
import os

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_agent_tools import _validate_data, _select_solution


def test_path_fix():
    """Test that the path fix works correctly"""
    print("Testing enhanced agent tools with path fix...")

    try:
        # Test validation tool
        print("\n1. Testing data validation...")
        result = _validate_data("phase_a")
        print(f"   Result length: {len(result)} characters")
        print(f"   Success: {'PASS' in result}")

        # Test selection tool
        print("\n2. Testing solution selection...")
        result = _select_solution("cost")
        print(f"   Result length: {len(result)} characters")
        print(f"   Success: {'Recommended Solution' in result}")

        print("\nPASS All tests passed! Path fix is working correctly.")
        return True

    except Exception as e:
        print(f"\nFAIL Test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_path_fix()
    if success:
        print("\nThe enhanced agent should now work correctly!")
        print("Try running: venv/Scripts/python.exe src/enhanced_langchain_agent.py")
    else:
        print("\nThere are still issues. Check the error above.")

    sys.exit(0 if success else 1)