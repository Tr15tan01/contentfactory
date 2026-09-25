"""Grant or revoke platform admin (superuser) access. Audited.

python -m scripts.set_admin someone@example.com --by "Name"
python -m scripts.set_admin someone@example.com --revoke --by "Name"
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import User
from app.services import audit


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument(
        "--by", required=True, help="who is making this change (recorded in the audit log)"
    )
    args = parser.parse_args()
    async with SessionLocal() as db:
        user = (
            await db.execute(
                select(User).where(User.email == args.email.lower(), User.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"No user {args.email}")
        user.is_superuser = not args.revoke
        audit.record(
            db,
            "admin.superuser_changed",
            entity_type="user",
            entity_id=user.id,
            data={"granted": not args.revoke, "by": args.by},
        )
        await db.commit()
    print(f"{args.email}: admin {'revoked' if args.revoke else 'granted'}")


if __name__ == "__main__":
    asyncio.run(main())
