import os
import requests
import google.generativeai as genai

# Setup Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# 1. Fetch Posts (උදාහරණයක් ලෙස Text එකක් පරික්ෂා කිරීමට)
# මෙතැනට Meta Graph API හරහා එකතු වන පෝස්ට් එකේ Text එක යෙදේ
post_text = "Here is the fetched post content from your social media."

# 2. Check Policy Violation using Gemini Free AI
model = genai.GenerativeModel('gemini-1.5-flash')
prompt = f"""
Analyze this social media post for policy violations (hate speech, violence, harassment, misinformation, explicit content).
Post: "{post_text}"

Reply ONLY in this JSON format:
{{"violation": true/false, "reason": "brief explanation in Sinhala"}}
"""

response = model.generate_content(prompt)
result = response.text

# 3. Send Telegram Alert if Violation Found
if '"violation": true' in result.lower() or '"violation":True' in result:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    message = f"⚠️ **Policy Violation Alert!**\n\nවිස්තරය: {result}"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})
