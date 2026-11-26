import asyncio
import base64
import html
import json
import subprocess
import urllib.parse
from pathlib import Path
from typing import Dict, List
import edge_tts
import httpx

from app.config import DATA_DIR, get_settings

MUSIC_MEDIA_DIR = DATA_DIR / "music_videos"
MUSIC_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

US_UK_VOICES = {
    "us_male": "en-US-AndrewNeural",
    "us_female": "en-US-JennyNeural",
    "uk_male": "en-GB-RyanNeural",
    "uk_female": "en-GB-SoniaNeural",
}


def _ffprobe_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(json.loads(res.stdout)["format"]["duration"])


async def _fetch_ai_image(prompt: str, topic_query: str, scene_idx: int, out_path: Path, w: int, h: int):
    req_w, req_h = (768, 1344) if h > w else (1280, 720)
    encoded = urllib.parse.quote(prompt[:240])
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={req_w}&height={req_h}&nologo=true"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        async with httpx.AsyncClient(timeout=18.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 5000:
                out_path.write_bytes(resp.content)
                return
    except Exception:
        pass

    # Fallback 1: Real high-res NASA Image Library API (free, no key, picks distinct image per scene)
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            for q in (topic_query, "space nebula galaxy cosmos"):
                r = await client.get(
                    "https://images-api.nasa.gov/search",
                    params={"q": q, "media_type": "image"},
                )
                items = r.json().get("collection", {}).get("items", []) if r.status_code == 200 else []
                if items:
                    chosen = items[(scene_idx * 3) % len(items)]
                    href = (chosen.get("links") or [{}])[0].get("href", "")
                    if href:
                        img_r = await client.get(href)
                        if img_r.status_code == 200 and len(img_r.content) > 5000:
                            out_path.write_bytes(img_r.content)
                            return
    except Exception:
        pass

    # Fallback 2: Deep cosmic gradient
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=#0f172a:s={w}x{h}:d=1", "-frames:v", "1", str(out_path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _render_scene_composite(
    chrome_path: str,
    bg_img: Path,
    category: str,
    title: str,
    narration: str,
    hp: Path,
    pp: Path,
    w: int,
    h: int,
):
    is_reel = h > w
    cap_size = "46px" if is_reel else "40px"
    pad = "72px 54px 160px 54px" if is_reel else "48px 96px 72px 96px"
    img_b64 = base64.b64encode(bg_img.read_bytes()).decode("ascii")
    html_str = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: {w}px; height: {h}px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #000000;
    color: #ffffff;
    position: relative;
    overflow: hidden;
  }}
  .bg {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: cover;
  }}
  .vignette {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.08) 38%, rgba(0,0,0,0.88) 100%);
  }}
  .overlay {{
    position: relative; z-index: 2;
    width: 100%; height: 100%;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: {pad};
  }}
  .top-pill {{
    align-self: flex-start;
    background: rgba(15, 23, 42, 0.78);
    border: 2px solid #fbbf24;
    color: #fbbf24;
    padding: 12px 28px;
    border-radius: 999px;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 0.8px;
    text-transform: uppercase;
  }}
  .caption-box {{
    background: rgba(0, 0, 0, 0.72);
    border-left: 8px solid #fbbf24;
    border-radius: 24px;
    padding: 32px 36px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.6);
  }}
  .cap-text {{
    font-size: {cap_size};
    font-weight: 900;
    line-height: 1.3;
    color: #ffffff;
    text-shadow: 0 4px 16px rgba(0,0,0,0.85);
  }}
</style>
</head>
<body>
  <img class="bg" src="data:image/jpeg;base64,{img_b64}" />
  <div class="vignette"></div>
  <div class="overlay">
    <div class="top-pill">🌌 {html.escape(category)} • {html.escape(title)}</div>
    <div class="caption-box">
      <div class="cap-text">{html.escape(narration)}</div>
    </div>
  </div>
