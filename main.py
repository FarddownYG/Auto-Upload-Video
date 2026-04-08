import os
import sys
import random
import requests
from datetime import datetime
from pathlib import Path

# pip install moviepy gtts google-api-python-client google-auth-oauthlib pillow requests

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MISTRAL_API_KEY      = os.environ.get("MISTRAL_KEY", "")
ELEVEN_API_KEY       = os.environ.get("ELEVEN_KEY", "")
YT_REFRESH_TOKEN     = os.environ.get("YT_REFRESH_TOKEN", "")
YT_CLIENT_ID         = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET_STR = os.environ.get("YT_CLIENT_SECRET_STR", "")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── MISTRAL CALL ─────────────────────────────────────────────────────────────
def call_mistral(prompt, max_tokens=400):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.8
    }
    r = requests.post("https://api.mistral.ai/v1/chat/completions",
                      headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip().strip('"').strip("'")

# ─── STEP 0: GENERATE TOPIC ───────────────────────────────────────────────────
def pick_topic():
    print("[0/5] Asking AI for best trending topic...")
    topic = call_mistral("""You are a viral YouTube Shorts and TikTok expert.
Suggest ONE video topic in English that is currently trending and highly monetizable.
Niche: finance, business, or AI/tech.
Requirements:
- High CPM (finance/investing preferred)
- Trending in 2025
- Under 60 characters
- Return ONLY the topic title, nothing else, no quotes.""", max_tokens=60)
    print(f"   Topic: {topic}")
    return topic

# ─── STEP 1: GENERATE SCRIPT ─────────────────────────────────────────────────
def generate_script(topic):
    print("[1/5] Generating script...")
    script = call_mistral(f"""Write a YouTube Shorts video script in English about: "{topic}"

Rules:
- Duration: exactly 90 seconds when read aloud (about 220 words)
- Style: energetic, direct, no fluff, finance/business tone
- Structure: hook (10s) then 3 key points (60s) then call to action (20s)
- Start with a strong statement, no "hey guys"
- End with: "Subscribe for more money tips every day."
- Return ONLY the script text, nothing else""", max_tokens=400)
    print(f"   Script ready ({len(script)} chars)")
    return script

# ─── STEP 2: GENERATE VOICEOVER ──────────────────────────────────────────────
def generate_voice(script, output_path):
    print("[2/5] Generating voiceover...")

    if ELEVEN_API_KEY:
        try:
            voice_id = "21m00Tcm4TlvDq8ikWAM"
            headers = {
                "xi-api-key": ELEVEN_API_KEY,
                "Content-Type": "application/json"
            }
            body = {
                "text": script,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers=headers, json=body, timeout=60
            )
            if r.status_code == 200:
                output_path.write_bytes(r.content)
                print("   ElevenLabs voice OK")
                return True
            else:
                print(f"   ElevenLabs quota reached, switching to gTTS")
        except Exception as e:
            print(f"   ElevenLabs error: {e}")

    try:
        from gtts import gTTS
        tts = gTTS(text=script, lang="en", slow=False)
        tts.save(str(output_path))
        print("   gTTS voice OK")
        return True
    except Exception as e:
        print(f"   gTTS error: {e}")
        return False

# ─── STEP 3: FETCH IMAGES ────────────────────────────────────────────────────
def generate_images(topic, num_images=6):
    print("[3/5] Fetching images...")
    from PIL import Image
    import io

    images = []
    keywords = ["finance", "money", "business", "investment", "success", "growth"]

    for i in range(num_images):
        try:
            kw = keywords[i % len(keywords)]
            url = f"https://source.unsplash.com/1280x720/?{kw}&sig={i}{random.randint(0,9999)}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img = img.resize((1280, 720))
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 120))
                img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
                path = OUTPUT_DIR / f"img_{i}.jpg"
                img.save(str(path), "JPEG")
                images.append(str(path))
            else:
                raise Exception(f"HTTP {r.status_code}")
        except Exception as e:
            print(f"   Image {i} fallback: {e}")
            colors = ["#1a1a2e", "#16213e", "#0f3460", "#1b262c", "#0d1117", "#161b22"]
            img = Image.new("RGB", (1280, 720), colors[i % len(colors)])
            path = OUTPUT_DIR / f"img_{i}.jpg"
            img.save(str(path), "JPEG")
            images.append(str(path))

    print(f"   {len(images)} images ready")
    return images

