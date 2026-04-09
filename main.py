import os
import sys
import random
import requests
import numpy as np
from datetime import datetime
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MISTRAL_API_KEY      = os.environ.get("MISTRAL_KEY", "")
ELEVEN_API_KEY       = os.environ.get("ELEVEN_KEY", "")
YT_REFRESH_TOKEN     = os.environ.get("YT_REFRESH_TOKEN", "")
YT_CLIENT_ID         = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET_STR = os.environ.get("YT_CLIENT_SECRET_STR", "")

VIDEO_W = 1080
VIDEO_H = 1920
FPS     = 30

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── MISTRAL ──────────────────────────────────────────────────────────────────
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

# ─── STEP 0: TOPIC ────────────────────────────────────────────────────────────
def pick_topic():
    print("[0/5] Asking AI for best trending topic...")
    topic = call_mistral("""You are a viral YouTube Shorts expert.
Suggest ONE video topic in English, trending and highly monetizable.
Niche: finance, business, or AI/tech.
Under 55 characters.
Return ONLY the topic title, no quotes, no punctuation.""", max_tokens=60)
    print(f"   Topic: {topic}")
    return topic

# ─── STEP 1: SCRIPT + KEYWORDS + TOOLS ───────────────────────────────────────
def generate_script(topic):
    print("[1/5] Generating script + keywords + tools...")

    script = call_mistral(f"""Write a punchy YouTube Shorts script in English about: "{topic}"
- 55 seconds when read aloud (~130 words)
- VERY energetic, punchy, direct like a top finance TikToker
- Start with a SHOCKING hook statement, no "hey guys"
- 3 fast key points with numbers or stats
- End with: Subscribe for more money tips every day.
- Return ONLY the script text, nothing else""", max_tokens=300)

    keywords_raw = call_mistral(f"""Give 6 simple English image search keywords for: "{topic}"
Example: money, finance, investing, stock market, wealth, success
Return ONLY 6 single keywords separated by commas, nothing else.""", max_tokens=40)
    keywords = [k.strip() for k in keywords_raw.split(",")][:6]
    if len(keywords) < 3:
        keywords = ["finance", "money", "investing", "business", "success", "wealth"]

    tools_raw = call_mistral(f"""List real websites or apps mentioned in this script. If none write NONE.
Script: {script}
Return only full URLs starting with http, one per line.""", max_tokens=100)
    tools = [] if "NONE" in tools_raw.upper() else [
        t.strip() for t in tools_raw.split("\n")
        if t.strip().startswith("http")
    ]

    print(f"   Script ready ({len(script)} chars)")
    print(f"   Keywords: {keywords}")
    print(f"   Tools: {tools}")
    return script, keywords, tools

# ─── STEP 2: VOICEOVER ────────────────────────────────────────────────────────
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
                "voice_settings": {"stability": 0.3, "similarity_boost": 0.85}
            }
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers=headers, json=body, timeout=60
            )
            if r.status_code == 200:
                output_path.write_bytes(r.content)
                print("   ElevenLabs voice OK")
                return True
            print("   ElevenLabs quota reached, switching to gTTS")
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

# ─── STEP 3: IMAGES ───────────────────────────────────────────────────────────
def fetch_image(keyword, index):
    from PIL import Image
    import io
    for url in [
        f"https://source.unsplash.com/{VIDEO_W}x{VIDEO_H}/?{keyword}&sig={index}{random.randint(0,9999)}",
        f"https://picsum.photos/{VIDEO_W}/{VIDEO_H}?random={index}{random.randint(0,9999)}"
    ]:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                return img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
        except Exception:
            pass
    colors = ["#0d1117", "#1a1a2e", "#16213e", "#0f3460", "#1b262c", "#161b22"]
    return Image.new("RGB", (VIDEO_W, VIDEO_H), colors[index % len(colors)])

def generate_images(keywords, num_images=8):
    print("[3/5] Fetching images...")
    from PIL import Image
    images = []
    for i in range(num_images):
        kw = keywords[i % len(keywords)]
        img = fetch_image(kw, i)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 130))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        path = OUTPUT_DIR / f"img_{i}.jpg"
        img.save(str(path), "JPEG", quality=95)
        images.append(str(path))
    print(f"   {len(images)} images ready")
    return images

# ─── KEN BURNS ZOOM ───────────────────────────────────────────────────────────
def make_ken_burns_clip(img_path, duration, zoom_direction="in"):
    from moviepy.editor import VideoClip
    from PIL import Image

    img = Image.open(img_path).convert("RGB")
    img_arr = np.array(img, dtype=np.uint8)
    h, w = img_arr.shape[:2]

    zoom_start = 1.0 if zoom_direction == "in" else 1.08
    zoom_end   = 1.08 if zoom_direction == "in" else 1.0

    def make_frame(t):
        progress = t / max(duration, 0.001)
        zoom = zoom_start + (zoom_end - zoom_start) * progress
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        x1 = (w - new_w) // 2
        y1 = (h - new_h) // 2
        cropped = img_arr[y1:y1+new_h, x1:x1+new_w]
        resized = np.array(
            Image.fromarray(cropped).resize((w, h), Image.LANCZOS),
            dtype=np.uint8
        )
        return resized

    return VideoClip(make_frame, duration=duration).set_fps(FPS)

