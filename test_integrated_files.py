#!/usr/bin/env python3
"""
Test integrated file generation in Logistics Agent
"""

from logistics_agent import LogisticsAgent


def main():
    """Test file generation integration."""

    print("="*80)
    print("TESTING INTEGRATED FILE GENERATION")
    print("="*80)

    # Initialize agent
    print("\nInitializing agent...")
    agent = LogisticsAgent()

    # Test prompts that should trigger file generation
    test_prompts = [
        "Create a yard layout for the project site",
        "Generate crane safety guidelines for the team",
        "I need both a yard layout and safety guidelines",
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print("\n" + "="*80)
        print(f"TEST {i}: {prompt}")
        print("="*80)

        answer = agent.ask(prompt)
        print(answer)
        print("-"*80)

    print("\n" + "="*80)
    print("CHECK THE logistics_outputs/ FOLDER FOR GENERATED FILES")
    print("="*80)


if __name__ == "__main__":
    main()
