"""Support tool: grant (or clear) a plan without Paddle. Every change is audited.

python -m scripts.set_plan someone@example.com business --by "Nino (support)"
python -m scripts.set_plan someone@example.com clear --by "Nino (support)"
"""

from __future__ import annotations

import argparse
import asyncio

from app.billing.service import set_manual_plan
from app.core.database import SessionLocal
from app.models.enums import Plan


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("email")
    parser.add_argument("plan", choices=[p.value for p in Plan] + ["clear"])
    parser.add_argument(
        "--by", required=True, help="who is making this change (recorded in the audit log)"
    )
    args = parser.parse_args()
    plan = None if args.plan == "clear" else Plan(args.plan)
    async with SessionLocal() as db:
        await set_manual_plan(db, args.email, plan, args.by)
    print(f"{args.email}: manual plan {'cleared' if plan is None else plan.value}")


if __name__ == "__main__":
    asyncio.run(main())
