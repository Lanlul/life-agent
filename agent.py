import os
from dotenv import load_dotenv
import pytz
from datetime import datetime
from typing import Annotated
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

from tools import tools

#載入金鑰
load_dotenv()

#LangGraph agent大腦
#定義狀態(保存對話紀錄)
class State(TypedDict):
    messages: Annotated[list, add_messages]

#初始化LLM並綁定工具
llm = ChatOpenAI(model='gpt-3.5-turbo', base_url = os.getenv('BASE_URL'), temperature=0)
llm_with_tools = llm.bind_tools(tools)

#定義Agent思考節點
async def chatbot_node(state):
    tz = pytz.timezone('Asia/Taipei')
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %A")

    system_prompt = f"""
    你是一個全能理財與時程助理。
    現在的台灣時間是 {current_time}。
    請根據此時間基準來推算使用者提到的「明天」、「下週」等相對時間。
    如果需要呼叫行事曆工具，請務必自行推算並轉換為ISO 8601格式(需包含+08:00時區)。
    如果使用者沒有提供結束時間，請預設行程長度為1小時。
    如果使用者記帳沒有提供金額或項目，請不要瞎猜，必須中斷工具呼叫並主動反問使用者。
    """

    messages_to_llm = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages_to_llm)
    return {'messages': [response]}

#組合狀態機圖表
builder = StateGraph(State)
builder.add_node('agent', chatbot_node)
builder.add_node('tools', ToolNode(tools=tools))

#設定邏輯流向
builder.add_edge(START, 'agent')
builder.add_conditional_edges('agent', tools_condition)
builder.add_edge('tools', 'agent')

memory = MemorySaver()
agent_app = builder.compile(checkpointer=memory)