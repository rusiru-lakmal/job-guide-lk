import asyncio
import html
import json
import subprocess
from pathlib import Path
from typing import Dict
import edge_tts

from app.config import VIDEOS_DIR, get_settings
from app.formatter import category_to_sinhala

VOICES = {
    "female": "si-LK-ThiliniNeural",
    "male": "si-LK-SameeraNeural",
}


def build_voiceover_script(job: Dict) -> str:
    brand = "SL රැකියා මග"
    role = (job.get("card_headline_si") or job.get("title_en") or "නව රැකියා ඇබෑර්තු").strip()
    company = (job.get("company") or "ශ්‍රී ලංකාවේ ප්‍රමුඛ ආයතනයක").strip()
    salary = (job.get("salary") or "").strip()
    closing = (job.get("closing_date") or "").strip()

    parts = [
        f"ආයුබෝවන්! {brand} වෙතින් අද නවතම රැකියා අවස්ථාවක්.",
        f"{company} හි, {role} තනතුර සඳහා දැන් අයදුම්පත් කැඳවනු ලැබේ.",
    ]
    if salary:
        parts.append(f"මෙම තනතුර සඳහා වැටුප {salary} ලෙස සඳහන් වේ.")
    if closing and "වෙබ්" not in closing:
        parts.append(f"අයදුම් කිරීමේ අවසන් දිනය {closing}.")
    parts.append("සම්පූර්ණ විස්තර සහ අයදුම් කිරීමේ ලින්ක් එක පහත විස්තරයේ බලන්න.")
    parts.append("දිනපතා නවතම රැකියා පුවත් සඳහා අපේ පේජ් එක ෆලෝ කරන්න.")
    return " ".join(parts)