# ─── PIL TEXT ON FRAME (sans ImageMagick pour titre/sous-titres) ──────────────
def draw_text_on_frame(frame, text, y_center, fontsize=60, color=(255,255,0)):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.fromarray(frame.astype(np.uint8))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", fontsize)
    except Exception:
        font = ImageFont.load_default()

    # Word wrap
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > VIDEO_W - 80:
            if current:
                lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    total_h = len(lines) * (fontsize + 8)
    y = y_center - total_h // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (VIDEO_W - text_w) // 2
        # Shadow
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,3),(0,-3),(-3,0),(3,0)]:
            draw.text((x+dx, y+dy), line, font=font, fill=(0,0,0))
        draw.text((x, y), line, font=font, fill=color)
        y += fontsize + 8

    return np.array(img)

# ─── STEP 4: VIDEO WITH EFFECTS + PIL SUBTITLES ───────────────────────────────
def assemble_video(images, audio_path, topic, script, output_path):
    print("[4/5] Assembling video with effects + subtitles...")
    try:
        from moviepy.editor import (AudioFileClip, VideoClip,
                                    concatenate_videoclips)
        from moviepy.video.fx.fadein import fadein
        from moviepy.video.fx.fadeout import fadeout

        audio = AudioFileClip(str(audio_path))
        total_duration = audio.duration
        clip_duration = total_duration / len(images)

        # Subtitle chunks — 3 words each
        words = script.split()
        chunk_size = 3
        chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
        chunk_dur = total_duration / len(chunks)

        # Ken Burns clips
        directions = ["in","out","in","out","in","out","in","out"]
        base_clips = []
        for i, img_path in enumerate(images):
            clip = make_ken_burns_clip(img_path, clip_duration, directions[i % len(directions)])
            if i > 0:
                clip = fadein(clip, 0.25)
            if i < len(images) - 1:
                clip = fadeout(clip, 0.25)
            base_clips.append(clip)

        base_video = concatenate_videoclips(base_clips, method="compose")

        # Composite: base + PIL subtitles + progress bar
        short_title = (topic[:40] + "...") if len(topic) > 40 else topic

        def make_final_frame(t):
            frame = base_video.get_frame(t)
            frame = frame.copy()

            # Title first 3 seconds
            if t < 3.0:
                alpha = min(1.0, (3.0 - t) / 0.5) if t > 2.5 else 1.0
                frame = draw_text_on_frame(
                    frame, short_title.upper(),
                    y_center=220, fontsize=58,
                    color=(255, 255, 255)
                )

            # Subtitle
            chunk_idx = min(int(t / chunk_dur), len(chunks) - 1)
            frame = draw_text_on_frame(
                frame, chunks[chunk_idx],
                y_center=VIDEO_H - 320,
                fontsize=62,
                color=(255, 220, 0)
            )

            # Progress bar
            progress = t / total_duration
            bar_w = int(VIDEO_W * progress)
            frame[VIDEO_H-10:VIDEO_H, :bar_w] = [255, 200, 0]

            return frame

        final_clip = VideoClip(make_final_frame, duration=total_duration).set_fps(FPS)
        final_clip = final_clip.set_audio(audio)

        final_clip.write_videofile(
            str(output_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(OUTPUT_DIR / "temp_audio.m4a"),
            remove_temp=True,
            logger=None,
            preset="fast"
        )
        print(f"   Video ready: {output_path}")
        return True
    except Exception as e:
        print(f"   Assembly error: {e}")
        import traceback
        traceback.print_exc()
        return False

# ─── STEP 5: YOUTUBE ──────────────────────────────────────────────────────────
def upload_to_youtube(video_path, topic, script, tools):
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

        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

        tools_section = ""
        if tools:
            tools_section = "\n\nTools & Resources mentioned:\n" + "\n".join(tools)

        description = (
            script[:300] + "...\n\n"
            "Subscribe for daily money tips and financial advice."
            + tools_section +
            "\n\n#finance #money #investing #business #personalfinance "
            "#makemoney #wealth #financetips #shorts"
        )

        body = {
            "snippet": {
                "title": topic + " #shorts",
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
            str(video_path), mimetype="video/mp4", resumable=True)

        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media)

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

    topic                   = pick_topic()
    script, keywords, tools = generate_script(topic)
    audio_path              = OUTPUT_DIR / "voiceover.mp3"
    video_path              = OUTPUT_DIR / "final_video.mp4"

    if not script:
        print("ERROR: Empty script")
        sys.exit(1)

    if not generate_voice(script, audio_path):
        print("ERROR: Voice generation failed")
        sys.exit(1)

    images = generate_images(keywords)

    if not assemble_video(images, audio_path, topic, script, output_path=video_path):
        print("ERROR: Video assembly failed")
        sys.exit(1)

    video_id = upload_to_youtube(video_path, topic, script, tools)

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