# ─── STEP 4: ASSEMBLE VIDEO ──────────────────────────────────────────────────
def assemble_video(images, audio_path, topic, output_path):
    print("[4/5] Assembling video...")
    try:
        from moviepy.editor import (ImageClip, AudioFileClip,
                                    concatenate_videoclips, TextClip,
                                    CompositeVideoClip)

        audio = AudioFileClip(str(audio_path))
        total_duration = audio.duration
        clip_duration = total_duration / len(images)

        clips = []
        for i, img_path in enumerate(images):
            img_clip = ImageClip(img_path, duration=clip_duration)
            if i == 0:
                short_title = topic[:50] + "..." if len(topic) > 50 else topic
                try:
                    txt = TextClip(
                        short_title, fontsize=48, color="white",
                        font="DejaVu-Sans-Bold", size=(1200, None),
                        method="caption"
                    ).set_duration(clip_duration).set_position(("center", 580))
                    img_clip = CompositeVideoClip([img_clip, txt])
                except Exception:
                    pass
            clips.append(img_clip)

        video = concatenate_videoclips(clips, method="compose")
        video = video.set_audio(audio)
        video.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(OUTPUT_DIR / "temp_audio.m4a"),
            remove_temp=True,
            logger=None
        )
        print(f"   Video ready: {output_path}")
        return True
    except Exception as e:
        print(f"   Assembly error: {e}")
        return False

# ─── STEP 5: UPLOAD TO YOUTUBE ───────────────────────────────────────────────
def upload_to_youtube(video_path, topic, script):
    print("[5/5] Uploading to YouTube...")
    try:
        import google.oauth2.credentials
        import googleapiclient.discovery
        import googleapiclient.http

        creds = google.oauth2.credentials.Credentials(
            token=None,
            refresh_token=YT_REFRESH_TOKEN,
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET_STR,
            token_uri="https://oauth2.googleapis.com/token"
        )

        youtube = googleapiclient.discovery.build(
            "youtube", "v3", credentials=creds)

        description = (
            script[:300] + "...\n\n"
            "Subscribe for daily money tips and financial advice.\n\n"
            "#finance #money #investing #business #personalfinance "
            "#makemoney #wealth #financetips #shorts"
        )

        body = {
            "snippet": {
                "title": topic,
                "description": description,
                "tags": ["finance", "money", "investing", "business",
                         "personalfinance", "makemoney", "wealth", "shorts"],
                "categoryId": "27",
                "defaultLanguage": "en"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = googleapiclient.http.MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   Upload {int(status.progress() * 100)}%")

        print(f"   Done! https://youtube.com/watch?v={response['id']}")
        return response["id"]

    except Exception as e:
        print(f"   Upload error: {e}")
        return None

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"YouTube Auto Publisher - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    topic      = pick_topic()
    script     = generate_script(topic)
    audio_path = OUTPUT_DIR / "voiceover.mp3"
    video_path = OUTPUT_DIR / "final_video.mp4"

    if not generate_voice(script, audio_path):
        print("ERROR: Voice generation failed")
        sys.exit(1)

    images = generate_images(topic)

    if not assemble_video(images, audio_path, topic, video_path):
        print("ERROR: Video assembly failed")
        sys.exit(1)

    video_id = upload_to_youtube(video_path, topic, script)

    for f in OUTPUT_DIR.glob("img_*.jpg"):
        f.unlink()
    for f in [audio_path, video_path]:
        if f.exists():
            f.unlink()

    if video_id:
        print(f"\nSUCCESS: https://youtube.com/watch?v={video_id}")
    else:
        print("\nWARNING: Upload failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
