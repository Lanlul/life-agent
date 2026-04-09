# 🤖 Life Agent: 個人智能助理

這是一個基於 **LangGraph** 與 **LangChain** 開發的智慧個人助手，並整合至 **Discord** 平台。它能協助你管理日常開支、安排 Google 行事曆，甚至能搜尋學術論文並進行 RAG（檢索增強生成）摘要分析。

---

## 🌟 核心功能

### 💰 智慧理財管理 (SQLite 整合)
* **自動記帳**：支援「餐飲、交通、購物、娛樂、居住、醫療、其他」七大類別。
* **視覺化報表**：可產生日報表、月報表或總表，並自動繪製 **Matplotlib 圓餅圖** 回傳至 Discord。
* **彈性操作**：支援即時修改金額或刪除當日的記帳紀錄。

### 📅 Google 行事曆同步
* **行程查詢**：查詢指定日期範圍內的行程清單。
* **衝突偵測**：新增行程時若發現時間重疊，會主動詢問使用者是否強制寫入。
* **自動化排程**：自動將自然語言描述轉化為 ISO 8601 格式進行排程。

### 🎓 學術論文助手 (RAG)
* **自動搜尋與下載**：對接 OpenAlex API，根據關鍵字搜尋並自動下載開放獲取 (OA) 論文。
* **智慧摘要分析**：利用 **FAISS** 向量資料庫與 **HuggingFace Embeddings** 進行全文分析或細節問答。
* **中文在地化**：自動將搜尋結果的標題翻譯成繁體中文。

### 🧠 智慧對話管理 (LangGraph)
* **記憶清理機制**：具備 `filter_history_node`，會自動刪除冗長的搜尋結果與拋棄式 RAG 訊息，確保 token 使用效率並維持對話品質。
* **多工切換**：能夠在理財、行事曆與學術工具間自動判定使用者意圖並進行呼叫。

---

## 🛠️ 技術棧
* **LLM 框架**: LangChain, LangGraph
* **主要模型**: OpenAI `gpt-4o-mini` (主邏輯), `gpt-3.5-turbo` (RAG 專用)
* **資料庫**: SQLite (財務), FAISS (向量檢索)
* **外部 API**: Discord.py, Google Calendar API, OpenAlex API

---

## 🚀 安裝與設定

### 1. 複製專案
```bash
git clone <your-repo-url>
cd life-agent-master
```

### 2. 安裝依賴環境
```bash
pip install -r requirements.txt
```

### 3. 環境變數設定(`.env`)
在根目錄建立 `.env` 檔案，並填入以下資訊：
```bash
DISCORD_TOKEN=你的Discord機器人Token
OPENAI_API_KEY=你的OpenAI密鑰
BASE_URL=OpenAI的API起點 (選填)
GOOGLE_CALENDAR_ID=你的Google行事曆ID (通常是你的Gmail地址)
```
### 4.憑證準備
請將 Google Cloud Console 下載的 Service Account 憑證重新命名為 `credentials.json` 並放置於根目錄。

確保該 Service Account 已具備存取該 Google 行事曆 的權限。

## 📂 檔案結構
* `main.py`: Discord 機器人入口點，負責處理訊息傳遞。
* `agent.py`: 定義 LangGraph 狀態機、對話邏輯與記憶過濾機制。
* `tools/`: 工具集模組
    * `money.py`: 理財資料庫操作與圖表生成。
    * `calendar.py`: Google 行事曆操作介面。
    * `research.py`: 論文搜尋、下載與 RAG 分析邏輯。
* `papers/`: 下載論文 PDF 的預設儲存路徑。
* `expenses.db`: 自動生成的 SQLite 財務資料庫。

## ⚠️ 使用須知
* **類別限制**：記帳功能嚴格限制只能使用指定七大類別，未指定時機器人會自動分類。
* **記憶清理**：系統會保留最近約 15 則訊息，並過濾掉已標記為 `[DISPOSABLE]` 或 `[SEARCH_RESULT]` 的過期資訊。
* **圖表字體**：生成圓餅圖時，系統會嘗試使用常見中文字體（如 Microsoft JhengHei），請確保運行環境已安裝相關字體。