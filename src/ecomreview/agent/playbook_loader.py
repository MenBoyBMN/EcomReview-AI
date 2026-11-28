"""Multi-industry domain Playbook & per-shop Brand Voice loader."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from ecomreview.db.database import DatabaseManager

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAYBOOK_PATH = _PROJECT_ROOT / "knowledge" / "playbook_aomua.yaml"
TEMPLATES_DIR = _PROJECT_ROOT / "knowledge" / "templates"

INDUSTRY_REGISTRY: dict[str, dict[str, Any]] = {
    "raincoat": {
        "display_name": "Áo mưa & Đồ đi mưa",
        "path": DEFAULT_PLAYBOOK_PATH,
    },
    "fashion": {
        "display_name": "Thời trang & May mặc",
        "path": TEMPLATES_DIR / "fashion.yaml",
    },
    "cosmetics": {
        "display_name": "Mỹ phẩm & Chăm sóc da",
        "path": TEMPLATES_DIR / "cosmetics.yaml",
    },
    "home_living": {
        "display_name": "Gia dụng & Đời sống",
        "path": TEMPLATES_DIR / "home_living.yaml",
    },
    "electronics": {
        "display_name": "Phụ kiện & Điện tử",
        "path": TEMPLATES_DIR / "electronics.yaml",
    },
}

_INDUSTRY_ALIASES: dict[str, str] = {
    "ao_mua": "raincoat",
    "aomua": "raincoat",
    "raincoat": "raincoat",
    "thoi_trang": "fashion",
    "fashion": "fashion",
    "my_pham": "cosmetics",
    "cosmetics": "cosmetics",
    "beauty": "cosmetics",
    "gia_dung": "home_living",
    "home_living": "home_living",
    "home": "home_living",
    "dien_tu": "electronics",
    "phu_kien": "electronics",
    "electronics": "electronics",
}


def normalize_industry(industry: str | None) -> str:
    """Normalize an industry slug/alias into a supported template key."""
    key = str(industry or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _INDUSTRY_ALIASES.get(key, "raincoat")


def resolve_playbook_path(industry: str | None = None) -> Path:
    """Resolve YAML playbook path for a given industry key."""
    norm = normalize_industry(industry)
    entry = INDUSTRY_REGISTRY.get(norm) or INDUSTRY_REGISTRY["raincoat"]
    path = Path(entry["path"])
    return path if path.exists() else DEFAULT_PLAYBOOK_PATH


def list_industry_templates() -> list[dict[str, Any]]:
    """Return metadata for all available industry playbook templates."""
    items: list[dict[str, Any]] = []
    for ind_key, meta in INDUSTRY_REGISTRY.items():
        path = Path(meta["path"])
        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                logger.warning("Failed loading industry template %s: %s", path, exc)
        items.append(
            {
                "industry": ind_key,
                "display_name": str(data.get("display_name") or meta["display_name"]),
                "domain": str(data.get("domain") or f"{ind_key}_ecommerce_vn"),
                "rules_count": len(data.get("playbook_rules") or []),
                "aspect_labels": dict(data.get("aspect_labels") or {}),
            }
        )
    return items


def load_shop_playbook(
    db: DatabaseManager | None = None,
    scenario_tag: str | None = None,
    industry: str | None = None,
    playbook_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load effective playbook YAML + shop brand voice profile without touching RO tables."""
    shop_info: dict[str, Any] | None = None
    if db is not None and scenario_tag:
        try:
            shop_info = db.get_pilot_shop(scenario_tag, include_secret=False)
        except Exception as exc:
            logger.debug("Skipping pilot_shops lookup for %s: %s", scenario_tag, exc)

    raw_ind = industry or (shop_info.get("industry") if shop_info else None) or "raincoat"
    eff_industry = normalize_industry(raw_ind)

    if playbook_path is not None:
        pb_obj = Path(playbook_path)
        resolved = pb_obj if pb_obj.is_absolute() else (_PROJECT_ROOT / pb_obj)
    else:
        resolved = resolve_playbook_path(eff_industry)

    data: dict[str, Any] = {}
    if resolved.exists():
        try:
            data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("Failed loading playbook %s: %s", resolved, exc)

    alert_cfg = dict((shop_info or {}).get("alert_config") or {})
    raw_bv = alert_cfg.get("brand_voice")
    brand_voice = dict(raw_bv) if isinstance(raw_bv, dict) else {}

    guardrails = dict(data.get("guardrails") or {})
    merged_overclaim = list(guardrails.get("overclaim_keywords") or [])
    existing_lower = {str(k).lower() for k in merged_overclaim}
    for kw in brand_voice.get("custom_overclaim_keywords") or []:
        kw_s = str(kw).strip()
        if kw_s and kw_s.lower() not in existing_lower:
            merged_overclaim.append(kw_s)
            existing_lower.add(kw_s.lower())
    guardrails["overclaim_keywords"] = merged_overclaim
    data["guardrails"] = guardrails
    data["industry"] = eff_industry
    data["_resolved_path"] = str(resolved)
    data["shop_profile"] = {
        "shop_name": str((shop_info or {}).get("name") or scenario_tag or ""),
        "industry": eff_industry,
        "brand_voice": brand_voice,
    }
    return data


# CreBy: MenBoyBMN
