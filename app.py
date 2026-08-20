import os
import requests
import google.generativeai as genai

# Setup Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Access Tokens
ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]
INSTAGRAM_ID = os.environ["INSTAGRAM_ID"]

def fetch_latest_posts():
    posts = []
    
    # 1. Fetch Latest Facebook Post
    try:
        fb_url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/published_posts?fields=message&limit=1&access_token={ACCESS_TOKEN}"
        fb_res = requests.get(fb_url).json()
        if 'data' in fb_res and len(fb_res['data']) > 0:
            msg = fb_res['data'][0].get('message', '')
            if msg:
                posts.append({"source": "Facebook", "text": msg})
    except Exception as e:
        print(f"FB Fetch Error: {e}")

    # 2. Fetch Latest Instagram Post Caption
    try:
        ig_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ID}/media?fields=caption&limit=1&access_token={ACCESS_TOKEN}"
        ig_res = requests.get(ig_url).json()
        if 'data' in ig_res and len(ig_res['data']) > 0:
            caption = ig_res['data'][0].get('caption', '')
            if caption:
                posts.append({"source": "Instagram", "text": caption})
    except Exception as e:
        print(f"IG Fetch Error: {e}")

    return posts

# Main Process
latest_posts = fetch_latest_posts()

for post in latest_posts:
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    You are an automated social media policy inspector.
    Analyze this {post['source']} post for policy violations such as hate speech, violence, harassment, sexual content, or misinformation.

    Post Content: "{post['text']}"

    Respond ONLY with a clear summary in Sinhala language if there is a violation or risk.
    If there is a violation, include the word "VIOLATION_FOUND" in your response.
    """

    response = model.generate_content(prompt)
    result_text = response.text

    if "VIOLATION_FOUND" in result_text:
        bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        chat_id = os.environ["TELEGRAM_CHAT_ID"]
        message = f"⚠️ **{post['source']} Policy Violation Alert!**\n\n{result_text}\n\n**Original Post:** {post['text']}"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": message})
