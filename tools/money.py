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
    """將使用者的花費紀錄到資料庫中。必須包含項目(item)、金額(amount)與類別(category)。"""
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
def generate_expense_report():
    """當使用者想看花費報表、花費比例、圓餅圖，呼叫此工具。"""
    try:
        conn = sqlite3.connect('expenses.db')
        c = conn.cursor()
        c.execute('SELECT category, SUM(amount) FROM expenses GROUP BY category')
        data = c.fetchall()
        conn.close()

        if not data:
            return '目前資料庫沒有任何記帳紀錄，無法生成圖表。請使用者先記幾筆帳。'
        
        categories = [
            row[0]
            for row in data
        ]
        amounts = [
            row[1]
            for row in data
        ]

        plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Microsoft JhengHei', 'PingFang HK', 'SemHei']
        plt.rcParams['axes.unicode_minus'] = False

        plt.figure(figsize=(6, 6))
        plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=140)
        plt.title('個人消費類別比例圖')

        plt.savefig('chart.png')
        plt.close()

        return '圖表已成功生成並儲存為chart.png。'
    
    except Exception as e:
        return f'生成圖表失敗，錯誤訊息：{{str(e)}}'
