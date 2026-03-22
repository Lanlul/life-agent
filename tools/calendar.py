import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

load_dotenv()

@tool
def add_schedule(title, start_time, end_time):
    """
    新增行程到Google行事曆。
    start_time和end_time必須是標準的ISO 8601格式字串(包含時區)，
    例如：'2026-03-22T15:00:00+08:00'。
    """
    try:
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = service_account.Credentials.from_service_account_file(
            'credentials.json', scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')

        event = {
            'summary': title,
            'start': {'dateTime': start_time, 'time_Zone': 'Asia/Taipei'},
            'end': {'dateTime': end_time, 'timeZone': 'Asia/Taipei'}, 
        }
        event = service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f'\n[日立日誌] 成功寫入行程：{title} ({start_time} ~ {end_time})\n')
        return f'行程已成功加入行事曆：{title}。請回復使用者已順利排程。'

    except Exception as e:
        return f'寫入行事曆失敗，錯誤訊息：{str(e)}'