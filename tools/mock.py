from langchain_core.tools import tool

#定義假工具
@tool
def mock_record_expense(item, amount, category):
    """將使用者的花費紀錄到資料庫中。必須包含項目(item)、金額(amount)與類別(category)。"""
    print(f'\n[系統日誌]觸發工具! 準備記帳 -> 項目:{item}, 金額:{amount}, 類別:{category}')
    return f'系統已成功在背景將「{item} ({amount}元)」分類為「{category}」並記錄。'

tools = [mock_record_expense]