from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from langdetect import detect
from googletrans import Translator
import re 
import time

is_cold_start = True

app = Flask(__name__)

line_bot_api = LineBotApi('DNiG14dlnuM+Y0+7io452MX3+7xyQJM/RpAB/h26baFZgCnVNO9GTIwaiCY19lD/zNJVlcJIMaCu4kTEGbJrJnzorqBlrh/QjBh8C/aTh0Y9OGh+oEklAFQO7Ct1EH3pR42w0tu44py0G/qD5TxJZgdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('7ae43c5b1e96b1ab6746c02e73385e0b')

# LibreTranslate 翻譯函式
translator = Translator()

def extract_mentions(text):
    mentions = re.findall(r"@[\w\W]{1,8}", text)

    # 若有提及者，只去除第一個 mention，視為「開頭提及」
    pure_text = text
    if mentions and text.startswith(mentions[0]):
        pure_text = text[len(mentions[0]):].strip()
    else:
        pure_text = text

    return mentions, pure_text


# 修正 langdetect 的語言代碼，避免 googletrans 無法辨識
def normalize_lang_code(code):
    if code.startswith("zh"):
        return "zh-cn"  # Google 翻譯接受 zh-cn（簡中）或 zh-tw（繁中），但建議統一 zh-cn
    if code == "jw":  # 有些版本會誤判印尼語為 jw（Javanese）
        return "id"
    return code

def translate(text, target_lang, source_lang="auto"):
    from googletrans import Translator
    translator = Translator()

    source_lang = normalize_lang_code(source_lang)
    target_lang = normalize_lang_code(target_lang)

    try:
        result = translator.translate(text, src=source_lang, dest=target_lang)
        print(f"✅ 翻譯成功：{text} → {result.text}")
        return result.text
    except Exception as e:
        print("⚠️ 翻譯錯誤：", e)
        return "⚠️ 翻譯失敗，請稍後再試"


# 判斷是否為「主要為中文字」的句子
def is_mostly_chinese(text):
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars) / max(len(text), 1) > 0.5

def auto_translate(text):
    try:
        # 提取純文字（不含提及）
        mentions, pure_text = extract_mentions(text)

        # 改善語言偵測：保留標點與語意符號，只過濾 emoji（Unicode 大於 U+FFFF 的範圍）
        clean_text = re.sub(r"[\U00010000-\U0010ffff]", "", pure_text).strip()

        # 避免空字串送進 detect
        # 特殊情境：文字太短但在已知詞彙中
        # 特殊情境：文字太短但在已知詞彙中
        short_fallback = {
            # 印尼語常見短語
            "iya": "id",
            "tidak": "id",
            "makasih": "id",
            "terima kasih": "id",
            "ok": "id",
            "oke": "id",
            "nggak": "id",
            "enggak": "id",
            "sip": "id",
            "siap": "id",
            "yoi": "id",
            "yuk": "id",
            "ayo": "id",
            "mantap": "id",
        
            # 中文常見短語
            "好": "zh",
            "是": "zh",
            "對": "zh",
            "沒錯": "zh",
            "沒問題": "zh",
            "謝謝": "zh",
            "感謝": "zh",
            "了解": "zh",
            "知道了": "zh",
            "可以": "zh",
            "行": "zh"
        }

        
        if len(clean_text.strip()) < 2:
            # 試著用 fallback 字詞對應語言
            lowers = clean_text.lower()
            if lowers in short_fallback:
                lang = short_fallback[lowers]
            else:
                return "⚠️ 翻譯錯誤：內容太短，無法進行語言辨識"


        lang = detect(clean_text)
        print("語言偵測結果（純文字）:", lang)

        # 中文比例高 → 強制 zh
        if is_mostly_chinese(clean_text) or any(word in clean_text for word in ["訊息", "你", "什麼", "吃", "今天"]):
            lang = "zh"
        elif any(word in clean_text.lower() for word in ["makan", "apa", "anda", "mengerti", "iya", "tidak"]):
            lang = "id"

        # 語言標準化
        if "zh" in lang:
            lang = "zh"
        elif lang == "jw" or "id" in lang:
            lang = "id"

        # 翻譯流程
        if lang == "zh":
            eng = translate(pure_text, "en", "zh")
            idn = translate(eng, "id", "en")
            return f"🧑‍🏫 原文（中文）：\n{' '.join(mentions)} {pure_text}\n\n🌐 印尼語翻譯：\n{' '.join(mentions)} {idn}"
        elif lang == "id":
            eng = translate(pure_text, "en", "id")
            zh = translate(eng, "zh", "en")
            return f"🧑‍🏫 原文（印尼語）：\n{' '.join(mentions)} {pure_text}\n\n🌐 中文翻譯：\n{' '.join(mentions)} {zh}"
        else:
            return f"⚠️ 暫不支援此語言（偵測為：{lang}）"

    except Exception as e:
        return f"⚠️ 翻譯錯誤：{str(e)}"


# LINE callback入口
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@app.route("/", methods=['GET'])
def home():
    return "Line Translator Bot is running!"

# 處理文字訊息事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global is_cold_start
    user_text = event.message.text
    reply_text = auto_translate(user_text)

    # 如果是第一次啟動，先回「啟動中」訊息，然後再正常翻譯
    if is_cold_start: 
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="⚡ 系統剛啟動，可能需要幾秒熱機，請稍候...\n⚡ Sistem baru saja dimulai, mungkin perlu beberapa detik untuk memanas, harap tunggu ..."
            )
        )
        is_cold_start = False
        # 0.5秒後再送出真正翻譯訊息
        time.sleep(0.1)
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text=reply_text)
        )

    else:
        # 非第一次直接回應
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # 讀取 Render 自動給的 PORT 或預設 5000
    app.run(host='0.0.0.0', port=port)


