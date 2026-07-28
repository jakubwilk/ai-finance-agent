"""Seed CATEGORIES/FIXED_COSTS from data/local/*.json.

Usage: uv run python scripts/seed_reference_data.py

Reads the real, gitignored data/local/categories.json and
data/local/fixed_costs.json (see docs/01-spec-data-model.md's
"Przechowywanie realnej zawartości" section) and upserts them into the
Postgres tables via the SQLAlchemy models. Safe to re-run: existing rows are
matched by name and updated in place rather than duplicated.
"""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Category, FixedCost
from finance_agent.db.session import async_session_factory

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_LOCAL_DIR = REPO_ROOT / "data" / "local"


class CategorySeed(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    type: Literal["income", "expense", "transfer"]


class FixedCostSeed(BaseModel):
    name: str
    category: str
    expected_amount: Decimal
    frequency: Literal["monthly", "quarterly", "yearly"]


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        example = path.with_suffix(".example" + path.suffix)
        raise FileNotFoundError(
            f"{path} not found. This holds real reference data and is gitignored — "
            f"create it yourself (see {example.name} for the expected shape, and "
            f"docs/01-spec-data-model.md's 'Przechowywanie realnej zawartości' section)."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_categories(data_dir: Path) -> list[CategorySeed]:
    raw = _load_json(data_dir / "categories.json")
    return [CategorySeed.model_validate(item) for item in raw]


def load_fixed_costs(data_dir: Path) -> list[FixedCostSeed]:
    raw = _load_json(data_dir / "fixed_costs.json")
    return [FixedCostSeed.model_validate(item) for item in raw]


async def upsert_categories(
    session: AsyncSession, categories: list[CategorySeed]
) -> None:
    existing = {c.name: c for c in (await session.execute(select(Category))).scalars()}

    for seed in categories:
        category = existing.get(seed.name)
        if category is None:
            session.add(Category(name=seed.name, score=seed.score, type=seed.type))
        else:
            category.score = seed.score
            category.type = seed.type

    await session.flush()


async def upsert_fixed_costs(
    session: AsyncSession, fixed_costs: list[FixedCostSeed]
) -> None:
    category_by_name = {
        c.name: c for c in (await session.execute(select(Category))).scalars()
    }
    existing = {
        fc.name: fc for fc in (await session.execute(select(FixedCost))).scalars()
    }

    for seed in fixed_costs:
        category = category_by_name.get(seed.category)
        if category is None:
            raise ValueError(
                f"Fixed cost '{seed.name}' references unknown category '{seed.category}' — "
                "add it to categories.json first."
            )

        fixed_cost = existing.get(seed.name)
        if fixed_cost is None:
            session.add(
                FixedCost(
                    name=seed.name,
                    category_id=category.id,
                    expected_amount=seed.expected_amount,
                    frequency=seed.frequency,
                )
            )
        else:
            fixed_cost.category_id = category.id
            fixed_cost.expected_amount = seed.expected_amount
            fixed_cost.frequency = seed.frequency

    await session.flush()


async def seed(session: AsyncSession, data_dir: Path = DEFAULT_DATA_LOCAL_DIR) -> None:
    await upsert_categories(session, load_categories(data_dir))
    await upsert_fixed_costs(session, load_fixed_costs(data_dir))


async def main() -> None:
    async with async_session_factory() as session:
        try:
            await seed(session)
        except Exception:
            await session.rollback()
            raise
        await session.commit()

        category_count = (await session.execute(select(Category))).scalars().all()
        fixed_cost_count = (await session.execute(select(FixedCost))).scalars().all()
        print(
            f"Seeded {len(category_count)} categories, {len(fixed_cost_count)} fixed costs."
        )


if __name__ == "__main__":
    asyncio.run(main())
