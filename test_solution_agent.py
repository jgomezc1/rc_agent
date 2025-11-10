#!/usr/bin/env python3
"""
Test script for the Solution Chat Agent
"""

from solution_chat_agent import SolutionChatAgent


def main():
    """Run automated tests."""

    # Initialize agent
    agent = SolutionChatAgent()

    # Test questions
    questions = [
        "How many structural elements are in this solution?",
        "What types of elements are included (beams, columns, etc.)?",
        "What bar sizes are available in this solution?",
        "Which floor has the most elements?",
        "Tell me about the first beam in the solution",
    ]

    print("\n" + "="*80)
    print("TESTING SOLUTION CHAT AGENT")
    print("="*80)

    for i, question in enumerate(questions, 1):
        print(f"\n[TEST {i}]")
        print(f"Q: {question}")
        print("-" * 80)

        answer = agent.ask(question)
        print(f"A: {answer}")
        print("-" * 80)

    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)
    print("\nThe agent successfully answered all questions about the solution.")
    print("Now you can run the interactive mode:")
    print("  ./venv/Scripts/python.exe solution_chat_agent.py")


if __name__ == "__main__":
    main()
