from fastapi import Depends, FastAPI, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.database import get_db
from app.models import Campaign, AdGroup, AdGroupStat


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello"}



@app.get("/campaigns")
def get_campaigns(db: Session = Depends(get_db)):

    # Subquery: Calculate the monthly total cost for each AdGroup
    monthly_totals_subquery = (
        db.query(
            AdGroupStat.ad_group_id,
            func.sum(AdGroupStat.cost).label("monthly_total"),
            extract("year", AdGroupStat.date).label("year"),
            extract("month", AdGroupStat.date).label("month"),
        ).group_by(
            AdGroupStat.ad_group_id,
            extract("year", AdGroupStat.date),
            extract("month", AdGroupStat.date),
        )
    ).subquery()

    # Subquery: Calculate the average monthly cost for each AdGroup
    average_monthly_cost_subquery = (
        db.query(
            monthly_totals_subquery.c.ad_group_id,
            func.avg(monthly_totals_subquery.c.monthly_total).label(
                "average_monthly_cost"
            ),
        ).group_by(monthly_totals_subquery.c.ad_group_id)
    ).subquery()

    # Subquery: Calculate the average cost per conversion for each AdGroup
    average_cost_per_conversion_subquery = (
        db.query(
            AdGroupStat.ad_group_id,
            (func.sum(AdGroupStat.cost) / func.sum(AdGroupStat.conversions)).label(
                "average_cost_per_conversion"
            ),
        )
        .group_by(AdGroupStat.ad_group_id)
        .having(func.sum(AdGroupStat.conversions) > 0)  # Avoid division by zero
    ).subquery()

    # Main query: Combine campaigns with AdGroup details and aggregated stats
    campaigns_query = (
        db.query(
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            func.count(AdGroup.id).label("num_ad_groups"),
            func.array_agg(AdGroup.name).label("ad_group_names"),
            func.coalesce(
                func.avg(average_monthly_cost_subquery.c.average_monthly_cost), 0
            ).label("average_monthly_cost"),
            func.coalesce(
                func.avg(
                    average_cost_per_conversion_subquery.c.average_cost_per_conversion
                ),
                0,
            ).label("average_cost_per_conversion"),
        )
        .join(AdGroup, Campaign.id == AdGroup.campaign_id)
        .outerjoin(
            average_monthly_cost_subquery,
            AdGroup.id == average_monthly_cost_subquery.c.ad_group_id,
        )
        .outerjoin(
            average_cost_per_conversion_subquery,
            AdGroup.id == average_cost_per_conversion_subquery.c.ad_group_id,
        )
        .group_by(Campaign.id, Campaign.name)
    )

    # Execute the query
    results = campaigns_query.all()

    output = []

    # Process and display the results
    for result in results:
        output.append(
            {
                "campaign_id": result.campaign_id,
                "campaign_name": result.campaign_name,
                "num_ad_groups": result.num_ad_groups,
                "ad_group_names": result.ad_group_names,
                "average_monthly_cost": result.average_monthly_cost,
                "average_cost_per_conversion": result.average_cost_per_conversion
            }
        )

    return output


class CampaignUpdateRequest(BaseModel):
    name: str

@app.patch("/campaigns/{campaign_id}")
def update_campaign(
    campaign_id: str,
    update_request: CampaignUpdateRequest = None,
    db: Session = Depends(get_db),
):
    # Fetch the campaign
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

    # Check if the campaign exists
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Update the campaign name
    campaign.name = update_request.name
    db.commit()
    db.refresh(campaign)

    # Return the updated campaign
    return {"id": campaign.id, "name": campaign.name} 