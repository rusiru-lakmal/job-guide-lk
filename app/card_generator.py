import html
import subprocess
from pathlib import Path
from typing import Dict
from app.config import CARDS_DIR, get_settings
from app.formatter import category_to_sinhala

THEME_PALETTES = {
    "Government": {
        "top_bar": "#b91c1c",       # Bold newspaper crimson
        "banner_bg": "#0f172a",     # Deep navy pill
        "role_color": "#b91c1c",
        "accent": "#fbbf24",        # Gold text on navy
        "date_bg": "#dc2626",
    },
    "Banking & Finance": {
        "top_bar": "#1d4ed8",       # Royal blue
        "banner_bg": "#0f172a",
        "role_color": "#1e40af",
        "accent": "#fbbf24",
        "date_bg": "#b91c1c",
    },
    "IT & Engineering": {
        "top_bar": "#4338ca",       # Indigo
        "banner_bg": "#1e1b4b",
        "role_color": "#4338ca",
        "accent": "#38bdf8",
        "date_bg": "#dc2626",
    },
    "Private": {
        "top_bar": "#047857",       # Emerald
        "banner_bg": "#0f172a",
        "role_color": "#065f46",
        "accent": "#fbbf24",
        "date_bg": "#dc2626",
    },
}


def generate_job_card(job_id: int, job: Dict) -> str:
    settings = get_settings()
    chrome_path = settings.get("chrome_path", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    brand_name = html.escape(settings.get("page_brand_name", "SL රැකියා මග - Job Guide LK"))

    category = job.get("category", "General")
    palette = THEME_PALETTES.get(category, THEME_PALETTES["Private"])
    cat_si = html.escape(category_to_sinhala(category))
    headline = html.escape(job.get("card_headline_si") or job.get("title_en") or "නව රැකියා ඇබෑර්තු")
    company = html.escape(job.get("company") or "ශ්‍රී ලංකාවේ ප්‍රමුඛ ආයතනයක්")
    location = html.escape(job.get("location") or "Sri Lanka")
    closing_date = html.escape(job.get("closing_date") or "වෙබ් අඩවිය බලන්න")
    salary = html.escape((job.get("salary") or "").strip())

    salary_badge_html = (
        f'<div class="salary-pill">💰 වැටුප: {salary}</div>'
        if salary
        else ""
    )

    html_content = f"""<!DOCTYPE html>
<html lang="si">
<head>
<meta charset="UTF-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1080px;
    height: 1080px;
    font-family: 'Sinhala Sangam MN', 'Sinhala MN', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f8fafc;
    color: #0f172a;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
  }}
  /* Subtle editorial dot pattern */
  .bg-pattern {{
    position: absolute;
    inset: 0;
    background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px);
    background-size: 28px 28px;
    opacity: 0.45;
    z-index: 0;
  }}
  .top-bar {{
    background: {palette['top_bar']};
    color: #ffffff;
    padding: 26px 48px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 2;
    box-shadow: 0 6px 20px rgba(0,0,0,0.15);
  }}
  .top-cat {{
    font-size: 30px;
    font-weight: 800;
    letter-spacing: 0.3px;
  }}
  .top-brand {{
    font-size: 24px;
    font-weight: 700;
    background: rgba(0, 0, 0, 0.22);
    padding: 8px 22px;
    border-radius: 999px;
  }}
  .main-content {{
    z-index: 2;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 36px 56px;
    gap: 26px;
  }}
  .vacancies-title {{
    font-size: 74px;
    font-weight: 900;
    color: #0f172a;
    letter-spacing: -0.5px;
    line-height: 1.1;
  }}
  .vacancies-title span {{
    color: {palette['top_bar']};
  }}
  .role-headline {{
    font-size: 44px;
    font-weight: 800;
    color: {palette['role_color']};
    line-height: 1.3;
    max-width: 940px;
    word-break: break-word;
  }}
  .salary-pill {{
    background: linear-gradient(90deg, #fef08a, #fde047);
    border: 2.5px solid #ca8a04;
    color: #713f12;
    font-size: 28px;
    font-weight: 800;
    padding: 12px 34px;
    border-radius: 999px;
    box-shadow: 0 8px 20px rgba(202, 138, 4, 0.2);
  }}
  .institution-banner {{
    width: 100%;
    background: {palette['banner_bg']};
    border-radius: 36px;
    padding: 34px 44px;
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.24);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    border: 3px solid {palette['accent']};
  }}
  .inst-name {{
    font-size: 46px;
    font-weight: 800;
    color: {palette['accent']};
    line-height: 1.25;
  }}
  .inst-loc {{
    font-size: 26px;
    font-weight: 600;
    color: #e2e8f0;
  }}
  .date-row {{
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    margin-top: 6px;
  }}
  .date-line {{
    position: absolute;
    left: 0;
    right: 0;
    height: 6px;
    background: {palette['date_bg']};
    border-radius: 999px;
    z-index: 1;
  }}
  .date-pill {{
    position: relative;
    z-index: 2;
    background: {palette['date_bg']};
    color: #ffffff;
    font-size: 32px;
    font-weight: 800;
    padding: 14px 42px;
    border-radius: 16px;
    box-shadow: 0 10px 24px rgba(185, 28, 28, 0.3);
  }}
  .footer {{
    z-index: 2;
    background: #0f172a;
    color: #ffffff;
    padding: 26px 48px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    text-align: center;
  }}
  .footer-cta {{
    font-size: 26px;
    font-weight: 700;
    color: #fbbf24;
  }}
  .footer-sub {{
    font-size: 21px;
    color: #cbd5e1;
  }}
</style>
</head>
<body>
  <div class="bg-pattern"></div>

  <div class="top-bar">
    <div class="top-cat">🇱🇰 {cat_si}</div>
    <div class="top-brand">{brand_name}</div>
  </div>

  <div class="main-content">
    <div class="vacancies-title">පුරප්පාඩු <span>•</span> Vacancies</div>
    <div class="role-headline">{headline}</div>
    {salary_badge_html}

    <div class="institution-banner">
      <div class="inst-name">🏢 {company}</div>
      <div class="inst-loc">📍 {location}</div>
    </div>

    <div class="date-row">
      <div class="date-line"></div>
      <div class="date-pill">⏳ අවසන් දිනය: {closing_date}</div>
    </div>
  </div>

  <div class="footer">
    <div class="footer-cta">👇 සම්පූර්ණ විස්තර සහ අයදුම් කිරීමට Caption එකේ Link එක බලන්න</div>
    <div class="footer-sub">දිනපතා නවතම රැකියා ඇබෑර්තු සඳහා අපේ Facebook Page එක Follow කරන්න 🔔</div>
  </div>
</body>
</html>
"""

    html_path = CARDS_DIR / f"job_{job_id}.html"
    png_path = CARDS_DIR / f"job_{job_id}.png"
    html_path.write_text(html_content, encoding="utf-8")

    if Path(chrome_path).exists():
        cmd = [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--user-data-dir=/tmp/chrome-headless-profile",
            "--hide-scrollbars",
            "--window-size=1080,1080",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        html_path.unlink(missing_ok=True)
        return f"/cards/job_{job_id}.png"

    return ""
