from decimal import Decimal
import sys

sys.path.append(".")

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.models import Campaign, AdGroup, AdGroupStat


SQLALCHEMY_DATABASE_URL = "postgresql://postgres:password@localhost/postgres"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

session = SessionLocal()


# dumping campaigns
df = pd.read_csv("./data/campaigns.csv")
campaigns = []
for _, row in df.iterrows():
    campaign = Campaign(
        id=int(row["campaign_id"]),
        name=row["campaign_name"],
        type=row["campaign_type"],
    )
    campaigns.append(campaign)
session.bulk_save_objects(campaigns)
session.commit()


# dumping ad groups
df = pd.read_csv("./data/ad_groups.csv")
ad_groups = []
for _, row in df.iterrows():
    ad_group = AdGroup(
        id=int(row["ad_group_id"]),
        name=row["ad_group_name"],
        campaign_id=int(row["campaign_id"]),
    )
    ad_groups.append(ad_group)
session.bulk_save_objects(ad_groups)
session.commit()


# dumping ad group stats
df = pd.read_csv("./data/ad_group_stats.csv")

df["date"] = pd.to_datetime(df["date"])
df["impressions"] = pd.to_numeric(df["impressions"], errors="coerce")
df["clicks"] = pd.to_numeric(df["clicks"], errors="coerce")
df["conversions"] = pd.to_numeric(df["conversions"], errors="coerce")
df["cost"] = pd.to_numeric(df["cost"], errors="coerce")


# aggregate duplicate rows
df_cleaned = df.groupby(["date", "ad_group_id", "device"], as_index=False).agg(
    {"impressions": "sum", "clicks": "sum", "conversions": "sum", "cost": "sum"}
)

ad_group_stats = []
for index, row in df_cleaned.iterrows():
    ad_group_stat = AdGroupStat(
        date=row["date"],
        ad_group_id=row["ad_group_id"],
        device=row["device"],
        impressions=row["impressions"],
        clicks=row["clicks"],
        conversions=Decimal(row["conversions"]),
        cost=Decimal(row["cost"]),
    )
    ad_group_stats.append(ad_group_stat)
session.bulk_save_objects(ad_group_stats)
session.commit()

session.close()
