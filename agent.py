import os
from dotenv import load_dotenv
import pytz
from datetime import datetime, timedelta
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
    now = datetime.now(tz)
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %A")
    today_date = now.strftime("%Y-%m-%d")

    start_of_week = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    end_of_week = (now + timedelta(days=6 - now.weekday())).strftime("%Y-%m-%d")
    
    system_prompt = f"""
    你是一個全能理財與時程助理。現在的台灣時間是 {current_time}。
    請嚴格遵守以下規則來決定你的行動：

    【規則 1：絕對時間參考座標 (嚴禁自己瞎算！)】
    - 今天日期：{today_date}
    - 本週範圍：{start_of_week} 到 {end_of_week} (週一至週日)
    當使用者查詢「今天」、「這禮拜」或「本週」的行程時，請【絕對照抄】上述的日期傳給工具。

    【規則 2：相對時間推算與格式區分 (重要！)】
    - 若使用者提到「明天」、「下週」等相對時間，請根據當前時間基準進行推算。
    - ⚠️ 工具格式限制：
      👉 呼叫 add_schedule (新增行程)：時間必須轉換為 ISO 8601 格式 (例如 2026-03-24T15:00:00+08:00)。若未提供結束時間，預設長度為 1 小時。
      👉 呼叫 query_schedule (查詢行程)：日期必須為 YYYY-MM-DD 格式 (例如 2026-03-24)，不可包含具體時間與時區。

    【規則 3：意圖判斷與缺漏反問 (超級重要！)】
    - 💰 記帳意圖：只要使用者提到「買、吃、花、繳費」或具體消費物品，且發生在【過去或現在】，即為「記帳」。
      👉 情況 A (資料齊全)：有提到具體金額，請立刻呼叫 record_expense (修改則呼叫 update_today_expense 等)。若使用者未提供「類別(category)」，請嚴格從【'餐飲', '交通', '購物', '娛樂', '居住', '醫療', '其他'】這 7 個類別中挑選最適合的一個，🚨絕對不允許你自己發明新類別！
      👉 情況 B (資料缺漏)：若【沒有提到金額】，🚨絕對不可呼叫工具，也不可自己瞎猜數字！請放棄呼叫，並用自然語言反問使用者：「請問這個花了多少錢呢？」

    - 📅 排程/查詢意圖：
      👉 若使用者提到「未來的待辦、提醒、開會、搶票」或「查詢行程」。
      👉 ⚠️ 即使句子包含金額與花費（例如：提醒我明天繳費 500 元），只要是發生在【未來】，皆屬於排程，請呼叫 add_schedule，不要記帳。

    - 📊 報表意圖：若要求「日報表」、「月報表」、「總報表」或畫圓餅圖，請呼叫 generate_expense_report。
      👉 日報表：report_type 設為 'daily'，target_date 提供 YYYY-MM-DD。
      👉 月報表：report_type 設為 'monthly'，從 today_date 擷取年月作為 target_date (YYYY-MM)。
      👉 總報表：report_type 設為 'all'。

    【規則 4：行程報告與不摘要原則】
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