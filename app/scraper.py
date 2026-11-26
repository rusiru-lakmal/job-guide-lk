import asyncio
import html
import json
import re
from typing import Dict, List
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_html_text(raw_html: str, max_chars: int = 1200) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    if len(cleaned) > max_chars:
        return cleaned[:max_chars].rsplit(" ", 1)[0] + "..."
    return cleaned


def extract_company(title: str) -> str:
    # Common patterns on gazette.lk & hellojobs.lk:
    # "Role - Company Vacancies 2026" or "Role – Company Job Vacancies 2026"
    parts = re.split(r"\s+[–—-]\s+", title, maxsplit=1)
    if len(parts) == 2:
        company_part = parts[1]
        company_part = re.sub(
            r"\b(Job\s+Vacancies|Vacancies|Careers|Recruitment|Jobs|202\d)\b",
            "",
            company_part,
            flags=re.IGNORECASE,
        )
        company_part = re.sub(r"\s+", " ", company_part).strip(" -–—,.")
        if company_part:
            return company_part
    return ""


def extract_closing_date(text: str) -> str:
    patterns = [
        r"(?:Closing\s*Date|Last\s*Date|Deadline|Apply\s*Before|අවසන්\s*දිනය)\s*[:\-–]?\s*([A-Za-z0-9,.\s/\-]{4,35})",
        r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+202\d)",
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+202\d)",
        r"(202\d[-/.]\d{1,2}[-/.]\d{1,2})",
        r"(\d{1,2}[-/.]\d{1,2}[-/.]202\d)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            val = re.sub(r"\s+", " ", match.group(1)).strip(" .,-:")
            # Keep it concise
            if len(val) > 32:
                val = val[:32].rsplit(" ", 1)[0]
            if val:
                return val
    return ""


def extract_salary(text: str) -> str:
    patterns = [
        r"(?:Salary|Remuneration|Pay\s*Scale|Basic\s*Salary|Monthly\s*Salary|වැටුප)\s*[:\-–]?\s*((?:Rs\.?|LKR|රු\.?)\s*[\d,]+(?:\.\d{2})?(?:\s*[-–to]+\s*(?:Rs\.?|LKR|රු\.?)?\s*[\d,]+(?:\.\d{2})?)?(?:\s*(?:per\s*month|monthly|/|p\.m\.|upwards|\+))?)",
        r"((?:Rs\.?|LKR)\s*[\d,]{4,}(?:\.\d{2})?(?:\s*[-–to]+\s*(?:Rs\.?|LKR)?\s*[\d,]{4,}(?:\.\d{2})?)?(?:\s*(?:per\s*month|monthly|upwards|\+))?)",
        r"(?:Salary|Remuneration|Pay\s*Scale)\s*[:\-–]\s*([A-Za-z0-9\s,.\-/]{4,45})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            val = re.sub(r"\s+", " ", match.group(1)).strip(" .,-:")
            if len(val) > 45:
                val = val[:45].rsplit(" ", 1)[0]
            if val and any(ch.isdigit() for ch in val):
                return val
    return ""


def classify_category(title: str, text: str) -> str:
    combined = f"{title} {text[:400]}".lower()
    if any(k in combined for k in ("ministry", "government", "gazette", "university", "department", "pradeshiya", "provincial", "municipal", "authority", "board of investment", "institute")):
        return "Government"
    if any(k in combined for k in ("bank", "finance", "leasing", "insurance", "credit")):
        return "Banking & Finance"
    if any(k in combined for k in ("software", "developer", "engineer", "network", "firewall", "ict", "data analyst", "devops", "qa ")):
        return "IT & Engineering"
    return "Private"


async def _curl_get_json(url: str) -> List[Dict]:
    proc = await asyncio.create_subprocess_exec(
        "curl", "-sL", "-m", "20", "-A", HEADERS["User-Agent"], "-H", "Accept: application/json", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="ignore") or f"curl failed with {proc.returncode}")
    return json.loads(stdout.decode("utf-8"))


