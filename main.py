from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import re
import time
from langdetect import detect
from googletrans import Translator

is_cold_start = True
app = Flask(__name__)

line_bot_api = LineBotApi('<你的Channel Access Token>')
handler = WebhookHandler('<你的Channel Secret>')

def normalize_lang_code(code):
    if code.startswith("zh"):
        return "zh-cn"
    if code == "jw":
        return "id"
    return code

def translate(text, target_lang, source_lang="auto"):
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

def is_mostly_chinese(text):
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars) / max(len(text), 1) > 0.5

def extract_mentions(text):
    mentions = re.findall(r'@\S+', text)
    content = re.sub(r'@\S+', '', text).strip()
    return mentions, content

def auto_translate(text):
    try:
        mentions, pure_text = extract_mentions(text)
        clean_text = re.sub(r"[，。！？、,.!?！：:]", "", pure_text)
        lang = detect(clean_text)
        print("語言偵測結果（初步）：", lang)

        if text.strip().lower() == "halo":
            lang = "id"
        if any(word in text for word in ["吃", "什麼", "今天", "你", "記得", "衣服", "收"]):
            lang = 'zh'
        elif any(word in text.lower() for word in ["apa", "makan", "suci", "kamu"]):
            lang = 'id'
        if is_mostly_chinese(text):
            lang = 'zh'
        if re.match(r"^\d{1,2}點$", text.strip()):
            lang = 'zh'
        if re.search(r'[\u4e00-\u9fff]', text) and re.search(r'[a-zA-Z]', text):
            lang = 'zh'

        if 'zh' in lang:
            lang = 'zh'
        elif lang == 'jw' or 'id' in lang:
            lang = 'id'

        if lang == 'zh':
            eng = translate(pure_text, 'en', 'zh')
            idn = translate(eng, 'id', 'en')
            return f"🧑‍🏫 原文（中文）：\n{' '.join(mentions)} {pure_text}\n\n🌐 印尼語翻譯：\n{' '.join(mentions)} {idn}"
        elif lang == 'id':
            eng = translate(pure_text, 'en', 'id')
            zh = translate(eng, 'zh', 'en')
            return f"🧑‍🏫 原文（印尼語）：\n{' '.join(mentions)} {pure_text}\n\n🌐 中文翻譯：\n{' '.join(mentions)} {zh}"
        else:
            return f"⚠️ 暫不支援此語言（偵測為：{lang}）"
    except Exception as e:
        return f"⚠️ 翻譯錯誤：{str(e)}"

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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global is_cold_start
    user_text = event.message.text
    reply_text = auto_translate(user_text)
    if is_cold_start:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="⚡ 系統剛啟動，可能需要幾秒熱機，請稍候...\n⚡ Sistem baru saja dimulai, mungkin perlu beberapa detik untuk memanas, harap tunggu ..."
            )
        )
        is_cold_start = False
        time.sleep(0.5)
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text=reply_text)
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
