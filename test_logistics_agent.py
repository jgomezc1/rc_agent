#!/usr/bin/env python3
"""
Test the ProDet+StructuBIM Logistics Agent
"""

from logistics_agent import LogisticsAgent


def main():
    """Test the agent with sample prompts."""

    print("\n" + "="*80)
    print("TESTING LOGISTICS AGENT")
    print("="*80)

    # Initialize agent
    agent = LogisticsAgent()

    # Test prompts from the specification
    test_prompts = [
        "Which elements on Floor 3 are hardest to install?",
        "Create an installation sequence for Floor 5",
        "What's the total steel weight for floors 5-10?",
        "Generate a task card outline for element V-7",
        "If bundle B-112 is missing, what's the impact?",
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {prompt}")
        print("="*80)

        answer = agent.ask(prompt)
        print(answer)
        print("-"*80)

    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)
    print("\nThe logistics agent is ready!")
    print("Run: ./venv/Scripts/python.exe logistics_agent.py")


if __name__ == "__main__":
    main()
