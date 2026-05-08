from __future__ import annotations

"""
Контракт-61: Сервис рекламных размещений.
"""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdPost

logger = logging.getLogger(__name__)


class AdService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, channel_name: str, created_by: int, **kwargs) -> AdPost:
        ad = AdPost(channel_name=channel_name, created_by=created_by, **kwargs)
        self.session.add(ad)
        await self.session.commit()
        await self.session.refresh(ad)
        logger.info("📢 Реклама #%d создана: %s", ad.id, channel_name)
        return ad

    async def bulk_create(self, items: list, created_by: int) -> List[AdPost]:
        """Массовый ввод. items = list of dicts with channel_name, channel_link, cost."""
        ads = []
        for item in items:
            ad = AdPost(
                channel_name=item.get("channel_name", "—"),
                channel_link=item.get("channel_link"),
                cost=item.get("cost", 0),
                post_date=item.get("post_date"),
                created_by=created_by,
            )
            self.session.add(ad)
            ads.append(ad)
        await self.session.commit()
        for ad in ads:
            await self.session.refresh(ad)
        logger.info("📢 Массовый ввод: %d записей", len(ads))
        return ads

    async def get_by_id(self, ad_id: int) -> Optional[AdPost]:
        return await self.session.get(AdPost, ad_id)

    async def get_all(self, archived: bool = False, limit: int = 50) -> List[AdPost]:
        q = select(AdPost).where(AdPost.archived == archived).order_by(AdPost.created_at.desc()).limit(limit)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update(self, ad_id: int, **kwargs) -> Optional[AdPost]:
        ad = await self.get_by_id(ad_id)
        if not ad:
            return None
        for k, v in kwargs.items():
            if hasattr(ad, k) and v is not None:
                setattr(ad, k, v)
        await self.session.commit()
        await self.session.refresh(ad)
        return ad

    async def update_clicks(self, ad_id: int, clicks: int) -> Optional[AdPost]:
        return await self.update(ad_id, clicks=clicks)

    async def update_candidates_count(self, ad_id: int, count: int) -> Optional[AdPost]:
        return await self.update(ad_id, candidates_count=count)

    async def archive(self, ad_id: int) -> Optional[AdPost]:
        return await self.update(ad_id, archived=True)

    async def stats_summary(self) -> dict:
        """Общая статистика по рекламе."""
        q = select(
            func.count(AdPost.id),
            func.sum(AdPost.cost),
            func.sum(AdPost.clicks),
            func.sum(AdPost.candidates_count),
        ).where(AdPost.archived == False)
        result = await self.session.execute(q)
        row = result.one()
        total, cost, clicks, candidates = row
        return {
            "total_posts": total or 0,
            "total_cost": cost or 0,
            "total_clicks": clicks or 0,
            "total_candidates": candidates or 0,
            "avg_cpl": (cost / candidates) if (cost and candidates) else 0,
            "avg_cpc": (cost / clicks) if (cost and clicks) else 0,
        }
