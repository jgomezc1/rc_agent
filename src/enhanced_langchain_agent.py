"""
Enhanced LangChain agent for RC Agent Phase 1 implementation.
Replaces the original agent with advanced decision-support capabilities.
"""

from langchain.agents import initialize_agent
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType
import os
from dotenv import load_dotenv
from enhanced_agent_tools import (
    select_solution,
    analyze_pareto_frontier,
    perform_sensitivity_analysis,
    validate_data,
    generate_detailed_report,
    what_if_analysis
)

load_dotenv()

# Enhanced tools with Phase 1 capabilities
tools = [
    select_solution,
    analyze_pareto_frontier,
    perform_sensitivity_analysis,
    validate_data,
    generate_detailed_report,
    what_if_analysis
]

system_msg = """
You are an advanced AI assistant specialized in reinforced concrete construction decision support.
You have access to powerful optimization and analysis tools for Phase 1 implementation.

## Your Capabilities:

### 🎯 **Solution Selection & Optimization**
- **select_solution**: Find optimal solutions using multi-objective optimization
- **analyze_pareto_frontier**: Identify Pareto-optimal trade-offs across objectives

### 📊 **Analysis & Risk Assessment**
- **perform_sensitivity_analysis**: Test robustness to parameter changes
- **what_if_analysis**: Evaluate scenarios with multiple parameter changes

### 📋 **Reporting & Validation**
- **generate_detailed_report**: Create comprehensive solution reports
- **validate_data**: Check data integrity and consistency

## Data Sources:
- **Phase A**: shop_drawings.json (10 solution scenarios with cost/performance summaries)
- **Phase B**: shop_drawings_structuBIM.json (detailed BIM data for execution planning)

## Key Objectives You Can Optimize For:
- **cost**: Minimize total project cost
- **co2**: Minimize CO₂ emissions
- **duration**: Minimize project duration
- **manhours**: Minimize labor requirements
- **constructibility**: Maximize ease of construction

## Example Usage Patterns:

**Basic Selection:**
"Find the most cost-effective solution"
→ Use select_solution with objective="cost"

**Multi-Objective Analysis:**
"What are the best trade-offs between cost and environmental impact?"
→ Use analyze_pareto_frontier with objectives=["cost", "co2"]

**Risk Assessment:**
"How sensitive is the ranking to steel price changes?"
→ Use perform_sensitivity_analysis with parameter="steel_cost"

**Scenario Planning:**
"What if steel costs increase 20% and duration constraints tighten?"
→ Use what_if_analysis with appropriate parameters

**Always provide actionable insights and clear recommendations based on your analysis.**
"""

llm = ChatOpenAI(temperature=0, model="gpt-4")

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={"system_message": system_msg}
)

if __name__ == "__main__":
    print("RC Agent Phase 1 - Advanced Construction Decision Support")
    print("Available capabilities: optimization, Pareto analysis, sensitivity testing, reporting")
    print("Type 'exit' to quit.\n")

    # Show quick start examples
    print("Quick Start Examples:")
    print("- 'Find the most cost-effective solution'")
    print("- 'What are the best trade-offs between cost and CO2?'")
    print("- 'Analyze sensitivity to steel price changes'")
    print("- 'Generate a detailed report for the best solution'")
    print("- 'Validate the data integrity'")
    print("-" * 60)

    while True:
        user_prompt = input("\n> ")
        if user_prompt.strip().lower() == "exit":
            break
        try:
            result = agent.invoke({"input": user_prompt})
            print("\n" + result["output"])
        except Exception as e:
            print(f"\nError: {e}")
            print("Try rephrasing your request or check the available commands above.")