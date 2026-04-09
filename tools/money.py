import sqlite3
from datetime import datetime
from langchain_core.tools import tool
import matplotlib.pyplot as plt
import os

def init_db():
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              date TEXT NOT NULL,
              item TEXT NOT NULL,
              amount INTEGER NOT NULL,
              category TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print('✅ SQLite 資料庫檢查/建立完成！')

init_db()

@tool
def record_expense(item, amount, category):
    """
    將使用者的花費紀錄到資料庫中。必須包含項目(item)、金額(amount)與類別(category)。
    
    【類別限制警告】：
    category 參數【嚴格】只能從以下 7 個選項中挑選一個填入：
    ['餐飲', '交通', '購物', '娛樂', '居住', '醫療', '其他']
    
    如果使用者沒有特別指定類別，請根據 item (例如：午餐->餐飲，高鐵->交通) 自行分類到上述七個類別之一。
    【絕對不允許】你自己發明這 7 個以外的新類別！
    """
    try:
        conn = sqlite3.connect('expenses.db')
        c = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")

        c.execute('''
            INSERT INTO expenses (date, item, amount, category)
            VALUES(?, ?, ?, ?)
        ''', (today, item, amount, category))

        conn.commit()
        conn.close()

        print(f'\n[資料庫日誌] 成功寫入一筆資料:{today} | {item} | ${amount} | {category}\n')
        return f'資料庫已成功寫入：項目為{item}，金額為{amount}，類別為{category}。'
    
    except Exception as e:
        return f'寫入資料庫失敗，錯誤訊息：{str(e)}'

@tool
def generate_expense_report(report_type='all', target_date=''):
    """
    當使用者想看花費報表、花費比例、圓餅圖時呼叫此工具。
    支援三種報表類型(report_type)：
    1.'daily'(日報表):必須提供target_date，格式為'YYYY-MM-DD'(例如'2026-03-23')。
    2.'monthly'(月報表):必須提供target_date，格式為'YYYY-MM'(例如'2026-03')。
    3.'all'(總報表):不需要提供target_date。
    """
    try:
        conn = sqlite3.connect('expenses.db')
        c = conn.cursor()

        if report_type == 'daily':
            query = 'SELECT category, SUM(amount) FROM expenses WHERE date = ? GROUP BY category'
            params = (target_date, )
            title = f'{target_date}個人消費比例圖(日報表)'
        elif report_type == 'monthly':
            query = 'SELECT category, SUM(amount) FROM expenses WHERE date LIKE ? GROUP BY category'
            params = (f'{target_date}-%', )
            title = f'{target_date}個人消費比例圖(月報表)'
        else:
            query = 'SELECT category, SUM(amount) FROM expenses GROUP BY category'
            params = ()
            title = '歷史總消費比例圖'
        
        c.execute(query, params)
        data = c.fetchall()
        conn.close()

        if not data:
            return f'找不到{target_date}的記帳紀錄，無法生成圖表。請告訴使用者目前沒有資料。'
        
        categories = [
            row[0]
            for row in data
        ]
        amounts = [
            row[1]
            for row in data
        ]

        total_amount = sum(amounts)
        labels_with_amount = [f'{cat}\n(${amt})' for cat, amt in zip(categories, amounts)]
        full_title = f'{title}\n總計花費：${total_amount}'
        plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Microsoft JhengHei', 'PingFang HK', 'SemHei']
        plt.rcParams['axes.unicode_minus'] = False

        plt.figure(figsize=(7, 7))
        plt.pie(amounts, labels=labels_with_amount, autopct='%1.1f%%', startangle=140)
        plt.title(full_title, fontsize=14, fontweight='bold', pad=20)

        plt.savefig('chart.png', bbox_inches='tight')
        plt.close()

        return f'圖表已成功生成({title})並儲存為chart.png。請回覆使用者已產出報表。'
    
    except Exception as e:
        return f'生成圖表失敗，錯誤訊息：{{str(e)}}'

@tool
def update_today_expense(item, new_amount):
    """
    當使用者想要「修改」今天已經記下的某筆花費金額時呼叫此工具。
    例如：「我剛剛午餐記錯了，改成120元」。
    必須提供要修改的項目名稱(item)與新的金額(new_amount)。
    """
    try:
        conn = sqlite3.connect('expenses.db')
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        c.execute('SELECT id, amount FROM expenses WHERE date = ? AND item = ?', (today, item))
        record = c.fetchone()

        if not record:
            conn.close()
            return f'找不到今天關於「{item}」的記帳紀錄，請確認項目名稱是否正確。'
        
        c.execute('UPDATE expenses SET amount = ? WHERE date = ? AND item = ?', (new_amount, today, item))
        conn.commit()
        conn.close()

        print(f'\n[資料庫日誌]成功修改資料：今日的{item}金額已更新為${new_amount}\n')
        return f'已成功將今天「{item}」的金額修改為{new_amount}元！'

    except Exception as e:
        return f'修改資料庫失敗，錯誤訊息：{str(e)}'
    
@tool
def delete_today_expense(item):
    """
    當使用者想要「刪除/取消」今天已經記下的某筆花費時呼叫此工具。
    例如：「幫我刪除剛剛記的午餐」、「午餐那筆不要記了」。
    必須提供要刪除的項目名稱(item)。
    """
    try:
        conn = sqlite3.connect('expenses.db')
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        c.execute('SELECT id FROM expenses WHERE date = ? AND item = ?', (today, item))
        record = c.fetchone()

        if not record:
            conn.close()
            return f'找不到今天關於「{item}」的記帳紀錄，無法刪除。'
        
        c.execute('DELETE FROM expenses WHERE date = ? AND item = ?', (today, item))
        conn.commit()
        conn.close()

        print(f'\n[資料庫日誌]成功刪除資料：已移除今日的{item}\n')
        return f'已成功刪除今天「{item}」的記帳紀錄！'
    
    except Exception as e:
        return f'刪除資料失敗，錯誤訊息：{str(e)}'
