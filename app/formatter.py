import json
import re
from typing import Dict
from app.config import get_settings

CATEGORY_SI_MAP = {
    "Government": "රජයේ රැකියා ඇබෑර්තු",
    "Banking & Finance": "බැංකු සහ මූල්‍ය රැකියා",
    "IT & Engineering": "IT සහ ඉංජිනේරු රැකියා",
    "Private": "පෞද්ගලික අංශයේ රැකියා",
    "General": "නව රැකියා ඇබෑර්තු",
}


def category_to_sinhala(category: str) -> str:
    return CATEGORY_SI_MAP.get(category, "නව රැකියා ඇබෑර්තු")


def _clean_role_title(title_en: str) -> str:
    parts = re.split(r"\s+[–—-]\s+", title_en, maxsplit=1)
    role = parts[0].strip()
    role = re.sub(r"\b(Job\s+Vacancies|Vacancies|202\d)\b", "", role, flags=re.IGNORECASE).strip(" -–—,.")
    return role or title_en


def _build_template_sinhala(job: Dict) -> Dict[str, str]:
    cat_si = category_to_sinhala(job.get("category", "General"))
    title_en = job.get("title_en", "").strip()
    role_part = _clean_role_title(title_en)
    company = job.get("company", "").strip() or "ශ්‍රී ලංකාවේ ප්‍රමුඛ ආයතනයක්"
    closing = job.get("closing_date", "").strip() or "වෙබ් අඩවියේ සඳහන් දිනය දක්වා"
    source_url = job.get("source_url", "").strip()
    excerpt = job.get("raw_excerpt", "").strip()

    # Take first 2-3 concise sentences/lines from excerpt for summary
    summary_lines = [line.strip() for line in excerpt.splitlines() if len(line.strip()) > 20][:3]
    summary_block = "\n".join(f"• {line[:180]}" for line in summary_lines) if summary_lines else "• සුදුසුකම් සහ වැඩිදුර විස්තර පහත ලින්ක් එකෙන් බලන්න."

    post_lines = [
        f"📢 {cat_si} | 2026",
        "",
        f"💼 තනතුරු: {role_part}",
        f"🏢 ආයතනය: {company}",
        f"📍 ස්ථානය: {job.get('location') or 'Sri Lanka'}",
        f"📅 අයදුම් කිරීමේ අවසන් දිනය: {closing}",
        "",
        "📝 කෙටි විස්තරය:",
        summary_block,
        "",
        f"👉 සම්පූර්ණ විස්තර සහ අයදුම් කිරීමට පිවිසෙන්න:",
        f"🔗 {source_url}" if source_url else "",
        "",
        "👍 මෙම රැකියා අවස්ථාව ඔබේ මිතුරන්ටත් Share කරන්න!",
        "#SriLankaJobs #JobsInSriLanka #රැකියා #SriLankaVacancies #JobNewsSL",
    ]
    sinhala_post = "\n".join(line for line in post_lines if line is not None).strip()

    card_headline_si = f"{role_part}"
    if len(card_headline_si) > 72:
        card_headline_si = card_headline_si[:69].rsplit(" ", 1)[0] + "..."

    card_subline_si = f"{company} හි නව රැකියා ඇබෑර්තු" if job.get("company") else cat_si

    return {
        "sinhala_post": sinhala_post,
        "card_headline_si": card_headline_si,
        "card_subline_si": card_subline_si,
    }


def format_job_sinhala(job: Dict) -> Dict[str, str]:
    settings = get_settings()
    api_key = settings.get("gemini_api_key", "")
    if not api_key:
        return _build_template_sinhala(job)

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = f"""
You are a Sri Lankan Sinhala Facebook Job Page editor.
Convert the following job vacancy into a clean, attractive, trustworthy Sinhala Facebook post and short job card text.
Keep job role titles, company names, and technical terms natural (English or Sinhala+English mix as Sri Lankans read), while writing all headings, explanations, and call-to-action in natural Sinhala Unicode.

Job Data:
- Title: {job.get('title_en')}
- Company: {job.get('company')}
- Category: {job.get('category')}
- Closing Date: {job.get('closing_date')}
- Source URL: {job.get('source_url')}
- Details Excerpt: {job.get('raw_excerpt', '')[:1000]}

Return ONLY valid JSON with these exact 3 keys:
{{
  "sinhala_post": "Full formatted Facebook post in Sinhala with emojis, bullet points, the source URL, and 4-5 relevant hashtags",
  "card_headline_si": "Short punchy headline for the image card (max 65 chars)",
  "card_subline_si": "Short 1-line Sinhala subtitle for the image card (max 70 chars)"
}}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        parsed = json.loads(response.text)
        if parsed.get("sinhala_post") and parsed.get("card_headline_si"):
            return {
                "sinhala_post": str(parsed["sinhala_post"]).strip(),
                "card_headline_si": str(parsed["card_headline_si"]).strip(),
                "card_subline_si": str(parsed.get("card_subline_si", "")).strip(),
            }
    except Exception:
        pass

    return _build_template_sinhala(job)
