"""
Gemini 2.0 Flash 聊天程式（多模態版）
支援圖片 (JPG/PNG)、PDF、純文字檔 (.txt) 輸入
使用 langchain-google-genai 搭配對話記憶與 JSON 持久化
"""

import base64
import json
import mimetypes
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# ── 載入環境變數 ──────────────────────────────────────────────
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("請在 .env 中設定 GOOGLE_API_KEY")

# ── 初始化模型 ────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=api_key,
)

# ── 支援的檔案類型 ────────────────────────────────────────────
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {".txt"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS | TEXT_EXTENSIONS

# ── 對話紀錄 ──────────────────────────────────────────────────
chat_history: list = []          # LangChain Message 物件
chat_log: list[dict] = []        # 用於 JSON 匯出的紀錄


def add_message(
    role: str,
    content,
    file_info: dict | None = None,
) -> None:
    """同時記錄到 chat_history 與 chat_log。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if role == "user":
        chat_history.append(HumanMessage(content=content))
    else:
        chat_history.append(AIMessage(content=content))

    # chat_log 只存文字摘要
    log_entry: dict = {
        "timestamp": timestamp,
        "role": role,
        "content": content if isinstance(content, str) else "[多模態訊息]",
    }
    if file_info:
        log_entry["file"] = file_info

    chat_log.append(log_entry)


def save_conversation() -> str | None:
    """將對話紀錄存為 JSON 檔案，回傳檔名。"""
    if not chat_log:
        return None

    filename = datetime.now().strftime("chat_%Y%m%d_%H%M%S.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(chat_log, f, ensure_ascii=False, indent=2)
    return filename


# ── 檔案處理 ──────────────────────────────────────────────────
def process_image(file_path: str, user_text: str):
    """讀取圖片並建構多模態 HumanMessage content。"""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = f"image/{ext.lstrip('.')}"

    with open(file_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    content = [
        {"type": "text", "text": user_text or "請描述這張圖片"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
        },
    ]
    return content


def process_pdf(file_path: str, user_text: str) -> str:
    """使用 PyPDFLoader 擷取 PDF 文字，組成帶 context 的提示。"""
    from langchain_community.document_loaders import PyPDFLoader

    loader = PyPDFLoader(file_path)
    pages = loader.load()
    full_text = "\n".join(page.page_content for page in pages)

    if not full_text.strip():
        return f"{user_text or '請分析這份文件'}\n\n[PDF 檔案無法擷取文字內容]"

    prompt = (
        f"以下是 PDF 文件的完整內容：\n"
        f"---\n{full_text}\n---\n\n"
        f"{user_text or '請摘要這份文件'}"
    )
    return prompt


def process_text_file(file_path: str, user_text: str) -> str:
    """讀取純文字檔，組成帶 context 的提示。"""
    with open(file_path, "r", encoding="utf-8") as f:
        file_content = f.read()

    prompt = (
        f"以下是文字檔案的完整內容：\n"
        f"---\n{file_content}\n---\n\n"
        f"{user_text or '請摘要這份文字'}"
    )
    return prompt


def handle_file_command(raw_input: str):
    """
    解析 /file 指令，回傳 (content, file_info) 或 (error_string, None)。
    格式: /file <路徑> [問題]
    """
    parts = raw_input[len("/file"):].strip()
    if not parts:
        return "請提供檔案路徑，格式：/file <路徑> [問題]", None

    # 解析路徑與問題文字
    # 支援帶空格的路徑（用引號包起來）
    if parts.startswith('"'):
        end_quote = parts.find('"', 1)
        if end_quote == -1:
            file_path = parts[1:]
            user_text = ""
        else:
            file_path = parts[1:end_quote]
            user_text = parts[end_quote + 1:].strip()
    else:
        tokens = parts.split(maxsplit=1)
        file_path = tokens[0]
        user_text = tokens[1] if len(tokens) > 1 else ""

    # 驗證檔案
    if not os.path.isfile(file_path):
        return f"[錯誤] 找不到檔案：{file_path}", None

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return (
            f"[錯誤] 不支援的檔案類型：{ext}\n"
            f"支援的格式：JPG, PNG, PDF, TXT"
        ), None

    # 依類型處理
    file_info = {"path": file_path, "type": ""}

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
        else:
            return f"[錯誤] 不支援的檔案類型：{ext}", None
    except Exception as e:
        return f"[錯誤] 處理檔案時發生問題：{e}", None

    return content, file_info


# ── 主程式 ────────────────────────────────────────────────────
def main() -> None:
    print("=" * 55)
    print("  Gemini 2.0 Flash 聊天室（多模態版）")
    print("  ─────────────────────────────────")
    print("  指令說明：")
    print("    直接輸入文字 → 純文字對話")
    print("    /file <路徑> [問題] → 傳送檔案")
    print("      支援格式：JPG, PNG, PDF, TXT")
    print("    exit → 結束對話並儲存紀錄")
    print("=" * 55)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            break

        # ── 判斷是否為檔案指令 ────────────────────────────────
        if user_input.lower().startswith("/file "):
            content, file_info = handle_file_command(user_input)

            if file_info is None:
                # 錯誤訊息，直接顯示不加入對話歷史
                print(f"\n{content}")
                continue

            # 記錄使用者訊息（含檔案）
            add_message("user", content, file_info=file_info)
        else:
            # 純文字對話
            content = user_input
            add_message("user", content)

        # 呼叫模型（傳入完整對話歷史）
        try:
            response = llm.invoke(chat_history)
            ai_text = response.content
        except Exception as e:
            ai_text = f"[錯誤] {e}"

        # 記錄 AI 回應
        add_message("ai", ai_text)
        print(f"\nAI: {ai_text}")

    # ── 儲存對話 ──────────────────────────────────────────────
    saved = save_conversation()
    if saved:
        print(f"\n對話紀錄已儲存至: {saved}")
    else:
        print("\n沒有對話紀錄需要儲存。")


if __name__ == "__main__":
    main()
