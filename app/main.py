from typing import List, Literal, Optional
from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract, case

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
                "average_cost_per_conversion": result.average_cost_per_conversion,
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


class PerformanceTimeSeriesResponse(BaseModel):
    date: str
    campaign_id: int
    campaign_name: str
    total_cost: float
    total_clicks: int
    total_conversions: float
    avg_cost_per_click: Optional[float]
    avg_cost_per_conversion: Optional[float]
    avg_click_through_rate: Optional[float]
    avg_conversion_rate: Optional[float]


@app.get("/performance-time-series")
def get_performance_time_series(
    aggregate_by: Literal["day", "week", "month"] = Query(
        ..., description="Aggregate the data by day, week, or month"
    ),
    campaign_ids: Optional[List[int]] = Query(
        None, description="Filter data for specific campaign IDs"
    ),
    start_date: Optional[str] = Query(
        None, description="Filter data from a given start date (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter data up to a given end date (YYYY-MM-DD)"
    ),
    db: Session = Depends(get_db),
):
    """
    Returns time-series performance data aggregated by day, week, or month for each campaign,
    with optional filters for campaigns and date range. Average value not provided
    if clicks/conversions/impressions are zero.

    Metrics:
    - Total cost
    - Total clicks
    - Total conversions
    - Average cost per click
    - Average cost per conversion
    - Average click-through rate = clicks / impressions
    - Average conversion rate = conversions / clicks
    """

    # Determine the grouping level based on the `aggregate_by` parameter
    if aggregate_by == "day":
        group_by = [Campaign.id, Campaign.name, AdGroupStat.date]
    elif aggregate_by == "week":
        group_by = [
            Campaign.id,
            Campaign.name,
            extract("year", AdGroupStat.date).label("year"),
            func.date_part("week", AdGroupStat.date).label("week"),
        ]
    elif aggregate_by == "month":
        group_by = [
            Campaign.id,
            Campaign.name,
            extract("year", AdGroupStat.date).label("year"),
            extract("month", AdGroupStat.date).label("month"),
        ]
    else:
        raise HTTPException(status_code=400, detail="Invalid aggregation level")

    # Base query
    query = (
        db.query(
            func.min(AdGroupStat.date).label("date"),
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            func.sum(AdGroupStat.cost).label("total_cost"),
            func.sum(AdGroupStat.clicks).label("total_clicks"),
            func.sum(AdGroupStat.conversions).label("total_conversions"),
            case(
                (
                    func.sum(AdGroupStat.clicks) > 0,
                    func.sum(AdGroupStat.cost) / func.sum(AdGroupStat.clicks),
                ),
                else_=None,
            ).label("avg_cost_per_click"),
            case(
                (
                    func.sum(AdGroupStat.conversions) > 0,
                    func.sum(AdGroupStat.cost) / func.sum(AdGroupStat.conversions),
                ),
                else_=None,
            ).label("avg_cost_per_conversion"),
            case(
                (
                    func.sum(AdGroupStat.impressions) > 0,
                    func.sum(AdGroupStat.clicks) / func.sum(AdGroupStat.impressions),
                ),
                else_=None,
            ).label("avg_click_through_rate"),
            case(
                (
                    func.sum(AdGroupStat.clicks) > 0,
                    func.sum(AdGroupStat.conversions) / func.sum(AdGroupStat.clicks),
                ),
                else_=None,
            ).label("avg_conversion_rate"),
        )
        .join(AdGroup, AdGroupStat.ad_group_id == AdGroup.id)
        .join(Campaign, AdGroup.campaign_id == Campaign.id)
    )

    # Apply filters for campaigns and date range
    filters = []
    if campaign_ids:
        filters.append(Campaign.id.in_(campaign_ids))
    if start_date:
        filters.append(AdGroupStat.date >= start_date)
    if end_date:
        filters.append(AdGroupStat.date <= end_date)

    if filters:
        query = query.filter(and_(*filters))

    # Group and execute query
    query = query.group_by(*group_by).order_by(func.min(AdGroupStat.date))
    results = query.all()

    # Transform query results into the response model
    response = [
        PerformanceTimeSeriesResponse(
            date=result.date.isoformat(),
            campaign_id=result.campaign_id,
            campaign_name=result.campaign_name,
            total_cost=float(result.total_cost or 0),
            total_clicks=int(result.total_clicks or 0),
            total_conversions=float(result.total_conversions or 0),
            avg_cost_per_click=result.avg_cost_per_click,
            avg_cost_per_conversion=result.avg_cost_per_conversion,
            avg_click_through_rate=result.avg_click_through_rate,
            avg_conversion_rate=result.avg_conversion_rate,
        )
        for result in results
    ]

    return response


