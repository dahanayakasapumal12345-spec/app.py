import os
import time
import requests
from google import genai

# Setup Gemini API Client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Access Tokens
ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]
INSTAGRAM_ID = os.environ["INSTAGRAM_ID"]

# Telegram Credentials
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def download_file(url, filename):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return filename
    return None

def fetch_latest_posts():
    posts = []
    
    # 1. Fetch Latest Facebook Posts (පෝස්ට් 5ම ලබා ගැනීමට loop එකක් භාවිත කෙරේ)
    try:
        fb_url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/published_posts?fields=message,created_time,attachments{{media_type,media,subattachments}}&limit=5&access_token={ACCESS_TOKEN}"
        fb_res = requests.get(fb_url).json()
        
        if 'error' in fb_res:
            print(f"FB API Error: {fb_res['error'].get('message')}")
        elif 'data' in fb_res:
            for post_data in fb_res['data']: # සාර්ථකව පෝස්ට් එකිනෙක පරික්ශා කිරීම
                msg = post_data.get('message', '')
                media_url = None
                media_type = 'text'

                if 'attachments' in post_data and 'data' in post_data['attachments']:
                    attachment = post_data['attachments']['data'][0]
                    media_type = attachment.get('media_type', 'text')
                    if 'media' in attachment and 'image' in attachment['media']:
                        media_url = attachment['media']['image'].get('src')
                    elif 'media' in attachment and 'source' in attachment['media']:
                        media_url = attachment['media'].get('source')

                posts.append({
                    "source": "Facebook",
                    "text": msg,
                    "media_url": media_url,
                    "media_type": media_type
                })
    except Exception as e:
        print(f"FB Fetch Error: {e}")

    # 2. Fetch Latest Instagram Posts
    try:
        ig_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ID}/media?fields=caption,media_type,media_url,timestamp&limit=5&access_token={ACCESS_TOKEN}"
        ig_res = requests.get(ig_url).json()
        
        if 'error' in ig_res:
            print(f"IG API Error: {ig_res['error'].get('message')}")
        elif 'data' in ig_res:
            for post_data in ig_res['data']: # සාර්ථකව පෝස්ට් එකිනෙක පරික්ශා කිරීම
                caption = post_data.get('caption', '')
                media_url = post_data.get('media_url')
                media_type = post_data.get('media_type', 'IMAGE').lower()

                posts.append({
                    "source": "Instagram",
                    "text": caption,
                    "media_url": media_url,
                    "media_type": media_type
                })
    except Exception as e:
        print(f"IG Fetch Error: {e}")

    return posts

# Main Process
latest_posts = fetch_latest_posts()

if not latest_posts:
    send_telegram_msg("ℹ️ **දිනපතා පරීක්ෂාව:** අද දින Facebook හෝ Instagram හි අලුත් පෝස්ට් කිසිවක් හමු නොවීය.")
else:
    violations_found = False
    checked_posts_summary = []  # පරීක්ෂා කළ පෝස්ට් වල විස්තර එකතු කිරීමට

    for post in latest_posts:
        contents = []
        uploaded_file = None
        local_filename = None

        # Process Media (Image or Video)
        if post['media_url']:
            if 'video' in post['media_type']:
                local_filename = "temp_video.mp4"
                if download_file(post['media_url'], local_filename):
                    print("Uploading Video to Gemini File API...")
                    uploaded_file = client.files.upload(file=local_filename)
                    attempts = 0
                while uploaded_file.state.name == "PROCESSING" and attempts < 20:
                    time.sleep(3)
                    attempts += 1
                    try:
                        uploaded_file = client.files.get(name=uploaded_file.name)
                    except Exception as file_err:
                        print(f"Temporary Gemini API error (Retrying...): {file_err}")
                
                if uploaded_file.state.name == "ACTIVE":
                    contents.append(uploaded_file)
                else:
                    print(f"Video processing failed or timed out. State: {uploaded_file.state.name}")
            elif 'image' in post['media_type'] or 'photo' in post['media_type']:
                local_filename = "temp_image.jpg"
                if download_file(post['media_url'], local_filename):
                    uploaded_file = client.files.upload(file=local_filename)
                    contents.append(uploaded_file)

        # Prompt for Multimodal Analysis
        prompt = f"""
        You are an automated social media policy inspector inspecting both the text, images, and video content for {post['source']}.
        Analyze the text caption AND the attached visual/audio media for policy violations such as:
        - Hate speech or discrimination
        - Violence, weapons, physical harm, or gore
        - Harassment or personal attacks
        - Explicit, sexual, or suggestive content
        - Misinformation, frauds, scams, or illegal acts

        Post Caption Text: "{post['text']}"

        Respond ONLY with a clear summary in Sinhala language detailing any violation found in text, image, or video.
        If there is any violation in text OR media, include the exact phrase "VIOLATION_FOUND" in your response.
        If there are NO violations in both text and media, respond EXACTLY with "NO_VIOLATION".
        """
        contents.append(prompt)

        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=contents
            )
            result_text = response.text

            # පෝස්ට් එකේ විස්තර කෙටි සාරාංශයකට එකතු කිරීම
            post_preview = post['text'][:60] + "..." if len(post['text']) > 60 else post['text']
            checked_posts_summary.append(f"• **{post['source']}**: \"{post_preview}\"")

            if "VIOLATION_FOUND" in result_text:
                violations_found = True
                msg = f"⚠️ **{post['source']} Policy Violation Alert!**\n\n{result_text}\n\n**Original Caption:** {post['text']}"
                send_telegram_msg(msg)
        except Exception as err:
            print(f"Gemini Analysis Error: {err}")

        # Cleanup uploaded & local files
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except:
                pass
        if local_filename and os.path.exists(local_filename):
            os.remove(local_filename)

    # All Clear Message සමඟ පරීක්ෂා කළ පෝස්ට් වල ලැයිස්තුව යැවීම
    if not violations_found:
        summary_text = "\n".join(checked_posts_summary)
        msg = (
            f"✅ **දිනපතා පරීක්ෂාව අවසන්:**\n"
            f"ඔබගේ මෑත පෝස්ට් වල කිසිදු ප්‍රතිපත්ති උල්ලංඝනයක් (Policy Violation) හමු නොවීය. All Clear! 👍\n\n"
            f"📋 **පරීක්ෂා කරන ලද පෝස්ට්:**\n{summary_text}"
        )
        send_telegram_msg(msg)
