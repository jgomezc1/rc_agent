"""Quick verification that the path fix works"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_agent_tools import _validate_data

# Test validation output
result = _validate_data('phase_a')
print("Validation result:")
print(result)
print(f"\nLength: {len(result)} characters")
print(f"Contains 'Valid': {'Valid' in result}")
print(f"Contains 'PASS': {'PASS' in result}")