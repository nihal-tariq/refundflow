import asyncio
from dotenv import load_dotenv
load_dotenv(".env")
from app.config import get_settings
from app.services.llm_providers import build_chat_model
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

@tool
def dummy_tool(x: int) -> int:
    """Returns x + 1."""
    return x + 1

async def main():
    llm = build_chat_model(get_settings())
    agent = create_react_agent(llm, tools=[dummy_tool])
    result = await agent.ainvoke({"messages": [("user", "What is 5 + 1? Use the tool.")]})
    print(result["messages"][-1].content)

asyncio.run(main())
