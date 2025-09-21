from langchain.agents import initialize_agent, Tool
from langchain.chat_models import ChatOpenAI
from langchain.agents.agent_types import AgentType
from agent_tools import list_rs, filter_rs, top_n_rs, print_report_tool

tools = [
    Tool.from_function(list_rs, name="list_rs", description="List all RS IDs"),
    Tool.from_function(filter_rs, name="filter_rs", description="Filter RS by criteria"),
    Tool.from_function(top_n_rs, name="top_n_rs", description="Get top N RSs by metric"),
    Tool.from_function(print_report_tool, name="print_report", description="Generate summary report"),
]

system_msg = (
    "TOOLS\n"
    "======\n"
    "You have exactly four tools. You must call them using JSON syntax only.\n"
    "Each tool accepts **either** of these signatures:\n"
    "  • A single argument named *input* (a JSON-encoded string)\n"
    "  • Multiple named arguments (metric=…, where=…, n=…)\n\n"
    "Correct examples:\n"
    '  {"name":"list_rs","args":{"input":""}}\n'
    '  {"name":"filter_rs","args":{"where":"Manhours < 560"}}\n'
    '  {"name":"top_n_rs","args":{"metric":"Cost_total","n":3}}\n'
    '  {"name":"print_report","args":{"input":"{...}"}}\n\n'
    "⚠️ You must wrap tool names and arguments in double quotes. Do not write Python code. Only return valid JSON."
)

llm = ChatOpenAI(temperature=0)

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={"system_message": system_msg}
)

if __name__ == "__main__":
    print("🧠  Reinforcement‑Solution selector. Type 'exit' to quit.\n")
    while True:
        user_prompt = input("🗣  > ")
        if user_prompt.strip().lower() == "exit":
            break
        try:
            result = agent.invoke({"input": user_prompt})
            print(result["output"])
        except Exception as e:
            print("❌", e)