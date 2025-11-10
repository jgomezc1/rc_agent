#!/usr/bin/env python3
"""
Complete test of all 4 integrated file generation capabilities
Tests yard layout, crane safety, unloading schedule, and zone allocation
"""

from logistics_agent import LogisticsAgent


def main():
    """Test all file generation integration."""

    print("="*80)
    print("COMPLETE FILE GENERATION TEST")
    print("="*80)

    # Initialize agent
    print("\nInitializing agent...")
    agent = LogisticsAgent()

    # Test prompts that should trigger each file type
    test_prompts = [
        "Create a yard layout for the project site",
        "Generate crane safety guidelines for the team",
        "I need an unloading schedule for tomorrow's deliveries",
        "Show me the zone allocation plan for the bundles",
        "I need all logistics documents: yard layout, safety guidelines, unloading schedule, and zone allocation"
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print("\n" + "="*80)
        print(f"TEST {i}: {prompt}")
        print("="*80)

        answer = agent.ask(prompt)
        print(answer)
        print("-"*80)

    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)
    print("\nCheck the logistics_outputs/ folder for generated files:")
    print("- Yard Layout PDFs")
    print("- Crane Safety PDFs")
    print("- Unloading Schedule Excel files")
    print("- Zone Allocation PDFs")


if __name__ == "__main__":
    main()
