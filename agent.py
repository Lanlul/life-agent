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
from langchain_core.messages import RemoveMessage
from tools import tools

#載入金鑰
load_dotenv()

#LangGraph agent大腦
#定義狀態(保存對話紀錄)
class State(TypedDict):
    messages: Annotated[list, add_messages]

#初始化LLM並綁定工具
llm = ChatOpenAI(model='gpt-4o-mini', base_url = os.getenv('BASE_URL'), temperature=0)
llm_with_tools = llm.bind_tools(tools)

async def filter_history_node(state: State):
    messages = state["messages"]
    if len(messages) < 2:
        return {"messages": []}

    delete_ids = []
    
    # 👑 核心錨點：找出「最新一次 User 提問」的索引位置
    # 這能幫我們精準判斷哪些工具是「上一輪」的，哪些是「本輪」的
    last_user_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "human":
            last_user_idx = i
            break

    # 分類收集兩種工具的索引位置
    search_tool_indices = []
    rag_tool_indices = []

    for i, msg in enumerate(messages):
        if msg.type == "tool":
            # 透過工具名稱精準辨識 (也可以保留你原本判斷 [DISPOSABLE] 的寫法)
            if getattr(msg, "name", "") == "search_and_download_papers":
                search_tool_indices.append(i)
            elif getattr(msg, "name", "") == "paper_assistant_rag" or "[DISPOSABLE]" in str(msg.content):
                rag_tool_indices.append(i)

    # =========================================================
    # 🚀 策略一：search_and_download_papers (用到下一次才覆蓋)
    # =========================================================
    # 如果歷史紀錄中有 2 次以上的找論文紀錄，我們只保留「最後一次 (最新的)」
    if len(search_tool_indices) > 0:
        # search_tool_indices[:-1] 代表「除了最後一個以外的所有舊紀錄」
        for idx in search_tool_indices[:-1]:
            delete_ids.append(messages[idx].id) # 刪除舊的 ToolMessage
            
            # 對稱刪除：呼叫舊搜尋的 AI 指令
            if idx > 0 and messages[idx-1].type == "ai":
                delete_ids.append(messages[idx-1].id)
                
            # 對稱刪除：AI 針對舊搜尋所做的回覆清單
            if idx < len(messages) - 1 and messages[idx+1].type == "ai":
                delete_ids.append(messages[idx+1].id)

    # =========================================================
    # 🔥 策略二：paper_assistant_rag (下一個 prompt 輸入時馬上刪除)
    # =========================================================
    for idx in rag_tool_indices:
        # 判斷關鍵：如果這個 RAG 紀錄的位置 < 最新 User 提問的位置
        # 代表它是「上一輪」的產物，必須馬上被燒毀！
        if idx < last_user_idx:
            delete_ids.append(messages[idx].id) # 刪除舊的 RAG 結果
            
            # 對稱刪除：呼叫舊 RAG 的 AI 指令
            if idx > 0 and messages[idx-1].type == "ai":
                delete_ids.append(messages[idx-1].id)
            
            # 對稱刪除：AI 針對舊 RAG 所做的摘要回覆
            if idx < len(messages) - 1 and messages[idx+1].type == "ai":
                # 確保這個回覆也是在新的 User 提問之前
                if (idx + 1) < last_user_idx:
                    delete_ids.append(messages[idx+1].id)

    # 去除重複的 ID，避免 LangGraph 報錯
    unique_delete_ids = list(set(delete_ids))

    return {"messages": [RemoveMessage(id=m_id) for m_id in unique_delete_ids]}

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
    
    【規則 5：學術研究助理 (RAG 版)】
    - 📚 搜尋論文：當使用者想找論文時，呼叫 search_and_download_papers (請將中文關鍵字翻譯為精準的英文學術詞彙)。取得資料後，請列出標題、線上連結與伺服器檔案路徑。
    - 📖 論文摘要與問答：
      👉 無論使用者是要求「摘要整篇」還是「詢問特定細節」，🚨統一呼叫 paper_assistant_rag。
      👉 若要求摘要，請將 user_goal 設為「請摘要這篇論文的研究動機、核心貢獻、實驗方法與數據集、實驗結果與結論」。
      👉 若詢問細節，請將 user_goal 設為使用者的具體問題。
      👉 回覆時請保持專業，使用繁體中文，且排版清晰易讀。
    """

    messages_to_llm = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages_to_llm)
    return {'messages': [response]}

#組合狀態機圖表
builder = StateGraph(State)
builder.add_node('agent', chatbot_node)
builder.add_node('tools', ToolNode(tools=tools))
builder.add_node('filter', filter_history_node)

#設定邏輯流向
builder.add_edge(START, 'filter')
builder.add_edge('filter', 'agent')
builder.add_conditional_edges(
    'agent', 
    tools_condition, 
    {
        "tools": "tools", 
        END: END 
    }
)
builder.add_edge('tools', 'filter')
builder.add_edge('filter', 'agent')

memory = MemorySaver()
agent_app = builder.compile(checkpointer=memory)

# TODO 把找論文過濾加入filter，並在最後加入filter節點