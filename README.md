# Sri Lanka Job News • Facebook Page Studio

A local web dashboard & automation pipeline to fetch Sri Lankan job vacancies, arrange them into clean **Sinhala** Facebook posts, generate branded **1080×1080 Job Card images**, and publish them to your Facebook Page after your approval.

## Features
- **Auto-Fetch Job Sources**: Pre-configured for [Gazette.lk](https://www.gazette.lk/) and [HelloJobs.lk](https://hellojobs.lk/) via WordPress REST API, plus ability to add more WordPress job sites.
- **Manual / Facebook Post Import**: Paste any URL or copy-pasted job text (e.g. from `goodjoblk` on Facebook) to format in Sinhala and generate a card.
- **Sinhala Post Formatter**:
  - Works out-of-the-box with the built-in Sinhala template formatter.
  - Optionally add a **Gemini API Key** in Settings for full AI-powered Sinhala translation & summarization.
- **Branded Job Card Generator**: Renders 1080×1080 PNG job cards with Sinhala typography using Google Chrome headless.
- **Approval Queue**: Review, edit Sinhala captions, update closing dates, regenerate cards, reject, or **Approve & Publish to Facebook**.

## Quick Start

```bash
cd /Users/rusiru/projects/news
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Then open **http://127.0.0.1:8000** in your browser.

## Connecting Your Facebook Page
1. Go to [Meta for Developers](https://developers.facebook.com/) and create an app (Business type).
2. Add the **Facebook Login** / **Pages** product and generate a **Page Access Token** with `pages_manage_posts` and `pages_read_engagement` permissions.
3. Open **Settings & Sources** in the dashboard, enter your **Facebook Page ID** and **Page Access Token**, click **Save Settings**, and test with **Test FB Connection**.
