from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
from langdetect import detect
from googletrans import Translator

app = Flask(__name__)

line_bot_api = LineBotApi('DNiG14dlnuM+Y0+7io452MX3+7xyQJM/RpAB/h26baFZgCnVNO9GTIwaiCY19lD/zNJVlcJIMaCu4kTEGbJrJnzorqBlrh/QjBh8C/aTh0Y9OGh+oEklAFQO7Ct1EH3pR42w0tu44py0G/qD5TxJZgdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('7ae43c5b1e96b1ab6746c02e73385e0b')

# LibreTranslate 翻譯函式
translator = Translator()

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



# 自動翻譯邏輯＋加上標籤
def auto_translate(text):
    lang = detect(text)
    print("🔍 偵測語言：", lang)

    # 語言代碼修正
    if lang.startswith('zh') or lang == 'yue' or lang == 'ko':
        lang = 'zh'
    elif lang == 'jw':
        lang = 'id'

    if lang == 'zh':
        eng = translate(text, 'en', 'zh')   # 中文 → 英文（不顯示）
        idn = translate(eng, 'id', 'en')    # 英文 → 印尼語（顯示）
        return f"🧑‍🏫 原文（中文）：\n{text}\n\n🌐 印尼語翻譯：\n{idn}"

    elif lang == 'id':
        eng = translate(text, 'en', 'id')   # 印尼語 → 英文（不顯示）
        zh = translate(eng, 'zh', 'en')     # 英文 → 中文（顯示）
        return f"🧑‍🏫 原文（印尼語）：\n{text}\n\n🌐 中文翻譯：\n{zh}"

    else:
        return "⚠️ 暫不支援此語言"


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

# 處理文字訊息事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    reply_text = auto_translate(user_text)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run()
