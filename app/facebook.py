from pathlib import Path
from typing import Dict, Optional
import httpx
from app.config import CARDS_DIR

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


async def verify_page_token(page_id: str, access_token: str) -> Dict:
    if not access_token:
        return {"ok": False, "error": "Access Token is required."}
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Check what /me returns (Page if Page Token, User if User Token)
        me_resp = await client.get(
            f"{GRAPH_API_BASE}/me",
            params={"fields": "id,name", "access_token": access_token},
        )
        me_data = me_resp.json()
        if me_resp.status_code != 200:
            err = me_data.get("error", {}).get("message", me_resp.text)
            return {"ok": False, "error": err}

        # 2. Check /me/accounts to see if this is a User Token with managed pages
        acc_resp = await client.get(
            f"{GRAPH_API_BASE}/me/accounts",
            params={"fields": "id,name,access_token", "access_token": access_token},
        )
        if acc_resp.status_code == 200:
            pages = acc_resp.json().get("data", [])
            if pages:
                target_id = page_id.strip()
                matched = next((p for p in pages if p["id"] == target_id), None)
                if matched and matched.get("access_token"):
                    return {
                        "ok": True,
                        "page": {"id": matched["id"], "name": matched["name"]},
                        "page_access_token": matched["access_token"],
                        "auto_exchanged": True,
                    }
                page_list = ", ".join(f"{p['name']} (ID: {p['id']})" for p in pages)
                return {
                    "ok": False,
                    "error": (
                        f"Page ID '{target_id}' not found under your User Token. "
                        f"Found pages: {page_list}"
                    ),
                }

        # 3. Verify the target page_id if provided
        target_id = page_id.strip() or me_data.get("id", "")
        if target_id != me_data.get("id"):
            page_resp = await client.get(
                f"{GRAPH_API_BASE}/{target_id}",
                params={"fields": "id,name", "access_token": access_token},
            )
            page_data = page_resp.json()
            if page_resp.status_code != 200:
                err = page_data.get("error", {}).get("message", page_resp.text)
                return {
                    "ok": False,
                    "error": f"{err} (Note: Token belongs to '{me_data.get('name')}' with ID {me_data.get('id')})",
                }
            return {"ok": True, "page": page_data}

        return {"ok": True, "page": me_data}


async def publish_to_facebook(
    page_id: str,
    access_token: str,
    message: str,
    link: str = "",
    card_image_url_path: str = "",
    link_in_first_comment: bool = True,
) -> Dict:
    if not page_id or not access_token:
        return {"ok": False, "error": "Facebook Page ID or Access Token is not configured in Settings."}

    full_message = message.strip()
    if link and not link_in_first_comment and link not in full_message:
        full_message = f"{full_message}\n\n🔗 {link}"

    # Check if local PNG exists
    local_img: Optional[Path] = None
    if card_image_url_path and card_image_url_path.startswith("/cards/"):
        candidate = CARDS_DIR / Path(card_image_url_path).name
        if candidate.exists():
            local_img = candidate

    async with httpx.AsyncClient(timeout=30.0) as client:
        if local_img:
            # Step 1: Upload photo unpublished so we can attach it to a real Page Feed post
            upload_url = f"{GRAPH_API_BASE}/{page_id}/photos"
            with local_img.open("rb") as f:
                files = {"source": (local_img.name, f, "image/png")}
                upload_data = {"published": "false", "access_token": access_token}
                up_resp = await client.post(upload_url, data=upload_data, files=files)
            up_json = up_resp.json()
            if up_resp.status_code != 200 or not up_json.get("id"):
                err = up_json.get("error", {}).get("message", up_resp.text)
                return {"ok": False, "error": err}

            # Step 2: Publish to /{page_id}/feed with attached_media so it appears on main Posts/All tab
            import json
            feed_url = f"{GRAPH_API_BASE}/{page_id}/feed"
            payload = {
                "message": full_message,
                "attached_media": json.dumps([{"media_fbid": up_json["id"]}]),
                "access_token": access_token,
            }
            resp = await client.post(feed_url, data=payload)
        else:
            url = f"{GRAPH_API_BASE}/{page_id}/feed"
            payload = {"message": full_message, "access_token": access_token}
            if link:
                payload["link"] = link
            resp = await client.post(url, data=payload)

        res_data = resp.json()
        if resp.status_code != 200:
            err = res_data.get("error", {}).get("message", resp.text)
            return {"ok": False, "error": err}

        post_id = res_data.get("post_id") or res_data.get("id") or ""

        # Auto-post the external link as the First Comment to preserve organic reach
        if post_id and link and link_in_first_comment:
            try:
                comment_msg = f"🔗 සම්පූර්ණ විස්තර සහ අයදුම් කිරීමට පිවිසෙන්න:\n{link}"
                await client.post(
                    f"{GRAPH_API_BASE}/{post_id}/comments",
                    data={"message": comment_msg, "access_token": access_token},
                )
            except Exception:
                pass

        return {"ok": True, "post_id": post_id}


