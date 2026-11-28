"""Outbound proactive alert dispatcher (Telegram Bot API + HMAC Webhook)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

import requests

from ecomreview.db.database import DatabaseManager
from ecomreview.security import scrub_pii, validate_webhook_url

logger = logging.getLogger(__name__)

VALID_WEBHOOK_FORMATS = {"generic", "slack", "lark", "zalo_oa"}


def format_webhook_payload(
    webhook_format: str,
    *,
    scenario_tag: str,
    shop_name: str,
    severity: str,
    title: str,
    clean_message: str,
    payload: dict[str, Any],
    recipient_id: str = "",
) -> dict[str, Any]:
    """Format an outbound alert payload for Generic, Slack, Lark, or Zalo OA webhooks."""
    fmt = str(webhook_format or "generic").strip().lower()
    safe_title = scrub_pii(title)
    safe_msg = scrub_pii(clean_message)
    safe_shop = scrub_pii(shop_name)

    if fmt == "slack":
        header = f"[{severity}] {safe_shop} — {safe_title}"
        return {
            "text": f"{header}\n{safe_msg}",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": header[:140]}},
                {"type": "section", "text": {"type": "mrkdwn", "text": safe_msg[:2800]}},
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"Shop: `{scenario_tag}` • Mức độ: *{severity}*"}
                    ],
                },
            ],
        }

    if fmt == "lark":
        tpl_color = (
            "red"
            if severity.upper() == "HIGH"
            else ("orange" if severity.upper() == "MEDIUM" else "blue")
        )
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "template": tpl_color,
                    "title": {
                        "tag": "plain_text",
                        "content": f"[{severity}] {safe_shop} — {safe_title}"[:120],
                    },
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": safe_msg[:2800]}},
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"EcomReview AI • {scenario_tag}"}
                        ],
                    },
                ],
            },
        }

    if fmt == "zalo_oa":
        out: dict[str, Any] = {
            "event_name": "ecomreview_alert",
            "shop": scenario_tag,
            "shop_name": safe_shop,
            "severity": severity,
            "title": safe_title,
            "message": safe_msg,
            "data": payload,
        }
        if recipient_id.strip():
            out["recipient"] = {"user_id": recipient_id.strip()}
        return out

    return {
        "shop": scenario_tag,
        "shop_name": safe_shop,
        "severity": severity,
        "title": safe_title,
        "message": safe_msg,
        "data": payload,
    }


def _sign_webhook_payload(secret: str, body_bytes: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()


def send_telegram_message(bot_token: str, chat_id: str, text: str, timeout: int = 8) -> dict:
    """Send a plain/markdown message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": str(chat_id).strip(),
            "text": text[:3900],
            "disable_web_page_preview": True,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def send_webhook_alert(
    webhook_url: str,
    payload: dict[str, Any],
    secret: str = "",
    timeout: int = 8,
) -> dict[str, Any]:
    """Send a JSON alert payload to a custom webhook (Zalo OA/n8n/Slack/Lark)."""
    safe_url = validate_webhook_url(webhook_url)
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if secret:
        headers["X-EcomReview-Signature"] = _sign_webhook_payload(secret, body_bytes)
    resp = requests.post(
        safe_url,
        data=body_bytes,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,
    )
    resp.raise_for_status()
    return {"status_code": resp.status_code}


