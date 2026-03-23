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
    你是一個全能理財與時程助理。現在的台灣時間是 {current_time}。
    請嚴格遵守以下規則來決定你的行動：

    【規則 1：意圖判斷與缺漏反問 (超級重要！)】
    - 💰 記帳意圖：只要使用者提到「買、吃、花、繳費」或具體的【消費物品】(例如：午餐、飲料、衣服)，這就是「記帳」。
      👉 情況 A (資料齊全)：如果有提到具體金額，請立刻呼叫 record_expense。
      👉 情況 B (資料缺漏)：如果【沒有提到金額】，🚨絕對不可以呼叫 add_schedule，也絕對不可以自己瞎猜數字！請直接放棄呼叫任何工具，並用自然語言反問使用者：「請問這個花了多少錢呢？」

    - 📅 排程意圖：如果使用者提到的是「未來的待辦、提醒、開會、搶票、出門」，且【沒有提到具體花費與消費物品】，才屬於排程，請呼叫 add_schedule。

    【規則 2：時間推算】
    - 請根據當前時間基準來推算「明天」、「下週」等相對時間，並轉換為 ISO 8601 格式 (需包含 +08:00 時區)。
    - 若排程未提供結束時間，預設長度為 1 小時。

    【規則 3：行程報告與不摘要原則】
    - 當你呼叫 query_schedule 查詢行程後，請務必「一字不漏、完整列出」工具回傳的所有行程細節。
    - 🚨 絕對禁止擅自省略、總結或摘要行程！使用者需要看到最完整的時間與事件清單。
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