async def fetch_wp_json_jobs(source_name: str, base_url: str, limit: int = 8) -> List[Dict]:
    api_url = f"{base_url.rstrip('/')}/wp-json/wp/v2/posts?per_page={limit}"
    posts = None
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=HEADERS) as client:
        resp = await client.get(api_url)
        if resp.status_code == 200:
            posts = resp.json()
        elif resp.status_code in (403, 406, 429):
            posts = await _curl_get_json(api_url)
        else:
            resp.raise_for_status()

    results = []
    for post in posts:
        raw_title = html.unescape(post.get("title", {}).get("rendered", "")).strip()
        link = post.get("link", "").strip()
        if not raw_title or not link:
            continue

        # Skip weekly gazette PDF roundups if desired? No, keep them as they are popular on gazette.lk!
        content_html = post.get("content", {}).get("rendered", "") or post.get("excerpt", {}).get("rendered", "")
        excerpt = clean_html_text(content_html, max_chars=2400)
        company = extract_company(raw_title)
        closing_date = extract_closing_date(excerpt)
        salary = extract_salary(excerpt)
        category = classify_category(raw_title, excerpt)

        results.append(
            {
                "source_name": source_name,
                "source_url": link,
                "title_en": raw_title,
                "company": company,
                "category": category,
                "closing_date": closing_date,
                "salary": salary,
                "location": "Sri Lanka",
                "raw_excerpt": excerpt,
            }
        )
    return results


async def fetch_topjobs_lk(source_name: str = "TopJobs.lk", limit: int = 8) -> List[Dict]:
    url = "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?jst=OPEN"
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=HEADERS) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    rows = soup.select('tr[id^="tr"]')
    for idx, row in enumerate(rows[:limit]):
        tds = row.find_all("td")
        if len(tds) < 6:
            continue

        h2 = row.find("h2")
        h1 = row.find("h1")
        role = h2.get_text(" ", strip=True) if h2 else ""
        company = h1.get_text(" ", strip=True) if h1 else ""
        if not role:
            continue

        jc_el = row.select_one('span[id^="hdnJC"]')
        ec_el = row.select_one('span[id^="hdnEC"]')
        ac_el = row.select_one('span[id^="hdnAC"]')
        jc = jc_el.get_text(strip=True) if jc_el else ""
        ec = ec_el.get_text(strip=True) if ec_el else "DEFZZZ"
        ac = ac_el.get_text(strip=True) if ac_el else "DEFZZZ"

        job_link = (
            f"https://www.topjobs.lk/employer/JobAdvertismentServlet"
            f"?rid={idx}&ac={ac}&jc={jc}&ec={ec}&pg=applicant/vacancybyfunctionalarea.jsp"
            if jc
            else url
        )

        desc = " ".join(tds[3].get_text(" ", strip=True).split()) if len(tds) > 3 else ""
        closing_date = " ".join(tds[5].get_text(" ", strip=True).split()) if len(tds) > 5 else ""
        location = (" ".join(tds[6].get_text(" ", strip=True).split()) if len(tds) > 6 else "") or "Sri Lanka"
        title_en = f"{role} - {company}" if company else role

        excerpt = desc if desc and desc.lower() != "please refer the vacancy" else f"{role} vacancy at {company} ({location})."
        results.append(
            {
                "source_name": source_name,
                "source_url": job_link,
                "title_en": title_en,
                "company": company,
                "category": classify_category(title_en, excerpt),
                "closing_date": closing_date,
                "salary": extract_salary(excerpt),
                "location": location,
                "raw_excerpt": excerpt,
            }
        )
    return results


async def fetch_single_url_job(url: str, source_name: str = "Manual Link") -> Dict:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=HEADERS) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    og_title = soup.find("meta", property="og:title")
    title = (og_title["content"].strip() if og_title and og_title.get("content") else "") or (
        soup.title.string.strip() if soup.title and soup.title.string else url
    )
    title = html.unescape(title)

    main_el = soup.find("article") or soup.find("main") or soup.body
    excerpt = clean_html_text(str(main_el) if main_el else resp.text, max_chars=2400)

    return {
        "source_name": source_name,
        "source_url": url,
        "title_en": title,
        "company": extract_company(title),
        "category": classify_category(title, excerpt),
        "closing_date": extract_closing_date(excerpt),
        "salary": extract_salary(excerpt),
        "location": "Sri Lanka",
        "raw_excerpt": excerpt,
    }
