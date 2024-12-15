from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.database import get_db
from app.schema import (
    CampaignStats,
    CampaignUpdateRequest,
    CampaignUpdateResponse,
    PerformanceComparisonResponse,
    PerformanceTimeSeriesResponse,
)
from app.service import CampaignService, CampaignServiceError


app = FastAPI()
campaign_service = CampaignService(next(get_db()))


@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(url="/docs")


@app.get("/campaigns")
def get_campaigns() -> list[CampaignStats]:
    """
    Returns a list of campaigns with their respective number of ad groups, ad group names, average monthly cost, and average cost per conversion.
    """
    try:
        return campaign_service.get_campaigns()
    except (CampaignServiceError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.patch("/campaigns/{campaign_id}")
def update_campaign(
    campaign_id: str,
    update_request: CampaignUpdateRequest = None,
) -> CampaignUpdateResponse:
    """
    Endpoint to update a Campaign.
    """
    try:
        updated_campaign = campaign_service.update_campaign(
            campaign_id=campaign_id, update_request=update_request
        )
        return updated_campaign
    except (CampaignServiceError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.get("/performance-time-series")
def get_performance_time_series(
    aggregate_by: str = Query(
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
) -> list[PerformanceTimeSeriesResponse]:
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
    try:
        return campaign_service.get_time_series_performance(
            aggregate_by=aggregate_by,
            campaign_ids=campaign_ids,
            start_date=start_date,
            end_date=end_date,
        )
    except (CampaignServiceError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.get("/compare-performance")
def compare_performance(
    start_date: str = Query(
        ..., description="The start date of the current period (YYYY-MM-DD)."
    ),
    end_date: str = Query(
        ..., description="The end date of the current period (YYYY-MM-DD)."
    ),
    compare_mode: str = Query(
        ...,
        description="Defines how the comparison period is chosen. Valid values are 'preceding' and 'previous_month'",
    ),
) -> PerformanceComparisonResponse:
    """
    Compares performance metrics for a specified time range ('current') against a preceding time period ('before').

    Metrics:
    - Total cost
    - Total clicks
    - Total conversions
    - Cost per click
    - Cost per conversion
    - Cost per impression
    - Click-through rate
    """
    try:
        return campaign_service.compare_performance(
            start_date=start_date, end_date=end_date, compare_mode=compare_mode
        )
    except (CampaignServiceError, ValueError) as e:
        raise HTTPException(400, str(e))