</body>
</html>"""
    hp.write_text(html_str, encoding="utf-8")
    cmd = [
        chrome_path, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--user-data-dir=/tmp/chrome-headless-profile", "--hide-scrollbars",
        f"--window-size={w},{h}", f"--screenshot={pp}", hp.as_uri(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    hp.unlink(missing_ok=True)


async def _synth_scene(text: str, voice_id: str, mp3_path: Path) -> float:
    comm = edge_tts.Communicate(text, voice_id)
    await comm.save(str(mp3_path))
    return max(2.5, _ffprobe_duration(mp3_path) + 0.3)


async def render_music_story_video(
    story_id: int,
    artist: str,
    song_title: str,
    scenes: List[Dict],
    voice: str = "us_male",
    video_format: str = "reel",
) -> Dict[str, str]:
    settings = get_settings()
    chrome_path = settings.get("chrome_path", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    w, h = (1080, 1920) if video_format == "reel" else (1920, 1080)
    voice_id = US_UK_VOICES.get(voice, US_UK_VOICES["us_male"])

    # 1. Fetch AI / NASA cinematic images (max 2 concurrent to avoid rate limits)
    raw_imgs = [MUSIC_MEDIA_DIR / f"story_{story_id}_raw{i}.jpg" for i in range(len(scenes))]
    sem = asyncio.Semaphore(2)

    async def _bounded_fetch(i: int, s: Dict):
        async with sem:
            await _fetch_ai_image(
                s.get("visual_prompt", f"{artist} {song_title}"),
                song_title or artist or "space",
                i,
                raw_imgs[i],
                w,
                h,
            )

    await asyncio.gather(*[_bounded_fetch(i, s) for i, s in enumerate(scenes)])

    # 2. Synthesize narration + composite each scene with caption
    audio_clips = []
    durations = []
    comp_pngs = []

    for idx, scene in enumerate(scenes):
        mp3_path = MUSIC_MEDIA_DIR / f"story_{story_id}_a{idx}.mp3"
        dur = await _synth_scene(scene["narration"], voice_id, mp3_path)
        audio_clips.append(mp3_path)
        durations.append(dur)

        hp = MUSIC_MEDIA_DIR / f"story_{story_id}_s{idx}.html"
        pp = MUSIC_MEDIA_DIR / f"story_{story_id}_s{idx}.png"
        _render_scene_composite(chrome_path, raw_imgs[idx], artist, song_title, scene["narration"], hp, pp, w, h)
        comp_pngs.append(pp)

    # Save first composited frame as thumbnail
    thumb_path = MUSIC_MEDIA_DIR / f"story_{story_id}_thumb.png"
    thumb_path.write_bytes(comp_pngs[0].read_bytes())

    # 3. Concatenate narration MP3s
    concat_list = MUSIC_MEDIA_DIR / f"story_{story_id}_concat.txt"
    concat_list.write_text("\n".join(f"file '{p.name}'" for p in audio_clips), encoding="utf-8")
    merged_voice = MUSIC_MEDIA_DIR / f"story_{story_id}_voice.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(merged_voice)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # 4. Assemble MP4 with gentle Ken Burns zoom + crossfades + ambient space drone
    n = len(comp_pngs)
    fade = 0.35
    inputs = []
    filter_parts = []
    for i in range(n):
        d_i = durations[i] + (fade if i < n - 1 else 0.2)
        inputs.extend(["-loop", "1", "-t", f"{d_i:.2f}", "-i", str(comp_pngs[i])])
        frames = int(d_i * 30)
        filter_parts.append(
            f"[{i}:v]scale={w*2}:{h*2},zoompan=z='min(zoom+0.0008,1.08)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30,setpts=PTS-STARTPTS[v{i}]"
        )

    prev = "[v0]"
    offset = 0.0
    for i in range(1, n):
        offset += durations[i - 1]
        out_label = "[vout]" if i == n - 1 else f"[vx{i}]"
        filter_parts.append(f"{prev}[v{i}]xfade=transition=fade:duration={fade}:offset={offset:.2f}{out_label}")
        prev = out_label

    total_dur = sum(durations) + 1.0
    inputs.extend(["-i", str(merged_voice)])
    inputs.extend([
        "-f", "lavfi", "-t", f"{total_dur:.2f}",
        "-i", "aevalsrc=0.04*sin(2*PI*110*t)+0.03*sin(2*PI*164.81*t)+0.02*sin(2*PI*220*t):s=44100",
    ])
    filter_parts.append(f"[{n}:a]volume=1.1[vo];[{n+1}:a]lowpass=f=450,volume=0.35[bgm];[vo][bgm]amix=inputs=2:duration=first[aout]")

    out_mp4 = MUSIC_MEDIA_DIR / f"story_{story_id}.mp4"
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]" if n > 1 else "[v0]",
        "-map", "[aout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)

    concat_list.unlink(missing_ok=True)
    merged_voice.unlink(missing_ok=True)
    for p in audio_clips + raw_imgs + comp_pngs:
        p.unlink(missing_ok=True)

    return {
        "video_path": f"/music-media/story_{story_id}.mp4",
        "thumbnail_path": f"/music-media/story_{story_id}_thumb.png",
    }
