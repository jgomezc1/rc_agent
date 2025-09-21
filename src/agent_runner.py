from memory import load_shop_drawings
from reasoning import choose_strategy
from planning import build_plan
from action import evaluate_steel, evaluate_manhours, evaluate_cost, print_report
from reflection import needs_replan


def run_agent():
    # Step 1: Choose optimization strategy
    strategy = choose_strategy("minimize cost")  # Default strategy
    print(f"Strategy selected: {strategy}")

    # Step 2: Plan sequence
    steps = build_plan(strategy)
    print(f"Planned steps: {steps}")

    # Step 3: Execute plan
    shop_drawings = load_shop_drawings()

    if strategy == "minimize_steel":
        sorted_options = evaluate_steel(shop_drawings)
    elif strategy == "minimize_manhours":
        sorted_options = evaluate_manhours(shop_drawings)
    elif strategy == "minimize_cost":
        sorted_options = evaluate_cost(shop_drawings)
    else:
        sorted_options = evaluate_cost(shop_drawings)  # Default fallback

    # Step 4: Report results
    print(print_report(sorted_options[0]))

    # Step 5: Reflect
    top = sorted_options[0]
    needs_replan_result = needs_replan(top)
    print(f"Needs replanning: {needs_replan_result}")


if __name__ == "__main__":
    run_agent()
