import asyncio
from typing import Dict
from app.config import get_settings
from app.database import get_conn, utc_now_iso
from app.facebook import publish_to_facebook, publish_via_webhook


async def run_autopilot_cycle(scrape_fn) -> Dict:
    settings = get_settings()
    result = {"scraped": 0, "published": 0, "errors": []}

    if settings.get("auto_fetch_enabled"):
        scrape_res = await scrape_fn(limit_per_source=6)
        result["scraped"] = scrape_res.get("added", 0)
        result["errors"].extend(scrape_res.get("errors", []))

    has_webhook = bool(settings.get("webhook_url"))
    has_fb = bool(settings.get("fb_page_id") and settings.get("fb_page_access_token"))
    if settings.get("auto_publish_enabled") and (has_webhook or has_fb):
        limit = settings.get("auto_publish_max_per_run", 2)
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()

        for row in rows:
            job = dict(row)
            link = "" if job["source_url"].startswith("manual://") else job["source_url"]
            if has_webhook:
                res = await publish_via_webhook(
                    webhook_url=settings["webhook_url"],
                    message=job["sinhala_post"],
                    link=link,
                    card_image_url_path=job["card_image_path"],
                    title=job["title_en"],
                )
            else:
                res = await publish_to_facebook(
                    page_id=settings["fb_page_id"],
                    access_token=settings["fb_page_access_token"],
                    message=job["sinhala_post"],
                    link=link,
                    card_image_url_path=job["card_image_path"],
                    link_in_first_comment=True,
                )
            if res.get("ok"):
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE jobs SET status = 'published', fb_post_id = ?, error_message = '', published_at = ? WHERE id = ?",
                        (res.get("post_id", ""), utc_now_iso(), job["id"]),
                    )
                result["published"] += 1
            else:
                result["errors"].append(f"Job {job['id']}: {res.get('error')}")

    return result


async def autopilot_loop(scrape_fn):
    while True:
        settings = get_settings()
        interval_sec = max(1, settings.get("auto_fetch_interval_hours", 4)) * 3600
        await asyncio.sleep(interval_sec)
        try:
            if settings.get("auto_fetch_enabled") or settings.get("auto_publish_enabled"):
                await run_autopilot_cycle(scrape_fn)
        except Exception:
            pass