async def publish_via_webhook(
    webhook_url: str,
    message: str,
    link: str = "",
    card_image_url_path: str = "",
    title: str = "",
) -> Dict:
    if not webhook_url:
        return {"ok": False, "error": "Webhook URL is not configured."}

    first_comment = f"🔗 සම්පූර්ණ විස්තර සහ අයදුම් කිරීමට පිවිසෙන්න:\n{link}" if link else ""
    data = {
        "title": title,
        "message": message.strip(),
        "first_comment": first_comment,
        "link": link,
    }

    local_img: Optional[Path] = None
    if card_image_url_path and card_image_url_path.startswith("/cards/"):
        candidate = CARDS_DIR / Path(card_image_url_path).name
        if candidate.exists():
            local_img = candidate

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if local_img:
                with local_img.open("rb") as f:
                    files = {"photo": (local_img.name, f, "image/png")}
                    resp = await client.post(webhook_url, data=data, files=files)
            else:
                resp = await client.post(webhook_url, data=data)

        if resp.status_code >= 400:
            return {"ok": False, "error": f"Webhook returned HTTP {resp.status_code}: {resp.text[:200]}"}
        return {"ok": True, "post_id": f"webhook:{resp.status_code}"}
    except Exception as e:
        return {"ok": False, "error": f"Webhook error: {e}"}


async def fetch_page_analytics(page_id: str, access_token: str, limit: int = 15) -> Dict:
    if not page_id or not access_token:
        return {"ok": False, "error": "Facebook Page ID or Access Token is not configured in Settings."}

    fields = "id,message,created_time,permalink_url,full_picture,shares,reactions.summary(total_count),comments.summary(total_count)"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            # 1. Page profile info (followers, fans)
            page_resp = await client.get(
                f"{GRAPH_API_BASE}/{page_id}",
                params={"fields": "id,name,fan_count,followers_count", "access_token": access_token},
            )
            page_info = page_resp.json() if page_resp.status_code == 200 else {}

            # 2. Page-level 28-day daily insights (views, engagements, profile views, follows)
            page_insights = {
                "views_28d": 0,
                "engagements_28d": 0,
                "profile_views_28d": 0,
                "new_follows_28d": 0,
                "daily_series": [],
            }
            ins_resp = await client.get(
                f"{GRAPH_API_BASE}/{page_id}/insights",
                params={
                    "metric": "page_media_view,page_post_engagements,page_views_total,page_daily_follows_unique",
                    "period": "day",
                    "access_token": access_token,
                },
            )
            if ins_resp.status_code == 200:
                daily_map: Dict[str, Dict] = {}
                for item in ins_resp.json().get("data", []):
                    name = item.get("name")
                    for val_obj in item.get("values", []):
                        day = (val_obj.get("end_time") or "")[:10]
                        v = val_obj.get("value") or 0
                        if not isinstance(v, (int, float)):
                            v = 0
                        if day not in daily_map:
                            daily_map[day] = {"date": day, "views": 0, "engagements": 0}
                        if name == "page_media_view":
                            page_insights["views_28d"] += int(v)
                            daily_map[day]["views"] = int(v)
                        elif name == "page_post_engagements":
                            page_insights["engagements_28d"] += int(v)
                            daily_map[day]["engagements"] = int(v)
                        elif name == "page_views_total":
                            page_insights["profile_views_28d"] += int(v)
                        elif name == "page_daily_follows_unique":
                            page_insights["new_follows_28d"] += int(v)
                page_insights["daily_series"] = sorted(daily_map.values(), key=lambda x: x["date"])[-14:]

            # 3. Recent posts + per-post views & clicks
            resp = await client.get(
                f"{GRAPH_API_BASE}/{page_id}/posts",
                params={"fields": fields, "limit": limit, "access_token": access_token},
            )
            data = resp.json()
            if resp.status_code != 200:
                err = data.get("error", {}).get("message", resp.text)
                return {"ok": False, "error": err}

            posts = []
            totals = {"posts": 0, "views": 0, "clicks": 0, "reactions": 0, "comments": 0, "shares": 0}
            for p in data.get("data", []):
                reactions = p.get("reactions", {}).get("summary", {}).get("total_count", 0)
                comments = p.get("comments", {}).get("summary", {}).get("total_count", 0)
                shares = p.get("shares", {}).get("count", 0)
                views = 0
                clicks = 0

                try:
                    p_ins = await client.get(
                        f"{GRAPH_API_BASE}/{p['id']}/insights",
                        params={"metric": "post_media_view,post_clicks", "access_token": access_token},
                    )
                    if p_ins.status_code == 200:
                        for m in p_ins.json().get("data", []):
                            m_val = m.get("values", [{}])[0].get("value", 0)
                            if not isinstance(m_val, (int, float)):
                                m_val = 0
                            if m.get("name") == "post_media_view":
                                views = int(m_val)
                            elif m.get("name") == "post_clicks":
                                clicks = int(m_val)
                except Exception:
                    pass

                totals["posts"] += 1
                totals["views"] += views
                totals["clicks"] += clicks
                totals["reactions"] += reactions
                totals["comments"] += comments
                totals["shares"] += shares

                engagement_total = reactions + comments + shares + clicks
                eng_rate = round((engagement_total / views) * 100, 1) if views > 0 else 0.0

                posts.append(
                    {
                        "id": p.get("id", ""),
                        "message": (p.get("message") or "")[:180],
                        "created_time": p.get("created_time", ""),
                        "permalink_url": p.get("permalink_url", ""),
                        "full_picture": p.get("full_picture", ""),
                        "views": views,
                        "clicks": clicks,
                        "reactions": reactions,
                        "comments": comments,
                        "shares": shares,
                        "engagement_rate": eng_rate,
                    }
                )

            return {
                "ok": True,
                "page": {
                    "name": page_info.get("name", ""),
                    "followers": page_info.get("followers_count", 0),
                    "fans": page_info.get("fan_count", 0),
                },
                "page_insights": page_insights,
                "totals": totals,
                "posts": posts,
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}
