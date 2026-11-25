import html
import subprocess
from pathlib import Path
from typing import Dict
from app.config import CARDS_DIR, get_settings
from app.formatter import category_to_sinhala

THEME_PALETTES = {
    "Government": {
        "bg": "linear-gradient(135deg, #064e3b 0%, #0f766e 55%, #115e59 100%)",
        "accent": "#fbbf24",
        "badge_bg": "rgba(251, 191, 36, 0.18)",
        "badge_text": "#fde68a",
    },
    "Banking & Finance": {
        "bg": "linear-gradient(135deg, #0f172a 0%, #1e3a8a 60%, #1d4ed8 100%)",
        "accent": "#38bdf8",
        "badge_bg": "rgba(56, 189, 248, 0.18)",
        "badge_text": "#bae6fd",
    },
    "IT & Engineering": {
        "bg": "linear-gradient(135deg, #1e1b4b 0%, #4338ca 55%, #0284c7 100%)",
        "accent": "#a5f3fc",
        "badge_bg": "rgba(165, 243, 252, 0.18)",
        "badge_text": "#cffafe",
    },
    "Private": {
        "bg": "linear-gradient(135deg, #18181b 0%, #334155 55%, #0f172a 100%)",
        "accent": "#34d399",
        "badge_bg": "rgba(52, 211, 153, 0.18)",
        "badge_text": "#a7f3d0",
    },
}


def generate_job_card(job_id: int, job: Dict) -> str:
    settings = get_settings()
    chrome_path = settings.get("chrome_path", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    brand_name = html.escape(settings.get("page_brand_name", "Sri Lanka Job News"))

    category = job.get("category", "General")
    palette = THEME_PALETTES.get(category, THEME_PALETTES["Private"])
    cat_si = html.escape(category_to_sinhala(category))
    headline = html.escape(job.get("card_headline_si") or job.get("title_en") or "නව රැකියා ඇබෑර්තු")
    subline = html.escape(job.get("card_subline_si") or "")
    company = html.escape(job.get("company") or "Sri Lanka")
    closing_date = html.escape(job.get("closing_date") or "වෙබ් අඩවිය බලන්න")
    source_name = html.escape(job.get("source_name") or "Job News")

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
    background: {palette['bg']};
    color: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 64px;
    position: relative;
    overflow: hidden;
  }}
  .glow-1 {{
    position: absolute;
    width: 520px;
    height: 520px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0) 70%);
    top: -120px;
    right: -120px;
  }}
  .glow-2 {{
    position: absolute;
    width: 440px;
    height: 440px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 70%);
    bottom: -100px;
    left: -100px;
  }}
  .top-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 2;
  }}
  .brand-pill {{
    background: rgba(255,255,255,0.14);
    border: 1px solid rgba(255,255,255,0.25);
    padding: 14px 28px;
    border-radius: 999px;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 0.4px;
  }}
  .cat-pill {{
    background: {palette['badge_bg']};
    border: 1.5px solid {palette['accent']};
    color: {palette['badge_text']};
    padding: 14px 28px;
    border-radius: 999px;
    font-size: 24px;
    font-weight: 700;
  }}
  .center-card {{
    background: rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 36px;
    padding: 56px;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 28px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
  }}
  .hiring-tag {{
    color: {palette['accent']};
    font-size: 26px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
  }}
  .headline {{
    font-size: 56px;
    font-weight: 800;
    line-height: 1.28;
    color: #ffffff;
    word-break: break-word;
  }}
  .subline {{
    font-size: 32px;
    line-height: 1.45;
    color: rgba(255, 255, 255, 0.88);
    font-weight: 500;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-top: 12px;
  }}
  .meta-box {{
    background: rgba(0, 0, 0, 0.24);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 22px;
    padding: 22px 26px;
  }}
  .meta-label {{
    font-size: 20px;
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 8px;
  }}
  .meta-value {{
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
  }}
  .footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 2;
    background: rgba(0, 0, 0, 0.28);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 24px;
    padding: 24px 34px;
  }}
  .cta {{
    font-size: 26px;
    font-weight: 700;
    color: {palette['accent']};
  }}
  .source {{
    font-size: 22px;
    color: rgba(255, 255, 255, 0.75);
  }}
</style>
</head>
<body>
  <div class="glow-1"></div>
  <div class="glow-2"></div>

  <div class="top-bar">
    <div class="brand-pill">🇱🇰 {brand_name}</div>
    <div class="cat-pill">{cat_si}</div>
  </div>

  <div class="center-card">
    <div class="hiring-tag">WE ARE HIRING • නව රැකියා අවස්ථා</div>
    <div class="headline">{headline}</div>
    <div class="subline">{subline}</div>
    <div class="meta-grid">
      <div class="meta-box">
        <div class="meta-label">🏢 ආයතනය / Institution</div>
        <div class="meta-value">{company}</div>
      </div>
      <div class="meta-box">
        <div class="meta-label">📅 අවසන් දිනය / Closing Date</div>
        <div class="meta-value">{closing_date}</div>
      </div>
    </div>
  </div>

  <div class="footer">
    <div class="cta">👇 සම්පූර්ණ විස්තර සහ Apply Link එක Caption එකේ!</div>
    <div class="source">via {source_name}</div>
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
            "--hide-scrollbars",
            "--window-size=1080,1080",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        html_path.unlink(missing_ok=True)
        return f"/cards/job_{job_id}.png"

    return ""
