"""
Gemini 2.0 Flash 聊天室 — Chainlit Web 介面
支援圖片 (JPG/PNG)、PDF、純文字檔 (.txt) 上傳與多輪對話
"""

import asyncio
import base64
import json
import mimetypes
import os
import re
from datetime import datetime

import chainlit as cl
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# ── 載入環境變數 ──────────────────────────────────────────────
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("請在 .env 中設定 GOOGLE_API_KEY")

# ── 支援的檔案類型 ────────────────────────────────────────────
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {".txt"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS | TEXT_EXTENSIONS


# ── 檔案處理函式 ──────────────────────────────────────────────
def process_image(file_path: str, user_text: str):
    """讀取圖片並建構多模態 HumanMessage content (list)。"""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = f"image/{ext.lstrip('.')}"

    with open(file_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    return [
        {"type": "text", "text": user_text or "請描述這張圖片"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
        },
    ]


def process_pdf(file_path: str, user_text: str) -> str:
    """使用 PyPDFLoader 擷取 PDF 文字，組成帶 context 的提示。"""
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    full_text = "\n".join(page.page_content for page in pages)

    if not full_text.strip():
        return f"{user_text or '請分析這份文件'}\n\n[PDF 檔案無法擷取文字內容]"

    return (
        f"以下是 PDF 文件的完整內容：\n"
        f"---\n{full_text}\n---\n\n"
        f"{user_text or '請摘要這份文件'}"
    )


def process_text_file(file_path: str, user_text: str) -> str:
    """讀取純文字檔，組成帶 context 的提示。"""
    with open(file_path, "r", encoding="utf-8") as f:
        file_content = f.read()

    return (
        f"以下是文字檔案的完整內容：\n"
        f"---\n{file_content}\n---\n\n"
        f"{user_text or '請摘要這份文字'}"
    )


# ── 對話紀錄輔助 ──────────────────────────────────────────────
def add_to_log(role: str, content, file_info: dict | None = None) -> None:
    """將訊息同時記錄到 chat_history (LangChain) 和 chat_log (JSON)。"""
    chat_history: list = cl.user_session.get("chat_history")
    chat_log: list = cl.user_session.get("chat_log")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # LangChain 訊息
    if role == "user":
        chat_history.append(HumanMessage(content=content))
    else:
        chat_history.append(AIMessage(content=content))

    # JSON 紀錄
    log_entry: dict = {
        "timestamp": timestamp,
        "role": role,
        "content": content if isinstance(content, str) else "[多模態訊息]",
    }
    if file_info:
        log_entry["file"] = file_info

    chat_log.append(log_entry)


def save_conversation() -> str | None:
    """將 chat_log 儲存為 JSON 檔案。"""
    chat_log: list = cl.user_session.get("chat_log")
    if not chat_log:
        return None

    filename = datetime.now().strftime("chat_%Y%m%d_%H%M%S.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(chat_log, f, ensure_ascii=False, indent=2)
    return filename


async def invoke_with_retry(llm, chat_history, max_retries: int = 3):
    """呼叫 LLM，遇到 429 自動重試（含倒數提示）。"""
    base_wait = 16  # 起始等待秒數

    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(chat_history)
            return response.content
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str

            if not is_rate_limit or attempt >= max_retries:
                raise

            # 從錯誤訊息中擷取建議等待秒數
            wait_seconds = base_wait * (2 ** attempt)
            match = re.search(r"retry in ([\d.]+)s", error_str, re.IGNORECASE)
            if match:
                wait_seconds = max(int(float(match.group(1))) + 1, wait_seconds)

            # 發送倒數提示
            countdown_msg = cl.Message(
                content=(
                    f"⏳ API 配額已達上限（第 {attempt + 1}/{max_retries} 次重試）\n\n"
                    f"等待 **{wait_seconds} 秒**後自動重試..."
                )
            )
            await countdown_msg.send()
            await asyncio.sleep(wait_seconds)
            await countdown_msg.remove()


# ── Chainlit 生命週期 ─────────────────────────────────────────
@cl.on_chat_start
async def on_chat_start():
    """初始化 LLM 和對話紀錄。"""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
    )
    cl.user_session.set("llm", llm)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("chat_log", [])

    await cl.Message(
        content=(
            "👋 **歡迎使用 Gemini 2.0 Flash 聊天室！**\n\n"
            "你可以：\n"
            "- 直接輸入文字進行對話\n"
            "- 點擊 📎 按鈕上傳**圖片 (JPG/PNG)**、**PDF** 或**純文字檔 (.txt)**\n\n"
            "AI 會自動分析檔案內容並回答你的問題。"
        )
    ).send()


@cl.on_message
async def on_message(msg: cl.Message):
    """處理使用者訊息（含附件）。"""
    llm: ChatGoogleGenerativeAI = cl.user_session.get("llm")
    user_text = msg.content.strip()

    # ── 處理附件 ──────────────────────────────────────────────
    if msg.elements:
        for element in msg.elements:
            file_path = element.path
            file_name = element.name
            ext = os.path.splitext(file_name)[1].lower()

            # 檢查檔案類型
            if ext not in SUPPORTED_EXTENSIONS:
                await cl.Message(
                    content=(
                        f"⚠️ 不支援的檔案格式：**{ext}**\n\n"
                        f"目前支援：JPG、PNG、PDF、TXT"
                    )
                ).send()
                continue

            # 處理中提示
            processing_msg = cl.Message(content=f"📂 正在處理 **{file_name}** ...")
            await processing_msg.send()

            file_info = {"path": file_name, "type": ""}

            try:
                if ext in IMAGE_EXTENSIONS:
                    file_info["type"] = "image"
                    content = process_image(file_path, user_text)
                elif ext in PDF_EXTENSIONS:
                    file_info["type"] = "pdf"
                    content = process_pdf(file_path, user_text)
                elif ext in TEXT_EXTENSIONS:
                    file_info["type"] = "text"
                    content = process_text_file(file_path, user_text)
            except Exception as e:
                await cl.Message(
                    content=f"❌ 處理檔案時發生錯誤：{e}"
                ).send()
                continue

            # 記錄使用者訊息
            add_to_log("user", content, file_info=file_info)

            # 呼叫 LLM（含自動重試）
            try:
                chat_history = cl.user_session.get("chat_history")
                ai_text = await invoke_with_retry(llm, chat_history)
            except Exception as e:
                ai_text = f"❌ 呼叫模型時發生錯誤：{e}"

            # 記錄 AI 回應
            add_to_log("ai", ai_text)

            # 移除處理中提示，發送正式回覆
            await processing_msg.remove()
            await cl.Message(content=ai_text).send()

        return  # 附件已處理完畢

    # ── 純文字對話 ────────────────────────────────────────────
    if not user_text:
        return

    add_to_log("user", user_text)

    try:
        chat_history = cl.user_session.get("chat_history")
        ai_text = await invoke_with_retry(llm, chat_history)
    except Exception as e:
        ai_text = f"❌ 呼叫模型時發生錯誤：{e}"

    add_to_log("ai", ai_text)
    await cl.Message(content=ai_text).send()


@cl.on_chat_end
async def on_chat_end():
    """對話結束時自動儲存紀錄。"""
    saved = save_conversation()
    if saved:
        print(f"對話紀錄已儲存至: {saved}")
