import os
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

load_dotenv()

if not os.path.exists('papers'):
    os.makedirs('papers')

@tool
def search_and_download_papers(query, max_results=5):
    """
    使用者需要尋找、查詢或下載「學術論文」時呼叫此工具。
    query 必須是英文學術關鍵字。工具會下載 PDF 並回傳包含 [SEARCH_RESULT] 標籤的清單。
    """
    url = 'https://api.openalex.org/works'
    data = {
        'search': query,
        'filter': 'is_oa:true,primary_location.source.id:https://openalex.org/S4306400194,has_pdf_url:true',
        'sort': 'relevance_score:desc',
        'per-page': max_results
    }
    response = requests.get(url, data)
    results = response.json()
    results = results['results']
    results_text = [f'[SEARCH_RESULT] 關於「{query}」的搜尋清單：']
    for i, result in enumerate(results):
        title = result['title']
        pdf_url = result['best_oa_location']['pdf_url']
        
        
        safe_title = ''.join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        filename = f'./papers/{safe_title[:40]}.pdf'

        response = requests.get(pdf_url)
        with open(filename, 'wb') as file:
            file.write(response.content)

        results_text.append(f'**[{i}] {title}**')
        results_text.append(f'🔗線上觀看:{pdf_url}')
        results_text.append(f'📂伺服器檔案路徑: `{filename}`\n')

    return '\n'.join(results_text) + '\n\n請將以上論文標題翻譯成繁體中文，並回傳標題、線上連結給使用者。'

@tool
def paper_assistant_rag(filepath, user_goal):
    """
    當使用者想要「摘要整篇論文」或「詢問特定細節」時呼叫此工具。
    filepath: 伺服器上的檔案路徑。
    user_goal: 使用者的意圖。
    """
    try:
        if not os.path.exists(filepath):
            return f'找不到檔案：{filepath}。請確認檔名是否正確，或請使用者先執行搜尋下載。'

        loader = PyPDFLoader(filepath)
        docs = loader.load()
        print('test')

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=150)
        splits = text_splitter.split_documents(docs)

        embeddings = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
        vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)

        relevant_docs = vectorstore.as_retriever(search_kwargs={'k': 5}).invoke(user_goal)
        context = '\n\n---\n\n'.join([doc.page_content for doc in relevant_docs])
        summary_llm = ChatOpenAI(model='gpt-3.5-turbo', base_url = os.getenv('BASE_URL'), temperature=0)
        prompt = f'你是一個專業學術助手。請根據以下論文內容，用繁體中文回答：「{user_goal}」。\n\n內容：\n{context}'
        final_answer = summary_llm.invoke(prompt)

        return f'[DISPOSABLE] 論文分析回答：\n{final_answer.content}'
    
    except Exception as e:
        return f'RAG系統執行失敗，錯誤訊息：{str(e)}'