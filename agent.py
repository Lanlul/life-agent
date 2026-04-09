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

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]

llm = ChatOpenAI(model='gpt-4o-mini', base_url = os.getenv('BASE_URL'), temperature=0)
llm_with_tools = llm.bind_tools(tools)

async def filter_history_node(state: State):
    messages = state["messages"]
    if len(messages) < 2: 
        return {"messages": []}

    delete_ids = []
    search_indices = []
    rag_indices = []
    
    for i, msg in enumerate(messages):
        content_str = str(msg.content)
        if "[DISPOSABLE]" in content_str or getattr(msg, "name", "") == "paper_assistant_rag":
            rag_indices.append(i)
        if "[SEARCH_RESULT]" in content_str:
            search_indices.append(i)

    for idx in rag_indices:
        if idx < len(messages) - 1:
            delete_ids.append(messages[idx].id)
            if idx > 0 and messages[idx-1].type == "ai":
                delete_ids.append(messages[idx-1].id)

    if len(search_indices) > 1:
        for idx in search_indices[:-1]:
            delete_ids.append(messages[idx].id)
            if idx > 0 and messages[idx-1].type == "ai":
                delete_ids.append(messages[idx-1].id)

    MAX_BUFFER = 15
    current_active = [m for m in messages if m.id not in delete_ids]
    
    if len(current_active) > MAX_BUFFER:
        excess = len(current_active) - MAX_BUFFER
        count = 0
        
        for i, m in enumerate(messages):
            if count >= excess: break
            
            if m.id in delete_ids or "[SEARCH_RESULT]" in str(m.content) or m.type == "system":
                continue

            if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
                delete_ids.append(m.id)
                count += 1
                if i + 1 < len(messages) and messages[i+1].type == "tool":
                    delete_ids.append(messages[i+1].id)
                    count += 1
            else:
                delete_ids.append(m.id)
                count += 1

    final_delete_ids = list(set(delete_ids))
    if messages[-1].type == "ai" and messages[-1].id in final_delete_ids:
        final_delete_ids.remove(messages[-1].id)

    if final_delete_ids:
        print(f"🔥 預計刪除訊息 ID: {final_delete_ids}")
    else:
        print("✅ 無需清理，目前記憶狀態良好。")
    
    print('=' * 20)
    deleted = []
    for message in messages:
        if message.id not in final_delete_ids:
            print(message.content[:30] if message.type != 'tool' else 'tool')
        else:
            deleted.append(message)
    print('-' * 20)
    print('delete')
    for message in deleted:
        print(message.content[:30] if message.type != 'tool' else 'tool')
    for m in messages:
        if m.type == 'system':
            print('yes')
    print('=' * 20)

    return {"messages": [RemoveMessage(id=m_id) for m_id in final_delete_ids]}

async def chatbot_node(state):
    tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(tz)
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %A")
    today_date = now.strftime("%Y-%m-%d")

    start_of_week = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    end_of_week = (now + timedelta(days=6 - now.weekday())).strftime("%Y-%m-%d")
    
    system_prompt = f"""
    你是一個全能理財與學術助手。時間：{current_time}。
    - 今天：{today_date} | 本週：{start_of_week}~{end_of_week}。
    - 記帳：限「過去/現在」。無金額則反問。類別限：['餐飲', '交通', '購物', '娛樂', '居住', '醫療', '其他']。
    - 排程：未來事件一律呼叫 add_schedule。
    - 搜尋：翻譯關鍵字為英文。
    - 摘要：若使用者說「摘要第幾篇」，請從歷史 [SEARCH_RESULT] 找到對應「伺服器路徑」傳給 paper_assistant_rag。
    """

    messages_to_llm = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages_to_llm)
    return {'messages': [response]}


builder = StateGraph(State)
builder.add_node('agent', chatbot_node)
builder.add_node('tools', ToolNode(tools=tools))
builder.add_node('filter', filter_history_node)

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