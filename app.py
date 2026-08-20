import os
import time
import requests
import google.generativeai as genai

# Setup Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

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
    
    # 1. Fetch Latest Facebook Post (Text, Image, Video)
    try:
        fb_url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/published_posts?fields=message,attachments{{media_type,media,subattachments}}&limit=1&access_token={ACCESS_TOKEN}"
        fb_res = requests.get(fb_url).json()
        if 'data' in fb_res and len(fb_res['data']) > 0:
            post_data = fb_res['data'][0]
            msg = post_data.get('message', '')
            media_url = None
            media_type = 'text'

            if 'attachments' in post_data and 'data' in post_data['attachments']:
                attachment = post_data['attachments']['data'][0]
                media_type = attachment.get('media_type', 'text') # photo, video, share
                if 'media' in attachment and 'image' in attachment['media']:
                    media_url = attachment['media']['image'].get('src')
                elif 'media' in attachment and 'source' in attachment['media']:
                    media_url = attachment['media'].get('source') # Video source URL

            posts.append({
                "source": "Facebook",
                "text": msg,
                "media_url": media_url,
                "media_type": media_type
            })
    except Exception as e:
        print(f"FB Fetch Error: {e}")

    # 2. Fetch Latest Instagram Post Caption and Media
    try:
        ig_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ID}/media?fields=caption,media_type,media_url&limit=1&access_token={ACCESS_TOKEN}"
        ig_res = requests.get(ig_url).json()
        if 'data' in ig_res and len(ig_res['data']) > 0:
            post_data = ig_res['data'][0]
            caption = post_data.get('caption', '')
            media_url = post_data.get('media_url')
            media_type = post_data.get('media_type', 'IMAGE').lower() # IMAGE, VIDEO, CAROUSEL_ALBUM

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
    
    for post in latest_posts:
        model = genai.GenerativeModel('gemini-3.6-flash')
        contents = []
        uploaded_file = None
        local_filename = None

        # Process Media (Image or Video)
        if post['media_url']:
            if 'video' in post['media_type']:
                local_filename = "temp_video.mp4"
                if download_file(post['media_url'], local_filename):
                    print("Uploading Video to Gemini File API...")
                    uploaded_file = genai.upload_file(path=local_filename)
                    # Wait for processing
                    while uploaded_file.state.name == "PROCESSING":
                        time.sleep(2)
                        uploaded_file = genai.get_file(uploaded_file.name)
                    contents.append(uploaded_file)
            elif 'image' in post['media_type'] or 'photo' in post['media_type']:
                local_filename = "temp_image.jpg"
                if download_file(post['media_url'], local_filename):
                    uploaded_file = genai.upload_file(path=local_filename)
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
            response = model.generate_content(contents)
            result_text = response.text

            if "VIOLATION_FOUND" in result_text:
                violations_found = True
                msg = f"⚠️ **{post['source']} Policy Violation Alert! (Text/Image/Video Inspection)**\n\n{result_text}\n\n**Original Caption:** {post['text']}"
                send_telegram_msg(msg)
        except Exception as err:
            print(f"Gemini Analysis Error: {err}")

        # Cleanup uploaded & local files
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
        if local_filename and os.path.exists(local_filename):
            os.remove(local_filename)

    # All Clear Message
    if not violations_found:
        send_telegram_msg("✅ **දිනපතා පරීක්ෂාව අවසන්:** ඔබගේ මෑත පෝස්ට් වල (Text, Photos, සහ Videos) කිසිදු ප්‍රතිපත්ති උල්ලංඝනයක් (Policy Violation) හමු නොවීය. All Clear! 👍")
