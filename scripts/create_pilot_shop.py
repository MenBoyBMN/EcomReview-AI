"""CLI tool to onboard a new Pilot shop and create Owner/CSKH accounts in seconds."""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ecomreview.api.auth import hash_password  # noqa: E402
from ecomreview.db.database import DatabaseManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Onboard a Pilot shop and provision Owner / CSKH accounts."
    )
    parser.add_argument(
        "--slug", required=True, help="Shop slug (maps to scenario_tag), e.g. shop_abc"
    )
    parser.add_argument("--name", required=True, help="Display name of the shop")
    parser.add_argument(
        "--industry", default="raincoat", help="Industry profile (default: raincoat)"
    )
    parser.add_argument("--owner-email", required=True, help="Owner login email")
    parser.add_argument("--owner-name", default="Chủ gian hàng", help="Owner full name")
    parser.add_argument(
        "--owner-password", default="", help="Owner password (auto-generated if empty)"
    )
    parser.add_argument("--cskh-email", default="", help="Optional CSKH staff email")
    parser.add_argument("--cskh-name", default="Nhân viên CSKH", help="CSKH full name")
    parser.add_argument(
        "--cskh-password", default="", help="CSKH password (auto-generated if empty)"
    )
    parser.add_argument(
        "--admin-email", default="", help="Optional global admin email to ensure exists"
    )
    parser.add_argument(
        "--admin-password", default="", help="Admin password (auto-generated if empty)"
    )
    args = parser.parse_args()

    db = DatabaseManager()
    shop = db.create_pilot_shop(
        slug=args.slug,
        name=args.name,
        industry=args.industry,
    )
    print(f"[OK] Pilot shop ready: slug={shop['slug']} | name={shop['name']}")
    print(f"     Webhook secret: {shop['webhook_secret']}")

    owner_pw = args.owner_password.strip() or secrets.token_urlsafe(12)
    owner = db.upsert_user(
        email=args.owner_email,
        password_hash=hash_password(owner_pw),
        full_name=args.owner_name,
        role="owner",
        allowed_shops=[shop["slug"]],
    )
    print(
        f"[OK] Owner account: email={owner['email']} | password={owner_pw} "
        f"| shops={owner['allowed_shops']}"
    )

    if args.cskh_email.strip():
        cskh_pw = args.cskh_password.strip() or secrets.token_urlsafe(12)
        cskh = db.upsert_user(
            email=args.cskh_email.strip(),
            password_hash=hash_password(cskh_pw),
            full_name=args.cskh_name,
            role="cskh",
            allowed_shops=[shop["slug"]],
        )
        print(
            f"[OK] CSKH account:  email={cskh['email']} | password={cskh_pw} "
            f"| shops={cskh['allowed_shops']}"
        )

    if args.admin_email.strip():
        admin_pw = args.admin_password.strip() or secrets.token_urlsafe(14)
        admin = db.upsert_user(
            email=args.admin_email.strip(),
            password_hash=hash_password(admin_pw),
            full_name="System Admin",
            role="admin",
            allowed_shops=["*"],
        )
        print(f"[OK] Admin account: email={admin['email']} | password={admin_pw}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# CreBy: MenBoyBMN
