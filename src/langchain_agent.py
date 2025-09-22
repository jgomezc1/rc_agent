from langchain.agents import initialize_agent
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType
import os
from dotenv import load_dotenv
from agent_tools import list_rs, filter_rs, top_n_rs, print_report_tool

load_dotenv()

tools = [list_rs, filter_rs, top_n_rs, print_report_tool]

system_msg = (
    "You are a helpful assistant for analyzing reinforcement solution (RS) data.\n"
    "You have access to these tools:\n"
    "- list_rs: Lists all RS IDs (no parameters needed)\n"
    "- filter_rs: Filters RS data by conditions (parameter: where)\n"
    "- top_n_rs: Gets top N RSs by metric (parameters: metric, n)\n"
    "- print_report_tool: Generates report for RS data (parameter: rs_json)\n\n"
    "Always use the tools to answer questions about the RS data."
)

llm = ChatOpenAI(temperature=0)

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={"system_message": system_msg}
)

if __name__ == "__main__":
    print("Reinforcement-Solution selector. Type 'exit' to quit.\n")
    while True:
        user_prompt = input("> ")
        if user_prompt.strip().lower() == "exit":
            break
        try:
            result = agent.invoke({"input": user_prompt})
            print(result["output"])
        except Exception as e:
            print("Error:", e)