import asyncio
import json
import os
from pathlib import Path
from typing import Optional
import httpx
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import ENV_PATH
from music_studio.database import get_music_conn, init_music_db, utc_now_iso
from music_studio.scriptwriter import build_fb_caption, generate_song_story
from music_studio.video_engine import MUSIC_MEDIA_DIR, render_music_story_video

app = FastAPI(title="USA/UK Music Stories Studio")
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/music-media", StaticFiles(directory=str(MUSIC_MEDIA_DIR)), name="music-media")


def _get_music_settings() -> dict:
    vals = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    return {
        "music_webhook_url": (vals.get("MUSIC_WEBHOOK_URL") or os.getenv("MUSIC_WEBHOOK_URL", "")).strip(),
        "music_autopilot_enabled": (vals.get("MUSIC_AUTOPILOT_ENABLED") or "false").strip().lower() == "true",
        "music_autopilot_hours": max(1, int((vals.get("MUSIC_AUTOPILOT_HOURS") or "6").strip())),
        "default_voice": (vals.get("MUSIC_DEFAULT_VOICE") or "us_male").strip(),
        "default_format": (vals.get("MUSIC_DEFAULT_FORMAT") or "reel").strip(),
    }


def _save_music_settings(updates: dict):
    vals = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    mapping = {
        "music_webhook_url": "MUSIC_WEBHOOK_URL",
        "music_autopilot_enabled": "MUSIC_AUTOPILOT_ENABLED",
        "music_autopilot_hours": "MUSIC_AUTOPILOT_HOURS",
        "default_voice": "MUSIC_DEFAULT_VOICE",
        "default_format": "MUSIC_DEFAULT_FORMAT",
    }
    for k, env_k in mapping.items():
        if k in updates and updates[k] is not None:
            v = updates[k]
            vals[env_k] = ("true" if v else "false") if isinstance(v, bool) else str(v).strip()

    lines = [f"{k}={v}" for k, v in vals.items() if v is not None]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _autopilot_loop():
    while True:
        s = _get_music_settings()
        await asyncio.sleep(s["music_autopilot_hours"] * 3600)
        try:
            if s["music_autopilot_enabled"] and s["music_webhook_url"]:
                story = generate_song_story()
                created = await _create_story_and_video(
                    story, voice=s["default_voice"], video_format=s["default_format"]
                )
                await _publish_story_webhook(created["id"])
        except Exception:
            pass


@app.on_event("startup")
async def on_startup():
    init_music_db()
    asyncio.create_task(_autopilot_loop())


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


class GenerateStoryRequest(BaseModel):
    artist: str = ""
    song_title: str = ""
    voice: str = "us_male"
    video_format: str = "reel"


class MusicSettingsUpdate(BaseModel):
    music_webhook_url: Optional[str] = None
    music_autopilot_enabled: Optional[bool] = None
    music_autopilot_hours: Optional[int] = None
    default_voice: Optional[str] = None
    default_format: Optional[str] = None


async def _create_story_and_video(story: dict, voice: str, video_format: str) -> dict:
    caption = build_fb_caption(story)
    now = utc_now_iso()
    with get_music_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO stories (artist, song_title, hook, scenes_json, caption, voice, video_format, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                story["artist"],
                story["song_title"],
                story["hook"],
                json.dumps(story["scenes"], ensure_ascii=False),
                caption,
                voice,
                video_format,
                now,
            ),
        )
        sid = cur.lastrowid

    media = await render_music_story_video(
        story_id=sid,
        artist=story["artist"],
        song_title=story["song_title"],
        scenes=story["scenes"],
        voice=voice,
        video_format=video_format,
    )

    with get_music_conn() as conn:
        conn.execute(
            "UPDATE stories SET video_path = ?, thumbnail_path = ? WHERE id = ?",
            (media["video_path"], media["thumbnail_path"], sid),
        )
        row = conn.execute("SELECT * FROM stories WHERE id = ?", (sid,)).fetchone()
    return dict(row)


async def _publish_story_webhook(story_id: int) -> dict:
    s = _get_music_settings()
    webhook_url = s["music_webhook_url"]
    if not webhook_url:
        raise HTTPException(status_code=400, detail="Music Webhook URL is not configured in Settings.")

    with get_music_conn() as conn:
        row = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Story not found")
        story = dict(row)

    video_file = MUSIC_MEDIA_DIR / Path(story["video_path"]).name
    if not video_file.exists():
        raise HTTPException(status_code=400, detail="Video file not found.")

    data = {
        "artist": story["artist"],
        "song_title": story["song_title"],
        "title": f"{story['artist']} - {story['song_title']}",
        "message": story["caption"],
        "video_format": story["video_format"],
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        with video_file.open("rb") as f:
            files = {"video": (video_file.name, f, "video/mp4")}
            resp = await client.post(webhook_url, data=data, files=files)
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail=f"Webhook HTTP {resp.status_code}: {resp.text[:200]}")

    with get_music_conn() as conn:
        conn.execute(
            "UPDATE stories SET status = 'published', fb_post_id = ?, published_at = ? WHERE id = ?",
            (f"webhook:{resp.status_code}", utc_now_iso(), story_id),
        )
        updated = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
    return dict(updated)


@app.get("/api/stories")
def list_stories():
    with get_music_conn() as conn:
        rows = conn.execute("SELECT * FROM stories ORDER BY id DESC").fetchall()
    return {"stories": [dict(r) for r in rows]}


@app.post("/api/stories/generate")
async def generate_story(req: GenerateStoryRequest):
    story = generate_song_story(artist=req.artist, song_title=req.song_title)
    created = await _create_story_and_video(story, voice=req.voice, video_format=req.video_format)
    return {"story": created}


@app.post("/api/stories/{story_id}/publish")
async def publish_story(story_id: int):
    updated = await _publish_story_webhook(story_id)
    return {"story": updated}


@app.delete("/api/stories/{story_id}")
def delete_story(story_id: int):
    with get_music_conn() as conn:
        conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    return {"ok": True}


@app.get("/api/settings")
def get_settings_api():
    return _get_music_settings()


@app.post("/api/settings")
def save_settings_api(body: MusicSettingsUpdate):
    _save_music_settings(body.model_dump())
    return _get_music_settings()
