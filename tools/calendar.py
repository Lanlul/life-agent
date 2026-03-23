import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

load_dotenv()

def get_calendar_service():
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = service_account.Credentials.from_service_account_file(
        'credentials.json', scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

@tool
def query_schedule(start_date, end_date):
    """
    查詢一段日期範圍內的行事曆行程。
    start_date與end_date必須是'YYYY-MM-DD'格式(例如 '2026-03-23')。
    若只要查詢單日(例如今天)，請將start_date與end_date設為同一天。
    """
    try:
        service = get_calendar_service()
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')

        time_min = f'{start_date}T00:00:00+08:00'
        time_max = f'{end_date}T23:59:59+08:00'

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if not events:
            return f'{start_date}到{end_date}目前沒有任何行程。'
        
        schedule_list = [f'{start_date}到{end_date}的行程清單：']
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            if 'T' in start:
                date_part = start.split('T')[0][5:]
                time_part = start.split('T')[1][:5]
                schedule_list.append(f'- [{date_part} {time_part}] : {event['summary']}')
            else:
                date_part = start[5:]
                schedule_list.append(f'- [{date_part} 全天] : {event['summary']}')

        return '\n'.join(schedule_list)
        
    except Exception as e:
        return f'讀取行事曆失敗，錯誤訊息：{str(e)}'


@tool
def add_schedule(title, start_time, end_time, force=False):
    """
    新增行程到Google行事曆。
    start_time和end_time必須是標準的ISO 8601格式字串(包含時區)，例如：'2026-03-22T15:00:00+08:00'。
    若force為False，遇到時間衝突時會回報錯誤；若force為True，則無視衝突強制寫入。
    """
    try:
        service = get_calendar_service()
        calendar_id = os.getenv('GOOGLE_CALENDAR_ID')

        if not force:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True
            ).execute()
            events = events_result.get('items', [])

            if events:
                conflict_titles = ', '.join([e['summary'] for e in events])
                return f'⚠️發現行程衝突！該時段已經有行程：【{conflict_titles}】。請主動詢問使用者是否要強制重疊排入？(若使用者同意，請將force設為True重新呼叫此工具)'

        event = {
            'summary': title,
            'start': {'dateTime': start_time, 'timeZone': 'Asia/Taipei'},
            'end': {'dateTime': end_time, 'timeZone': 'Asia/Taipei'}, 
        }
        event = service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f'\n[行事曆日誌] 成功寫入行程：{title} ({start_time} ~ {end_time})\n')
        return f'行程已成功加入行事曆：{title}。請回復使用者已順利排程。'

    except Exception as e:
        return f'寫入行事曆失敗，錯誤訊息：{str(e)}'