def _get_audio_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(audio_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    return float(data["format"]["duration"])


def _render_slide_png(
    chrome_path: str,
    html_content: str,
    html_path: Path,
    png_path: Path,
    width: int,
    height: int,
):
    html_path.write_text(html_content, encoding="utf-8")
    cmd = [
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--user-data-dir=/tmp/chrome-headless-profile",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    html_path.unlink(missing_ok=True)


def _build_slide_html(
    width: int,
    height: int,
    badge: str,
    title: str,
    subtitle: str,
    accent_box: str,
    brand_name: str,
    bg_gradient: str,
) -> str:
    is_reel = height > width
    title_size = "68px" if is_reel else "58px"
    sub_size = "40px" if is_reel else "34px"
    pad = "90px 72px" if is_reel else "72px 64px"
    return f"""<!DOCTYPE html>
<html lang="si">
<head>
<meta charset="UTF-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: {width}px;
    height: {height}px;
    font-family: 'Sinhala Sangam MN', 'Sinhala MN', -apple-system, BlinkMacSystemFont, sans-serif;
    background: {bg_gradient};
    color: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: {pad};
    position: relative;
    overflow: hidden;
  }}
  .grid {{
    position: absolute;
    inset: 0;
    background-image: radial-gradient(rgba(255,255,255,0.12) 1.5px, transparent 1.5px);
    background-size: 36px 36px;
  }}
  .top {{
    z-index: 2;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .brand {{
    background: rgba(255,255,255,0.14);
    border: 1.5px solid rgba(255,255,255,0.28);
    padding: 14px 28px;
    border-radius: 999px;
    font-size: 26px;
    font-weight: 700;
  }}
  .center {{
    z-index: 2;
    background: rgba(15, 23, 42, 0.55);
    backdrop-filter: blur(10px);
    border: 2px solid rgba(251, 191, 36, 0.45);
    border-radius: 40px;
    padding: 58px 48px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 28px;
    box-shadow: 0 28px 60px rgba(0,0,0,0.4);
  }}
  .badge {{
    background: linear-gradient(90deg, #fbbf24, #f59e0b);
    color: #0f172a;
    font-size: 28px;
    font-weight: 800;
    padding: 12px 34px;
    border-radius: 999px;
  }}
  .title {{
    font-size: {title_size};
    font-weight: 800;
    line-height: 1.25;
    color: #ffffff;
    word-break: break-word;
  }}
  .subtitle {{
    font-size: {sub_size};
    font-weight: 600;
    color: #fde68a;
    line-height: 1.4;
  }}
  .accent-box {{
    background: rgba(255, 255, 255, 0.12);
    border: 1.5px solid rgba(255,255,255,0.25);
    border-radius: 22px;
    padding: 20px 34px;
    font-size: 32px;
    font-weight: 700;
    color: #a7f3d0;
  }}
  .footer {{
    z-index: 2;
    text-align: center;
    font-size: 26px;
    font-weight: 700;
    color: #fbbf24;
    background: rgba(0,0,0,0.35);
    padding: 22px 30px;
    border-radius: 24px;
  }}
</style>
</head>
<body>
  <div class="grid"></div>
  <div class="top">
    <div class="brand">🇱🇰 {html.escape(brand_name)}</div>
  </div>
  <div class="center">
    <div class="badge">{html.escape(badge)}</div>
    <div class="title">{html.escape(title)}</div>
    <div class="subtitle">{html.escape(subtitle)}</div>
    {f'<div class="accent-box">{html.escape(accent_box)}</div>' if accent_box else ''}
  </div>
  <div class="footer">👇 Apply Link එක Caption එකේ බලන්න • Follow 🔔</div>
</body>
</html>"""


async def generate_job_video(
    job_id: int,
    job: Dict,
    voice: str = "female",
    video_format: str = "reel",
) -> str:
    settings = get_settings()
    chrome_path = settings.get("chrome_path", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    brand_name = settings.get("page_brand_name", "SL රැකියා මග - Job Guide LK")

    width, height = (1080, 1920) if video_format == "reel" else (1080, 1080)
    voice_id = VOICES.get(voice, VOICES["female"])

    # 1. Generate Sinhala Voiceover MP3
    script = build_voiceover_script(job)
    audio_path = VIDEOS_DIR / f"job_{job_id}_voice.mp3"
    communicate = edge_tts.Communicate(script, voice_id)
    await communicate.save(str(audio_path))

    duration = max(6.0, _get_audio_duration(audio_path) + 0.6)
    seg_dur = round(duration / 3.0, 2)

    # 2. Render 3 dynamic slides
    cat_si = category_to_sinhala(job.get("category", "General"))
    role = (job.get("card_headline_si") or job.get("title_en") or "නව රැකියා ඇබෑර්තු").strip()
    company = (job.get("company") or "ශ්‍රී ලංකාවේ ප්‍රමුඛ ආයතනයක්").strip()
    salary = (job.get("salary") or "").strip()
    closing = (job.get("closing_date") or "වෙබ් අඩවිය බලන්න").strip()
    location = (job.get("location") or "Sri Lanka").strip()

    slides = [
        (
            f"🚨 {cat_si}",
            "නව රැකියා අවස්ථාවක්!",
            company,
            "දැන් අයදුම්පත් කැඳවනු ලැබේ",
            "linear-gradient(155deg, #020617 0%, #064e3b 55%, #0f766e 100%)",
        ),
        (
            "💼 තනතුර & විස්තර",
            role,
            f"🏢 {company}",
            f"💰 වැටුප: {salary}" if salary else f"📍 ස්ථානය: {location}",
            "linear-gradient(155deg, #0f172a 0%, #1e3a8a 55%, #1d4ed8 100%)",
        ),
        (
            "⏳ අවසන් දිනය",
            closing,
            "සම්පූර්ණ විස්තර සහ Apply Link එක පහත Caption එකේ!",
            "👍 Share & Follow SL රැකියා මග",
            "linear-gradient(155deg, #450a0a 0%, #991b1b 55%, #0f172a 100%)",
        ),
    ]

    png_paths = []
    for idx, (badge, title, sub, acc, bg) in enumerate(slides, start=1):
        hp = VIDEOS_DIR / f"job_{job_id}_s{idx}.html"
        pp = VIDEOS_DIR / f"job_{job_id}_s{idx}.png"
        html_str = _build_slide_html(width, height, badge, title, sub, acc, brand_name, bg)
        _render_slide_png(chrome_path, html_str, hp, pp, width, height)
        png_paths.append(pp)

    # 3. Assemble MP4 with gentle zoom + crossfade + Sinhala voiceover
    out_mp4 = VIDEOS_DIR / f"job_{job_id}.mp4"
    fade = 0.5
    d1 = seg_dur + fade
    d2 = seg_dur + fade
    d3 = seg_dur

    filter_complex = (
        f"[0:v]scale={width*2}:{height*2},zoompan=z='min(zoom+0.0008,1.08)':d={int(d1*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps=30,setpts=PTS-STARTPTS[v0];"
        f"[1:v]scale={width*2}:{height*2},zoompan=z='min(zoom+0.0008,1.08)':d={int(d2*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps=30,setpts=PTS-STARTPTS[v1];"
        f"[2:v]scale={width*2}:{height*2},zoompan=z='min(zoom+0.0008,1.08)':d={int(d3*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps=30,setpts=PTS-STARTPTS[v2];"
        f"[v0][v1]xfade=transition=fade:duration={fade}:offset={seg_dur}[v01];"
        f"[v01][v2]xfade=transition=fade:duration={fade}:offset={round(seg_dur*2, 2)}[vout]"
    )

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(d1), "-i", str(png_paths[0]),
        "-loop", "1", "-t", str(d2), "-i", str(png_paths[1]),
        "-loop", "1", "-t", str(d3), "-i", str(png_paths[2]),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "3:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out_mp4),
    ]
    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)

    # Cleanup temp files
    audio_path.unlink(missing_ok=True)
    for pp in png_paths:
        pp.unlink(missing_ok=True)

    return f"/videos/job_{job_id}.mp4"
