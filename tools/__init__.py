from tools.money import record_expense, generate_expense_report, update_today_expense, delete_today_expense
from tools.calendar import add_schedule, query_schedule
from tools.research import search_and_download_papers, paper_assistant_rag
tools = [record_expense, generate_expense_report, add_schedule, query_schedule, update_today_expense, delete_today_expense, search_and_download_papers, paper_assistant_rag]
