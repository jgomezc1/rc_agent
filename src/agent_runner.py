from memory import load_shop_drawings
from reasoning import choose_optimization_strategy
from planning import plan_evaluation_steps
from action import evaluate_steel_usage, evaluate_manpower, print_report
from reflection import reflect_on_result


def run_agent():
    # Step 1: Choose optimization strategy
    strategy = choose_optimization_strategy()
    print(f"🤖 Strategy selected: {strategy}")

    # Step 2: Plan sequence
    steps = plan_evaluation_steps(strategy)
    print(f"🧠 Planned steps: {steps}")

    # Step 3: Execute plan
    shop_drawings = load_shop_drawings()
    
    if strategy == "minimize_material":
        sorted_options = evaluate_steel_usage(shop_drawings)
    elif strategy == "minimize_manpower":
        sorted_options = evaluate_manpower(shop_drawings)
    else:
        raise ValueError("Unknown strategy")

    # Step 4: Report results
    print_report(sorted_options, strategy)

    # Step 5: Reflect
    top = sorted_options[0]
    reflection = reflect_on_result(top, strategy)
    print(reflection)


if __name__ == "__main__":
    run_agent()
