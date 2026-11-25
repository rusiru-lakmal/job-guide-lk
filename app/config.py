import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CARDS_DIR = DATA_DIR / "cards"
ENV_PATH = BASE_DIR / ".env"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CARDS_DIR.mkdir(parents=True, exist_ok=True)

if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)


def get_settings() -> dict:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)
    return {
        "fb_page_id": os.getenv("FB_PAGE_ID", "").strip(),
        "fb_page_access_token": os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip(),
        "gemini_api_key": os.getenv("GEMINI_API_KEY", "").strip(),
        "page_brand_name": os.getenv("PAGE_BRAND_NAME", "Sri Lanka Job News").strip() or "Sri Lanka Job News",
        "chrome_path": os.getenv(
            "CHROME_PATH",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ).strip(),
    }


def save_settings(updates: dict) -> dict:
    current = get_settings()
    for key in ("fb_page_id", "fb_page_access_token", "gemini_api_key", "page_brand_name", "chrome_path"):
        if key in updates and updates[key] is not None:
            current[key] = str(updates[key]).strip()

    lines = [
        f"FB_PAGE_ID={current['fb_page_id']}",
        f"FB_PAGE_ACCESS_TOKEN={current['fb_page_access_token']}",
        f"GEMINI_API_KEY={current['gemini_api_key']}",
        f"PAGE_BRAND_NAME={current['page_brand_name']}",
        f"CHROME_PATH={current['chrome_path']}",
    ]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(ENV_PATH, override=True)
    return current
