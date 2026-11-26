from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.card_generator import generate_job_card
from app.config import BASE_DIR, CARDS_DIR, get_settings, save_settings
from app.database import get_conn, init_db, utc_now_iso
from app.facebook import fetch_page_analytics, publish_to_facebook, verify_page_token
from app.formatter import format_job_sinhala
from app.scraper import classify_category, extract_closing_date, extract_salary, fetch_single_url_job, fetch_topjobs_lk, fetch_wp_json_jobs

app = FastAPI(title="Sri Lanka Job News FB Studio")
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/cards", StaticFiles(directory=str(CARDS_DIR)), name="cards")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


class JobUpdate(BaseModel):
    sinhala_post: Optional[str] = None
    card_headline_si: Optional[str] = None
    card_subline_si: Optional[str] = None
    company: Optional[str] = None
    closing_date: Optional[str] = None
    salary: Optional[str] = None
    category: Optional[str] = None
    regenerate_card: bool = True


class ManualImportRequest(BaseModel):
    url: str = ""
    raw_text: str = ""
    title: str = ""
    company: str = ""
    closing_date: str = ""
    salary: str = ""
    category: str = ""
    source_name: str = "Manual / FB Import"


class SourceCreate(BaseModel):
    name: str
    url: str
    source_type: str = "wp_json"


class SourceToggle(BaseModel):
    enabled: bool


class SettingsUpdate(BaseModel):
    fb_page_id: Optional[str] = None
    fb_page_access_token: Optional[str] = None
    gemini_api_key: Optional[str] = None
    page_brand_name: Optional[str] = None


class ApproveRequest(BaseModel):
    include_image: bool = True


def _row_to_dict(row) -> dict:
    return dict(row)


def _insert_and_generate(job_data: dict) -> dict:
    formatted = format_job_sinhala(job_data)
    now = utc_now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                source_name, source_url, title_en, company, category,
                closing_date, salary, location, raw_excerpt, sinhala_post,
                card_headline_si, card_subline_si, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                job_data["source_name"],
                job_data["source_url"],
                job_data["title_en"],
                job_data.get("company", ""),
                job_data.get("category", "General"),
                job_data.get("closing_date", ""),
                job_data.get("salary", ""),
                job_data.get("location", "Sri Lanka"),
                job_data.get("raw_excerpt", ""),
                formatted["sinhala_post"],
                formatted["card_headline_si"],
                formatted["card_subline_si"],
                now,
            ),
        )
        job_id = cur.lastrowid

    card_payload = {**job_data, **formatted}
    card_path = generate_job_card(job_id, card_payload)
    if card_path:
        with get_conn() as conn:
            conn.execute("UPDATE jobs SET card_image_path = ? WHERE id = ?", (card_path, job_id))

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row)


@app.get("/api/jobs")
def list_jobs(status: str = "pending"):
    with get_conn() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM jobs WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
        counts_rows = conn.execute("SELECT status, COUNT(*) as c FROM jobs GROUP BY status").fetchall()

    counts = {r["status"]: r["c"] for r in counts_rows}
    counts["all"] = sum(counts.values())
    return {"jobs": [_row_to_dict(r) for r in rows], "counts": counts}


@app.post("/api/scrape")
async def scrape_sources(limit_per_source: int = 6):
    with get_conn() as conn:
        sources = conn.execute("SELECT * FROM sources WHERE enabled = 1").fetchall()

    added = 0
    skipped = 0
    errors = []

    for src in sources:
        try:
            if "topjobs.lk" in src["url"].lower() or src["source_type"] == "topjobs":
                items = await fetch_topjobs_lk(src["name"], limit=limit_per_source)
            else:
                items = await fetch_wp_json_jobs(src["name"], src["url"], limit=limit_per_source)
            for item in items:
                with get_conn() as conn:
                    exists = conn.execute(
                        "SELECT id FROM jobs WHERE source_url = ?", (item["source_url"],)
                    ).fetchone()
                if exists:
                    skipped += 1
                    continue
                _insert_and_generate(item)
                added += 1

            with get_conn() as conn:
                conn.execute(
                    "UPDATE sources SET last_fetched_at = ? WHERE id = ?",
                    (utc_now_iso(), src["id"]),
                )
        except Exception as e:
            errors.append(f"{src['name']}: {str(e)}")

    return {"added": added, "skipped": skipped, "errors": errors}