@app.get("/compare-performance")
def compare_performance(
    start_date: str = Query(..., description="The start date of the current period (YYYY-MM-DD)."),
    end_date: str = Query(..., description="The end date of the current period (YYYY-MM-DD)."),
    compare_mode: Literal["preceding", "previous_month"] = Query(..., description="Defines how the comparison period is chosen."),
    db: Session = Depends(get_db),
):
    """
    Compares performance metrics for a specified time range ('current') against a preceding time period ('before').

    Metrics:
    - Total cost
    - Total clicks
    - Total conversions
    - Average cost per click
    - Average cost per conversion
    - Cost per impression
    - Click-through rate
    """
    try:
        current_start = datetime.strptime(start_date, "%Y-%m-%d")
        current_end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if current_start > current_end:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date.")

    # Determine the 'before' period based on compare_mode
    delta = (current_end - current_start).days + 1

    if compare_mode == "preceding":
        before_start = current_start - timedelta(days=delta)
        before_end = current_start - timedelta(days=1)
    elif compare_mode == "previous_month":
        before_start = current_start - timedelta(days=delta + 30)  # Approximation for previous month
        before_end = current_end - timedelta(days=30)
    else:
        raise HTTPException(status_code=400, detail="Invalid compare_mode.")

    def get_performance_metrics(start, end):
        query = (
            db.query(
                func.sum(AdGroupStat.cost).label("total_cost"),
                func.sum(AdGroupStat.clicks).label("total_clicks"),
                func.sum(AdGroupStat.conversions).label("total_conversions"),
                func.sum(AdGroupStat.impressions).label("total_impressions"),
                case(
                    (func.sum(AdGroupStat.clicks) > 0, func.sum(AdGroupStat.cost) / func.sum(AdGroupStat.clicks)),
                    else_=None,
                ).label("avg_cost_per_click"),
                case(
                    (func.sum(AdGroupStat.conversions) > 0, func.sum(AdGroupStat.cost) / func.sum(AdGroupStat.conversions)),
                    else_=None,
                ).label("avg_cost_per_conversion"),
                case(
                    (func.sum(AdGroupStat.impressions) > 0, func.sum(AdGroupStat.cost) / func.sum(AdGroupStat.impressions)),
                    else_=None,
                ).label("cost_per_impression"),
                case(
                    (func.sum(AdGroupStat.impressions) > 0, func.sum(AdGroupStat.clicks) / func.sum(AdGroupStat.impressions)),
                    else_=None,
                ).label("click_through_rate"),
            )
            .join(AdGroup, AdGroupStat.ad_group_id == AdGroup.id)
            .join(Campaign, AdGroup.campaign_id == Campaign.id)
            .filter(and_(AdGroupStat.date >= start, AdGroupStat.date <= end))
        )
        return query.one()

    # Fetch metrics for both periods
    current_metrics = get_performance_metrics(current_start, current_end)
    before_metrics = get_performance_metrics(before_start, before_end)

    # Structure the response
    response = {
        "current_period": {
            "start_date": current_start.strftime("%Y-%m-%d"),
            "end_date": current_end.strftime("%Y-%m-%d"),
            "total_cost": float(current_metrics.total_cost or 0),
            "total_clicks": int(current_metrics.total_clicks or 0),
            "total_conversions": float(current_metrics.total_conversions or 0),
            "avg_cost_per_click": current_metrics.avg_cost_per_click,
            "avg_cost_per_conversion": current_metrics.avg_cost_per_conversion,
            "cost_per_impression": current_metrics.cost_per_impression,
            "click_through_rate": current_metrics.click_through_rate,
        },
        "before_period": {
            "start_date": before_start.strftime("%Y-%m-%d"),
            "end_date": before_end.strftime("%Y-%m-%d"),
            "total_cost": float(before_metrics.total_cost or 0),
            "total_clicks": int(before_metrics.total_clicks or 0),
            "total_conversions": float(before_metrics.total_conversions or 0),
            "avg_cost_per_click": before_metrics.avg_cost_per_click,
            "avg_cost_per_conversion": before_metrics.avg_cost_per_conversion,
            "cost_per_impression": before_metrics.cost_per_impression,
            "click_through_rate": before_metrics.click_through_rate,
        },
    }

    return response
