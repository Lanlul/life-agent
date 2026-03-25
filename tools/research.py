import os
import time
import arxiv
import random
from langchain_core.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

if not os.path.exists('papers'):
    os.makedirs('papers')

@tool
def search_and_download_papers(query, max_results=5):
    """
    當使用者需要尋找、查詢或下載「學術論文」時呼叫此工具。
    query 必須是【英文】的學術關鍵字（例如："3D tooth semantic instance segmentation"）。
    此工具會自動去 ArXiv 資料庫搜尋最新且相關的論文，下載 PDF 到伺服器，並回傳論文資訊、連結與檔案路徑。
    """
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        results_text = [f'找到關於「{query}」的Top{max_results}論文，已全數下載至伺服器：\n']

        for i, result in enumerate(client.results(search), 1):
            title = result.title
            published_date = result.published.strftime("%Y-%m-%d")
            pdf_url = result.pdf_url

            safe_title = ''.join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            filename = f'./papers/[{published_date}] {safe_title[:40]}.pdf'

            result.download_pdf(filename=filename)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f'[{i}/{max_results}]準備下載：{safe_title[:20]}...')
                    result.download_pdf(filename=filename)

                    sleep_time = random.uniform(8, 15)
                    print(f'✅ 下載成功！隨機冷卻 {sleep_time:.1f} 秒防封鎖 ⏳')
                    time.sleep(sleep_time)
                    break

                except Exception as e:
                    if '429' in str(e):
                        wait_time = (2 ** attempt) * 15
                        print(f'⚠️ 觸發 429 限制！退避等待 {wait_time} 秒後重試...')
                        time.sleep(wait_time)
                    else:
                        print(f'❌ 下載失敗，未知錯誤：{str(e)}')
                        break

            results_text.append(f'**[{i}] {title}**')
            results_text.append(f'🔗線上觀看:{pdf_url}')
            results_text.append(f'📂伺服器檔案路徑: `{filename}`\n')

        print(f'\n[學術日誌]成功下載{max_results}篇關於{query}的論文！\n')
        return '\n'.join(results_text) + '\n\n請將以上清單翻譯成繁體中文回覆給使用者，並告訴使用者：若想深入了解某篇論文，請告訴我檔案路徑或第幾篇，我之後可以幫忙閱讀並摘要。'
    
    except Exception as e:
        print(e)
        print()
        return f'搜尋或下載論文失敗，錯誤訊息：{str(e)}'
    
@tool
def paper_assistant_rag(filepath, user_goal):
    """
    當使用者想要「摘要整篇論文」、「了解核心貢獻」或「詢問特定細節」時呼叫此工具。
    filepath: 伺服器上的檔案路徑。
    user_goal: 使用者的意圖 (例如："這篇論文的摘要" 或 "實驗數據是多少？")。
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

        is_summary = any(word in user_goal for word in ["摘要", "重點", "總結", "summary"])
        k_value = 6 if is_summary else 3

        retriever = vectorstore.as_retriever(search_kwargs={'k': k_value})
        relevant_docs = retriever.invoke(user_goal)

        context = '\n\n---\n\n'.join([doc.page_content for doc in relevant_docs])
        print(f"[RAG 系統]已針對目標「{user_goal}」檢索了{len(relevant_docs)}個段落。")

        return f"[DISPOSABLE]請根據以下檢索到的內容，用專業繁體中文回覆「{user_goal}」：\n\n{context}"
    
    except Exception as e:
        return f'RAG系統執行失敗，錯誤訊息：{str(e)}'