@app.post("/api/jobs/manual")
async def import_manual_job(req: ManualImportRequest):
    url = req.url.strip()
    raw_text = req.raw_text.strip()

    if not url and not raw_text:
        raise HTTPException(status_code=400, detail="Please provide either a URL or pasted job text.")

    if url and not raw_text and "facebook.com" not in url.lower():
        try:
            job_data = await fetch_single_url_job(url, source_name=req.source_name or "Manual Link")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")
    else:
        title = req.title.strip() or (raw_text.splitlines()[0][:100] if raw_text else "Job Vacancy")
        excerpt = raw_text or f"Job details at {url}"
        job_data = {
            "source_name": req.source_name or "Manual / FB Import",
            "source_url": url or f"manual://{utc_now_iso()}",
            "title_en": title,
            "company": req.company.strip(),
            "category": req.category.strip() or classify_category(title, excerpt),
            "closing_date": req.closing_date.strip() or extract_closing_date(excerpt),
            "salary": req.salary.strip() or extract_salary(excerpt),
            "location": "Sri Lanka",
            "raw_excerpt": excerpt[:2400],
        }

    # Apply any explicit overrides
    if req.title.strip():
        job_data["title_en"] = req.title.strip()
    if req.company.strip():
        job_data["company"] = req.company.strip()
    if req.closing_date.strip():
        job_data["closing_date"] = req.closing_date.strip()
    if req.salary.strip():
        job_data["salary"] = req.salary.strip()
    if req.category.strip():
        job_data["category"] = req.category.strip()

    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM jobs WHERE source_url = ?", (job_data["source_url"],)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="This job URL is already in your queue.")

    created = _insert_and_generate(job_data)
    return {"job": created}


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: int, body: JobUpdate):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        job = _row_to_dict(row)

        fields = {
            "sinhala_post": body.sinhala_post if body.sinhala_post is not None else job["sinhala_post"],
            "card_headline_si": body.card_headline_si if body.card_headline_si is not None else job["card_headline_si"],
            "card_subline_si": body.card_subline_si if body.card_subline_si is not None else job["card_subline_si"],
            "company": body.company if body.company is not None else job["company"],
            "closing_date": body.closing_date if body.closing_date is not None else job["closing_date"],
            "salary": body.salary if body.salary is not None else job.get("salary", ""),
            "category": body.category if body.category is not None else job["category"],
        }

        conn.execute(
            """
            UPDATE jobs SET
                sinhala_post = ?, card_headline_si = ?, card_subline_si = ?,
                company = ?, closing_date = ?, salary = ?, category = ?
            WHERE id = ?
            """,
            (
                fields["sinhala_post"],
                fields["card_headline_si"],
                fields["card_subline_si"],
                fields["company"],
                fields["closing_date"],
                fields["salary"],
                fields["category"],
                job_id,
            ),
        )

    merged = {**job, **fields}
    if body.regenerate_card:
        card_path = generate_job_card(job_id, merged)
        if card_path:
            with get_conn() as conn:
                conn.execute("UPDATE jobs SET card_image_path = ? WHERE id = ?", (card_path, job_id))

    with get_conn() as conn:
        updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return {"job": _row_to_dict(updated)}


@app.post("/api/jobs/reformat-all")
def reformat_all_pending():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE status = 'pending'").fetchall()
    updated_count = 0
    for row in rows:
        job = _row_to_dict(row)
        if not job.get("salary"):
            job["salary"] = extract_salary(job.get("raw_excerpt", ""))
        formatted = format_job_sinhala(job)
        merged = {**job, **formatted}
        card_path = generate_job_card(job["id"], merged)
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE jobs SET salary = ?, sinhala_post = ?, card_headline_si = ?, card_subline_si = ?, card_image_path = ?
                WHERE id = ?
                """,
                (
                    job.get("salary", ""),
                    formatted["sinhala_post"],
                    formatted["card_headline_si"],
                    formatted["card_subline_si"],
                    card_path or job["card_image_path"],
                    job["id"],
                ),
            )
        updated_count += 1
    return {"updated": updated_count}


@app.post("/api/jobs/{job_id}/reformat")
def reformat_job(job_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        job = _row_to_dict(row)

    formatted = format_job_sinhala(job)
    merged = {**job, **formatted}
    card_path = generate_job_card(job_id, merged)

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs SET sinhala_post = ?, card_headline_si = ?, card_subline_si = ?, card_image_path = ?
            WHERE id = ?
            """,
            (
                formatted["sinhala_post"],
                formatted["card_headline_si"],
                formatted["card_subline_si"],
                card_path or job["card_image_path"],
                job_id,
            ),
        )
        updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return {"job": _row_to_dict(updated)}


