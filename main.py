import os
import sys
import random
import requests
from datetime import datetime
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MISTRAL_API_KEY      = os.environ.get("MISTRAL_KEY", "")
ELEVEN_API_KEY       = os.environ.get("ELEVEN_KEY", "")
YT_REFRESH_TOKEN     = os.environ.get("YT_REFRESH_TOKEN", "")
YT_CLIENT_ID         = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET_STR = os.environ.get("YT_CLIENT_SECRET_STR", "")

# Format Short vertical
VIDEO_W = 1080
VIDEO_H = 1920

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
Suggest ONE video topic in English, trending and monetizable.
Niche: finance, business, or AI/tech.
Under 60 characters.
Return ONLY the topic title, no quotes.""", max_tokens=60)
    print(f"   Topic: {topic}")
    return topic

# ─── STEP 1: SCRIPT + KEYWORDS + TOOLS ───────────────────────────────────────
def generate_script(topic):
    print("[1/5] Generating script + keywords + tools...")
    result = call_mistral(f"""You are a viral YouTube Shorts scriptwriter.

Write about: "{topic}"

Return EXACTLY this format, nothing else:

SCRIPT:
[90 second script, ~220 words, energetic and direct, finance/business tone]
[Hook 10s -> 3 key points 60s -> CTA 20s]
[Start strong, no "hey guys"]
[End with: Subscribe for more money tips every day.]

KEYWORDS:
[5 comma-separated English image search keywords related to the topic]

TOOLS:
[List any real websites, apps or platforms mentioned in the script, one per line, with URL. If none, write NONE]""", max_tokens=600)

    script = ""
    keywords = []
    tools = []

    lines = result.split("\n")
    section = None
    for line in lines:
        line = line.strip()
        if line.startswith("SCRIPT:"):
            section = "script"
        elif line.startswith("KEYWORDS:"):
            section = "keywords"
        elif line.startswith("TOOLS:"):
            section = "tools"
        elif section == "script" and line:
            script += line + " "
        elif section == "keywords" and line:
            keywords = [k.strip() for k in line.split(",")]
        elif section == "tools" and line and line != "NONE":
            tools.append(line)

    script = script.strip()
    if not keywords:
        keywords = ["finance", "money", "investing", "business", "success"]

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
                "voice_settings": {"stability": 0.35, "similarity_boost": 0.8}
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
def generate_images(keywords, num_images=6):
    print("[3/5] Fetching images...")
    from PIL import Image
    import io

    images = []
    for i in range(num_images):
        kw = keywords[i % len(keywords)]
        try:
            # Use keyword-based search via Unsplash source (portrait format)
            url = f"https://source.unsplash.com/{VIDEO_W}x{VIDEO_H}/?{kw}&sig={i}{random.randint(0,9999)}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img = img.resize((VIDEO_W, VIDEO_H))
            else:
                raise Exception(f"HTTP {r.status_code}")
        except Exception:
            try:
                url = f"https://picsum.photos/{VIDEO_W}/{VIDEO_H}?random={i}{random.randint(0,9999)}"
                r = requests.get(url, timeout=15)
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img = img.resize((VIDEO_W, VIDEO_H))
            except Exception:
                colors = ["#1a1a2e", "#16213e", "#0f3460", "#1b262c", "#0d1117", "#161b22"]
                img = Image.new("RGB", (VIDEO_W, VIDEO_H), colors[i % len(colors)])

        # Dark overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 140))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        path = OUTPUT_DIR / f"img_{i}.jpg"
        img.save(str(path), "JPEG")
        images.append(str(path))

    print(f"   {len(images)} images ready")
    return images

# ─── STEP 4: VIDEO WITH SUBTITLES ─────────────────────────────────────────────
def assemble_video(images, audio_path, topic, script, output_path):
    print("[4/5] Assembling video with subtitles...")
    try:
        from moviepy.editor import (ImageClip, AudioFileClip,
                                    concatenate_videoclips, TextClip,
                                    CompositeVideoClip)

        audio = AudioFileClip(str(audio_path))
        total_duration = audio.duration
        clip_duration = total_duration / len(images)

        # Split script into subtitle chunks (~5 words each)
        words = script.split()
        chunk_size = 5
        chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
        chunk_duration = total_duration / len(chunks)

        clips = []
        for i, img_path in enumerate(images):
            img_clip = ImageClip(img_path, duration=clip_duration)

            # Title on first clip
            if i == 0:
                short_title = topic[:40] + "..." if len(topic) > 40 else topic
                try:
                    title_txt = TextClip(
                        short_title.upper(),
                        fontsize=60, color="white",
                        font="DejaVu-Sans-Bold",
                        size=(VIDEO_W - 80, None),
                        method="caption",
                        stroke_color="black",
                        stroke_width=2
                    ).set_duration(clip_duration).set_position(("center", 200))
                    img_clip = CompositeVideoClip([img_clip, title_txt])
                except Exception:
                    pass

            clips.append(img_clip)

        # Build subtitle clips
        subtitle_clips = []
        for i, chunk in enumerate(chunks):
            start = i * chunk_duration
            try:
                sub = TextClip(
                    chunk,
                    fontsize=52,
                    color="yellow",
                    font="DejaVu-Sans-Bold",
                    size=(VIDEO_W - 80, None),
                    method="caption",
                    stroke_color="black",
                    stroke_width=2
                ).set_start(start).set_duration(chunk_duration).set_position(("center", VIDEO_H - 350))
                subtitle_clips.append(sub)
            except Exception:
                pass

        base_video = concatenate_videoclips(clips, method="compose")
        if subtitle_clips:
            final = CompositeVideoClip([base_video] + subtitle_clips)
        else:
            final = base_video

        final = final.set_audio(audio)
        final.write_videofile(
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

        youtube = googleapiclient.discovery.build(
            "youtube", "v3", credentials=creds)

        # Build description with tools links
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

    topic               = pick_topic()
    script, keywords, tools = generate_script(topic)
    audio_path          = OUTPUT_DIR / "voiceover.mp3"
    video_path          = OUTPUT_DIR / "final_video.mp4"

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
