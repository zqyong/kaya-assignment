from __future__ import annotations
from decimal import Decimal
from typing import List
from datetime import date
from sqlalchemy import ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Campaign(Base):
    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column()
    type: Mapped[str] = mapped_column()

    ad_groups: Mapped[List["AdGroup"]] = relationship()


class AdGroup(Base):
    __tablename__ = "ad_group"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column()
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaign.id"))

    ad_group_stats: Mapped[List["AdGroupStat"]] = relationship()


class AdGroupStat(Base):
    __tablename__ = "ad_group_stat"

    date: Mapped[date] = mapped_column(primary_key=True)
    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_group.id"), primary_key=True
    )
    device: Mapped[str] = mapped_column(primary_key=True)
    impressions: Mapped[int] = mapped_column()
    clicks: Mapped[int] = mapped_column()
    conversions: Mapped[Decimal] = mapped_column()
    cost: Mapped[Decimal] = mapped_column()