@app.post("/api/jobs/{job_id}/approve-publish")
async def approve_and_publish(job_id: int, req: ApproveRequest = ApproveRequest()):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        job = _row_to_dict(row)

    settings = get_settings()
    link = "" if job["source_url"].startswith("manual://") else job["source_url"]
    img_path = job["card_image_path"] if req.include_image else ""

    res = await publish_to_facebook(
        page_id=settings["fb_page_id"],
        access_token=settings["fb_page_access_token"],
        message=job["sinhala_post"],
        link=link,
        card_image_url_path=img_path,
    )

    if not res["ok"]:
        with get_conn() as conn:
            conn.execute("UPDATE jobs SET error_message = ? WHERE id = ?", (res["error"], job_id))
        raise HTTPException(status_code=400, detail=res["error"])

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs SET status = 'published', fb_post_id = ?, error_message = '', published_at = ?
            WHERE id = ?
            """,
            (res["post_id"], utc_now_iso(), job_id),
        )
        updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    return {"job": _row_to_dict(updated)}


@app.post("/api/jobs/{job_id}/mark-published")
def mark_published_manual(job_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'published', error_message = '', published_at = ? WHERE id = ?",
            (utc_now_iso(), job_id),
        )
        updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Job not found")
    return {"job": _row_to_dict(updated)}


@app.post("/api/jobs/{job_id}/reject")
def reject_job(job_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET status = 'rejected' WHERE id = ?", (job_id,))
        updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Job not found")
    return {"job": _row_to_dict(updated)}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    return {"ok": True}


@app.get("/api/sources")
def list_sources():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sources ORDER BY id ASC").fetchall()
    return {"sources": [_row_to_dict(r) for r in rows]}


@app.post("/api/sources")
def add_source(body: SourceCreate):
    with get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO sources (name, url, source_type, enabled) VALUES (?, ?, ?, 1)",
                (body.name.strip(), body.url.strip().rstrip("/"), body.source_type),
            )
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (cur.lastrowid,)).fetchone()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"source": _row_to_dict(row)}


@app.patch("/api/sources/{source_id}")
def toggle_source(source_id: int, body: SourceToggle):
    with get_conn() as conn:
        conn.execute("UPDATE sources SET enabled = ? WHERE id = ?", (1 if body.enabled else 0, source_id))
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source not found")
    return {"source": _row_to_dict(row)}


@app.get("/api/settings")
def read_settings():
    s = get_settings()
    return {
        "fb_page_id": s["fb_page_id"],
        "fb_page_access_token_masked": (s["fb_page_access_token"][:8] + "..." + s["fb_page_access_token"][-4:]) if len(s["fb_page_access_token"]) > 14 else ("configured" if s["fb_page_access_token"] else ""),
        "has_fb_token": bool(s["fb_page_access_token"]),
        "has_gemini_key": bool(s["gemini_api_key"]),
        "page_brand_name": s["page_brand_name"],
    }


@app.post("/api/settings")
def write_settings(body: SettingsUpdate):
    updates = {}
    if body.fb_page_id is not None:
        updates["fb_page_id"] = body.fb_page_id
    if body.fb_page_access_token is not None and body.fb_page_access_token.strip() != "":
        updates["fb_page_access_token"] = body.fb_page_access_token
    if body.gemini_api_key is not None and body.gemini_api_key.strip() != "":
        updates["gemini_api_key"] = body.gemini_api_key
    if body.page_brand_name is not None:
        updates["page_brand_name"] = body.page_brand_name
    save_settings(updates)
    return read_settings()


@app.post("/api/settings/test-fb")
async def test_fb_connection():
    s = get_settings()
    res = await verify_page_token(s["fb_page_id"], s["fb_page_access_token"])
    if res.get("ok") and res.get("auto_exchanged") and res.get("page_access_token"):
        save_settings({
            "fb_page_id": res["page"]["id"],
            "fb_page_access_token": res["page_access_token"],
        })
        res.pop("page_access_token", None)
    return res


@app.get("/api/analytics")
async def get_analytics(limit: int = 15):
    s = get_settings()
    return await fetch_page_analytics(s["fb_page_id"], s["fb_page_access_token"], limit=limit)