def _resolve_alert_config(
    db: DatabaseManager, scenario_tag: str
) -> tuple[str, dict[str, Any], str]:
    """Load shop display name, alert_config, and webhook secret (with env fallback)."""
    shop = db.get_pilot_shop(scenario_tag, include_secret=True)
    shop_name = shop["name"] if shop else scenario_tag
    cfg = dict(shop.get("alert_config") or {}) if shop else {}
    secret = str(shop.get("webhook_secret") or "") if shop else ""

    if not cfg.get("telegram_bot_token") and os.getenv("TELEGRAM_BOT_TOKEN"):
        cfg["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not cfg.get("telegram_chat_id") and os.getenv("TELEGRAM_CHAT_ID"):
        cfg["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not cfg.get("webhook_url") and os.getenv("ECOMREVIEW_ALERT_WEBHOOK_URL"):
        cfg["webhook_url"] = os.getenv("ECOMREVIEW_ALERT_WEBHOOK_URL", "").strip()
    return shop_name, cfg, secret


def dispatch_alert(
    db: DatabaseManager,
    scenario_tag: str,
    dedup_key: str,
    severity: str,
    title: str,
    message_text: str,
    payload: dict[str, Any],
    force: bool = False,
) -> list[dict[str, Any]]:
    """Dispatch an alert to configured channels (Telegram / Webhook) with deduplication."""
    shop_name, cfg, secret = _resolve_alert_config(db, scenario_tag)
    clean_message = scrub_pii(message_text)
    full_text = f"[{severity}] {shop_name} — {title}\n{clean_message}"

    results: list[dict[str, Any]] = []
    channels: list[tuple[str, Any]] = []
    if cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
        channels.append(("telegram", (cfg["telegram_bot_token"], cfg["telegram_chat_id"])))
    if cfg.get("webhook_url"):
        channels.append(("webhook", cfg["webhook_url"]))

    for channel_name, target in channels:
        ch_dedup = f"{dedup_key}:{channel_name}"
        if not force and db.has_alert_dispatch(ch_dedup):
            results.append({"channel": channel_name, "status": "skipped_duplicate"})
            continue

        status_val = "SENT"
        err_msg = None
        try:
            if channel_name == "telegram":
                bot_tok, chat_id = target
                send_telegram_message(bot_tok, chat_id, full_text)
            elif channel_name == "webhook":
                wh_format = str(cfg.get("webhook_format") or "generic").strip().lower()
                zalo_rcpt = str(cfg.get("zalo_oa_recipient_id") or "").strip()
                formatted_body = format_webhook_payload(
                    wh_format,
                    scenario_tag=scenario_tag,
                    shop_name=shop_name,
                    severity=severity,
                    title=title,
                    clean_message=clean_message,
                    payload=payload,
                    recipient_id=zalo_rcpt,
                )
                send_webhook_alert(target, formatted_body, secret=secret)
        except Exception as exc:
            status_val = "FAILED"
            err_msg = str(exc)[:300]
            logger.warning("Alert dispatch failed (%s -> %s): %s", scenario_tag, channel_name, exc)

        dispatch_id = db.record_alert_dispatch(
            scenario_tag=scenario_tag,
            dedup_key=ch_dedup if not force else f"{ch_dedup}:{os.urandom(4).hex()}",
            channel=channel_name,
            severity=severity,
            title=title,
            payload=payload,
            status=status_val,
            error_message=err_msg,
        )
        results.append(
            {
                "dispatch_id": dispatch_id,
                "channel": channel_name,
                "status": status_val,
                "error": err_msg,
            }
        )

    return results


def notify_critical_reviews(
    db: DatabaseManager,
    scenario_tag: str,
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Send proactive alerts for severe negative reviews (default rating <= 2)."""
    _, cfg, _ = _resolve_alert_config(db, scenario_tag)
    if cfg.get("enable_critical_review_alert", True) is False:
        return []
    max_rating = int(cfg.get("min_rating_alert", 2))
    all_results: list[dict[str, Any]] = []

    for item in reviews:
        rating = int(item.get("rating") or 5)
        if rating > max_rating:
            continue
        rid = str(item.get("review_id") or "")
        text = scrub_pii(str(item.get("text") or item.get("text_raw") or ""))
        platform = str(item.get("platform") or "shopee").upper()
        product = str(item.get("product") or "")
        res = dispatch_alert(
            db=db,
            scenario_tag=scenario_tag,
            dedup_key=f"critical_review:{scenario_tag}:{rid}",
            severity="HIGH" if rating == 1 else "MEDIUM",
            title=f"Đánh giá {rating}★ mới trên {platform} (#{rid})",
            message_text=f"Sản phẩm: {product}\nNội dung: {text[:260]}",
            payload={
                "type": "critical_review",
                "review_id": rid,
                "rating": rating,
                "platform": platform.lower(),
                "product": product,
            },
        )
        all_results.extend(res)
    return all_results


def notify_trend_alerts(
    db: DatabaseManager,
    scenario_tag: str,
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Send proactive alerts for statistical Z-test spikes detected after analysis."""
    _, cfg, _ = _resolve_alert_config(db, scenario_tag)
    if cfg.get("enable_ztest_alert", True) is False:
        return []
    all_results: list[dict[str, Any]] = []
    for al in alerts:
        aspect = str(al.get("aspect") or "ALL")
        latest_period = str(al.get("latest_period") or "latest")
        severity = str(al.get("severity") or "MEDIUM").upper()
        delta = al.get("delta_pp", 0)
        latest_pct = al.get("latest_neg_pct", 0)
        base_pct = al.get("baseline_neg_pct", 0)
        res = dispatch_alert(
            db=db,
            scenario_tag=scenario_tag,
            dedup_key=f"ztest:{scenario_tag}:{aspect}:{latest_period}",
            severity=severity,
            title=f"Đột biến phàn nàn khía cạnh {aspect} (+{delta} điểm %)",
            message_text=(
                f"Kỳ {latest_period}: tỷ lệ tiêu cực tăng từ {base_pct}% lên {latest_pct}% "
                f"(p={al.get('p_value')}). Vui lòng kiểm tra lô hàng & phản hồi CSKH."
            ),
            payload={"type": "ztest_spike", **al},
        )
        all_results.extend(res)
    return all_results


# CreBy: MenBoyBMN
