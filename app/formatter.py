import json
import re
from typing import Dict, List
from app.config import get_settings

CATEGORY_SI_MAP = {
    "Government": "රජයේ රැකියා ඇබෑර්තු",
    "Banking & Finance": "බැංකු සහ මූල්‍ය රැකියා",
    "IT & Engineering": "IT සහ ඉංජිනේරු රැකියා",
    "Private": "පෞද්ගලික අංශයේ රැකියා",
    "General": "නව රැකියා ඇබෑර්තු",
}

NOISE_PATTERNS = (
    "click here",
    "join whatsapp",
    "join telegram",
    "follow us",
    "share this",
    "advertisement",
    "read more",
    "subscribe",
    "view all jobs",
    "download application",
)


def category_to_sinhala(category: str) -> str:
    return CATEGORY_SI_MAP.get(category, "නව රැකියා ඇබෑර්තු")


def _clean_role_title(title_en: str) -> str:
    parts = re.split(r"\s+[–—-]\s+", title_en, maxsplit=1)
    role = parts[0].strip()
    role = re.sub(r"\b(Job\s+Vacancies|Vacancies|202\d)\b", "", role, flags=re.IGNORECASE).strip(" -–—,.")
    return role or title_en


def _extract_clean_highlights(excerpt: str, max_items: int = 3) -> List[str]:
    highlights = []
    for raw_line in excerpt.splitlines():
        line = raw_line.strip(" •-*–")
        if len(line) < 22:
            continue
        low = line.lower()
        if any(noise in low for noise in NOISE_PATTERNS):
            continue
        if len(line) > 150:
            line = line[:147].rsplit(" ", 1)[0] + "..."
        highlights.append(line)
        if len(highlights) >= max_items:
            break
    return highlights


def _build_template_sinhala(job: Dict) -> Dict[str, str]:
    cat_si = category_to_sinhala(job.get("category", "General"))
    title_en = job.get("title_en", "").strip()
    role_part = _clean_role_title(title_en)
    company = job.get("company", "").strip() or "ශ්‍රී ලංකාවේ ප්‍රමුඛ ආයතනයක්"
    closing = job.get("closing_date", "").strip() or "වෙබ් අඩවියේ සඳහන් දිනය දක්වා"
    salary = job.get("salary", "").strip()
    source_url = job.get("source_url", "").strip()
    excerpt = job.get("raw_excerpt", "").strip()

    highlights = _extract_clean_highlights(excerpt, max_items=3)
    summary_block = (
        "\n".join(f"  ✅ {line}" for line in highlights)
        if highlights
        else "  ✅ සුදුසුකම් සහ වැඩිදුර විස්තර පහත ලින්ක් එකෙන් බලන්න."
    )

    salary_line = f"💰 වැටුප (Salary): {salary} 🔥" if salary else "💰 වැටුප (Salary): ආකර්ෂණීය වැටුප් පැකේජයක්"

    post_lines = [
        f"🚨 නව රැකියා අවස්ථාවක්! | {cat_si} 🇱🇰",
        f"🔥 {company} හි නව ඇබෑර්තු දැන් විවෘතයි!",
        "",
        f"💼 තනතුර: {role_part}",
        f"🏢 ආයතනය: {company}",
        salary_line,
        f"📍 ස්ථානය: {job.get('location') or 'Sri Lanka'}",
        f"⏳ අවසන් දිනය: {closing}",
        "",
        "✨ විශේෂ කරුණු / සුදුසුකම්:",
        summary_block,
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📲 සම්පූර්ණ විස්තර සහ අයදුම් කරන ආකාරය:",
        f"👇 පහත ලින්ක් එකට පිවිසෙන්න:",
        f"🔗 {source_url}" if source_url else "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "💬 රැකියාවක් හොයන ඔබේ යාළුවන්ටත් Share කරන්න! 👍",
        "🔔 දිනපතා අලුත් රැකියා පුවත් සඳහා අපේ Page එක Follow කරන්න.",
        "",
        "#SLJobGuide #SriLankaJobs #රැකියා #JobsInSriLanka #JobVacanciesSL",
    ]
    sinhala_post = "\n".join(line for line in post_lines if line is not None).strip()

    card_headline_si = role_part
    if len(card_headline_si) > 72:
        card_headline_si = card_headline_si[:69].rsplit(" ", 1)[0] + "..."

    card_subline_si = f"{company} හි නව රැකියා අවස්ථා" if job.get("company") else cat_si

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
You are a top Sri Lankan Sinhala Facebook Job Page editor ("SL රැකියා මග - Job Guide LK").
Convert the following job vacancy into a super engaging, scroll-stopping, trustworthy Sinhala Facebook post and short job card text.
- Start with an attention-grabbing Sinhala hook line with emojis.
- Highlight Salary prominently with 💰 if salary details are available (or mention competitive package if not).
- Keep job role titles, company names, and technical terms natural (English or Sinhala+English mix as Sri Lankans read), while writing headings, summary, and call-to-action in natural Sinhala Unicode.
- End with a clear Apply Link CTA and 4-5 hashtags including #SLJobGuide.

Job Data:
- Title: {job.get('title_en')}
- Company: {job.get('company')}
- Category: {job.get('category')}
- Salary: {job.get('salary')}
- Closing Date: {job.get('closing_date')}
- Source URL: {job.get('source_url')}
- Details Excerpt: {job.get('raw_excerpt', '')[:1600]}

Return ONLY valid JSON with these exact 3 keys:
{{
  "sinhala_post": "Full attractive formatted Facebook post in Sinhala with emojis, bullet points, salary highlight, the source URL, and hashtags",
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
