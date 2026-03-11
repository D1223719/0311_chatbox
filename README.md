# AI chatbot 機器人

## 第三組

### 組員：
* D1223719黃國傑
* D1245806楊永蘭
* D1245587蔡秉倫
* D1150271辛晴
* D1150313薛帆凱
  
## 專案簡介

本專案是一個使用 **Chainlit** 製作的 AI 聊天機器人 Web 應用，搭配 **LangChain** 串接 **Google Gemini 2.0 Flash** 模型。除了基本的多輪文字對話與記憶功能外，還支援**圖片 (JPG/PNG)**、**PDF** 及**純文字檔 (.txt)** 的上傳與分析，實現多模態互動體驗。對話歷史會自動儲存為 JSON 檔案。

## 目前功能

- ✅ 多輪對話記憶（LangChain `ChatMessageHistory`）
- ✅ 圖片上傳分析（base64 編碼 → Gemini 多模態 API）
- ✅ PDF 上傳分析（`PyPDFLoader` 擷取文字）
- ✅ 純文字檔上傳分析（直接讀取內容）
- ✅ 對話紀錄自動存檔為 JSON（`chat_YYYYMMDD_HHMMSS.json`）
- ✅ API 429 Rate Limit 自動重試機制（指數退避，最多 3 次）
- ✅ 終端機版本（`chat.py`）與 Web 版本（`app.py`）雙介面

## 執行方式

### 下載專案

```bash
git clone https://github.com/D1223719/chatbox.git
cd chatbox
```

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 啟動 Web 介面（Chainlit）

```bash
chainlit run app.py
```

啟動後瀏覽器開啟 http://localhost:8000 即可使用。

### 啟動終端機介面

```bash
python chat.py
```

## 環境變數說明

請自行建立 `.env` 檔案，並填入自己的 API Key。

範例：

```
GOOGLE_API_KEY=AIzaSyCzihQ0E4W7EPl9vgdwwLYp2G0J_2Jkeyk
```

API Key 可至 [Google AI Studio](https://aistudio.google.com/apikey) 免費申請。

## 遇到的問題與解法

### 問題 1

**問題：** 安裝 Chainlit 後執行 `import chainlit` 出現 `ImportError: cannot import name 'cygrpc' from 'grpc._cython'`。

**解法：** 這是 `grpcio` 套件版本不相容造成的。透過 `pip install --force-reinstall grpcio grpcio-tools` 強制重新安裝最新版 grpcio 即可解決。

### 問題 2

**問題：** 呼叫 Gemini API 時出現 `429 RESOURCE_EXHAUSTED` 錯誤，提示免費額度已用盡（`limit: 0`）。

**解法：** 在程式中加入 `invoke_with_retry` 自動重試機制，遇到 429 錯誤時會以指數退避方式（16s → 32s → 64s）自動重試最多 3 次，並在聊天介面顯示倒數提示。若為每日額度用盡，則需等待隔日重置或至 Google AI Studio 重新申請 API Key。

## 學習心得

本次作業讓我學習到如何使用 LangChain 框架串接 Google Gemini 2.0 Flash 大型語言模型，並透過 Chainlit 快速建構出具有專業感的 Web 聊天介面。在多模態處理方面，我學會了如何將圖片以 base64 編碼傳送給 Gemini 的 Vision API，以及使用 PyPDFLoader 擷取 PDF 文字內容。過程中也深刻體會到 API 配額管理的重要性，因此加入了自動重試機制來提升使用者體驗。整體而言，從終端機版本到 Web 版本的演進過程，讓我對 AI 應用開發的完整流程有了更全面的認識。

## GitHub 專案連結
* 楊永蘭: https://github.com/D1245806/AIagent.git
* 蔡秉倫: https://github.com/Ping-Lun/chat-bot.git
* 辛晴: https://github.com/xinching0524/chatrobot.git
* 薛帆凱: https://github.com/sailboat0116/chatbot.git
