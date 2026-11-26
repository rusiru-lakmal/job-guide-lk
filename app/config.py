import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CARDS_DIR = DATA_DIR / "cards"
VIDEOS_DIR = DATA_DIR / "videos"
ENV_PATH = BASE_DIR / ".env"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CARDS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)


def get_settings() -> dict:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)
    return {
        "fb_page_id": os.getenv("FB_PAGE_ID", "").strip(),
        "fb_page_access_token": os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip(),
        "webhook_url": os.getenv("WEBHOOK_URL", "").strip(),
        "gemini_api_key": os.getenv("GEMINI_API_KEY", "").strip(),
        "page_brand_name": os.getenv("PAGE_BRAND_NAME", "Sri Lanka Job News").strip() or "Sri Lanka Job News",
        "chrome_path": os.getenv(
            "CHROME_PATH",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ).strip(),
        "auto_fetch_enabled": os.getenv("AUTO_FETCH_ENABLED", "true").strip().lower() == "true",
        "auto_fetch_interval_hours": max(1, int(os.getenv("AUTO_FETCH_INTERVAL_HOURS", "4") or "4")),
        "auto_publish_enabled": os.getenv("AUTO_PUBLISH_ENABLED", "false").strip().lower() == "true",
        "auto_publish_max_per_run": max(1, int(os.getenv("AUTO_PUBLISH_MAX_PER_RUN", "2") or "2")),
    }


def save_settings(updates: dict) -> dict:
    current = get_settings()
    for key in ("fb_page_id", "fb_page_access_token", "webhook_url", "gemini_api_key", "page_brand_name", "chrome_path"):
        if key in updates and updates[key] is not None:
            current[key] = str(updates[key]).strip()
    for bool_key in ("auto_fetch_enabled", "auto_publish_enabled"):
        if bool_key in updates and updates[bool_key] is not None:
            current[bool_key] = bool(updates[bool_key])
    for int_key in ("auto_fetch_interval_hours", "auto_publish_max_per_run"):
        if int_key in updates and updates[int_key] is not None:
            current[int_key] = max(1, int(updates[int_key]))

    lines = [
        f"FB_PAGE_ID={current['fb_page_id']}",
        f"FB_PAGE_ACCESS_TOKEN={current['fb_page_access_token']}",
        f"WEBHOOK_URL={current['webhook_url']}",
        f"GEMINI_API_KEY={current['gemini_api_key']}",
        f"PAGE_BRAND_NAME={current['page_brand_name']}",
        f"CHROME_PATH={current['chrome_path']}",
        f"AUTO_FETCH_ENABLED={'true' if current['auto_fetch_enabled'] else 'false'}",
        f"AUTO_FETCH_INTERVAL_HOURS={current['auto_fetch_interval_hours']}",
        f"AUTO_PUBLISH_ENABLED={'true' if current['auto_publish_enabled'] else 'false'}",
        f"AUTO_PUBLISH_MAX_PER_RUN={current['auto_publish_max_per_run']}",
    ]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(ENV_PATH, override=True)
    return current
