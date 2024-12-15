from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Literal, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract, case

from app.models import Campaign, AdGroup, AdGroupStat
from app.schema import (
    CampaignStats,
    CampaignUpdateRequest,
    CampaignUpdateResponse,
    ChangeMetrics,
    PerformanceComparisonResponse,
    PerformanceTimeSeriesResponse,
    PeriodPerformance,
)


class CampaignServiceError(Exception):
    pass


class CampaignNotFound(CampaignServiceError):
    pass


class ComparisonError(CampaignServiceError):
    pass


def calculate_percentage_change(current: Decimal, before: Decimal) -> Optional[Decimal]:
    try:
        if current is not None and before is not None and before != 0:
            return round(((current - before) / before) * 100, 2)
    except InvalidOperation:
        pass
    return None


def validate_start_and_end_date(
    start_date: Optional[str], end_date: Optional[str]
) -> tuple[Optional[datetime], Optional[datetime]]:
    try:
        current_start = (
            datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        )
        current_end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        if (current_start and current_end) and (current_start > current_end):
            raise ComparisonError("start_date cannot be after end_date.")

        return current_start, current_end
    except ValueError:
        raise ComparisonError("Invalid date format. Use YYYY-MM-DD.")


class CampaignService:
    def __init__(self, db: Session):
        self.db = db
        pass

    def get_campaign(self, campaign_id: str) -> Campaign:
        return self.db.query(Campaign).filter(Campaign.id == campaign_id).first()

    def get_campaigns(self):
        # Subquery: Calculate the monthly total cost for each AdGroup
        monthly_totals_subquery = (
            self.db.query(
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
            self.db.query(
                monthly_totals_subquery.c.ad_group_id,
                func.avg(monthly_totals_subquery.c.monthly_total).label(
                    "average_monthly_cost"
                ),
            ).group_by(monthly_totals_subquery.c.ad_group_id)
        ).subquery()

        # Subquery: Calculate the average cost per conversion for each AdGroup
        average_cost_per_conversion_subquery = (
            self.db.query(
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
            self.db.query(
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
                CampaignStats(
                    campaign_id=result.campaign_id,
                    campaign_name=result.campaign_name,
                    num_ad_groups=result.num_ad_groups,
                    ad_group_names=result.ad_group_names,
                    average_monthly_cost=result.average_monthly_cost,
                    average_cost_per_conversion=result.average_cost_per_conversion,
                )
            )

        return output

    def update_campaign(self, campaign_id: str, update_request: CampaignUpdateRequest):
        # Fetch the campaign
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()

        # Check if the campaign exists
        if not campaign:
            raise CampaignNotFound

        # Update the campaign name
        campaign.name = update_request.name
        self.db.commit()
        self.db.refresh(campaign)

        # Return the updated campaign
        return CampaignUpdateResponse(
            id=campaign.id, name=campaign.name, type=campaign.type
        )

    def get_time_series_performance(
        self,
        aggregate_by: Literal["day", "week", "month"],
        campaign_ids: Optional[List[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
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
            raise ValueError(
                "Invalid aggregation level. Valid values are 'day', 'week' or 'month'"
            )

        start_date, end_date = validate_start_and_end_date(start_date, end_date)

        # Base query
        query = (
            self.db.query(
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
                        func.sum(AdGroupStat.clicks)
                        / func.sum(AdGroupStat.impressions),
                    ),
                    else_=None,
                ).label("avg_click_through_rate"),
                case(
                    (
                        func.sum(AdGroupStat.clicks) > 0,
                        func.sum(AdGroupStat.conversions)
                        / func.sum(AdGroupStat.clicks),
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
                total_cost=Decimal(result.total_cost or 0),
                total_clicks=int(result.total_clicks or 0),
                total_conversions=Decimal(result.total_conversions or 0),
                avg_cost_per_click=result.avg_cost_per_click,
                avg_cost_per_conversion=result.avg_cost_per_conversion,
                avg_click_through_rate=result.avg_click_through_rate,
                avg_conversion_rate=result.avg_conversion_rate,
            )
            for result in results
        ]

        return response

    def compare_performance(
        self,
        start_date: str,
        end_date: str,
        compare_mode: Literal["preceding", "previous_month"],
    ):
        current_start, current_end = validate_start_and_end_date(start_date, end_date)

        # Determine the 'before' period based on compare_mode
        delta = (current_end - current_start).days + 1

        if compare_mode == "preceding":
            before_start = current_start - timedelta(days=delta)
            before_end = current_start - timedelta(days=1)
        elif compare_mode == "previous_month":
            before_start = current_start - timedelta(
                days=delta + 30
            )  # Approximation for previous month
            before_end = current_end - timedelta(days=30)
        else:
            raise ValueError(
                "Invalid compare_mode. Valid values are 'preceding' and 'previous_month'."
            )

        def get_performance_metrics(start, end):
            query = (
                self.db.query(
                    func.sum(AdGroupStat.cost).label("total_cost"),
                    func.sum(AdGroupStat.clicks).label("total_clicks"),
                    func.sum(AdGroupStat.conversions).label("total_conversions"),
                    func.sum(AdGroupStat.impressions).label("total_impressions"),
                    case(
                        (
                            func.sum(AdGroupStat.clicks) > 0,
                            func.round(
                                func.sum(AdGroupStat.cost)
                                / func.sum(AdGroupStat.clicks),
                                2,
                            ),
                        ),
                        else_=None,
                    ).label("cost_per_click"),
                    case(
                        (
                            func.sum(AdGroupStat.conversions) > 0,
                            func.round(
                                func.sum(AdGroupStat.cost)
                                / func.sum(AdGroupStat.conversions),
                                2,
                            ),
                        ),
                        else_=None,
                    ).label("cost_per_conversion"),
                    case(
                        (
                            func.sum(AdGroupStat.impressions) > 0,
                            func.round(
                                func.sum(AdGroupStat.cost)
                                / func.sum(AdGroupStat.impressions),
                                2,
                            ),
                        ),
                        else_=None,
                    ).label("cost_per_impression"),
                    case(
                        (
                            func.sum(AdGroupStat.impressions) > 0,
                            func.round(
                                func.sum(AdGroupStat.clicks)
                                / func.sum(AdGroupStat.impressions),
                                2,
                            ),
                        ),
                        else_=None,
                    ).label("click_through_rate"),
                    case(
                        (
                            func.sum(AdGroupStat.clicks) > 0,
                            func.round(
                                func.sum(AdGroupStat.conversions)
                                / func.sum(AdGroupStat.clicks),
                                2,
                            ),
                        ),
                        else_=None,
                    ).label("conversion_rate"),
                )
                .join(AdGroup, AdGroupStat.ad_group_id == AdGroup.id)
                .join(Campaign, AdGroup.campaign_id == Campaign.id)
                .filter(and_(AdGroupStat.date >= start, AdGroupStat.date <= end))
            )
            return query.one()

        # Fetch metrics for both periods
        current_metrics = get_performance_metrics(current_start, current_end)
        before_metrics = get_performance_metrics(before_start, before_end)

        # Response
        response = PerformanceComparisonResponse(
            before_period=PeriodPerformance(
                start_date=before_start.strftime("%Y-%m-%d"),
                end_date=before_end.strftime("%Y-%m-%d"),
                total_cost=float(before_metrics.total_cost or 0),
                total_clicks=int(before_metrics.total_clicks or 0),
                total_conversions=float(before_metrics.total_conversions or 0),
                cost_per_click=before_metrics.cost_per_click,
                cost_per_conversion=before_metrics.cost_per_conversion,
                cost_per_impression=before_metrics.cost_per_impression,
                click_through_rate=before_metrics.click_through_rate,
                conversion_rate=before_metrics.conversion_rate,
            ),
            current_period=PeriodPerformance(
                start_date=current_start.strftime("%Y-%m-%d"),
                end_date=current_end.strftime("%Y-%m-%d"),
                total_cost=float(current_metrics.total_cost or 0),
                total_clicks=int(current_metrics.total_clicks or 0),
                total_conversions=float(current_metrics.total_conversions or 0),
                cost_per_click=current_metrics.cost_per_click,
                cost_per_conversion=current_metrics.cost_per_conversion,
                cost_per_impression=current_metrics.cost_per_impression,
                click_through_rate=current_metrics.click_through_rate,
                conversion_rate=current_metrics.conversion_rate,
            ),
            change_in_percentage=ChangeMetrics(
                total_cost=calculate_percentage_change(
                    current_metrics.total_cost, before_metrics.total_cost
                ),
                total_clicks=calculate_percentage_change(
                    current_metrics.total_clicks, before_metrics.total_clicks
                ),
                total_conversions=calculate_percentage_change(
                    current_metrics.total_conversions, before_metrics.total_conversions
                ),
                cost_per_click=calculate_percentage_change(
                    current_metrics.cost_per_click,
                    before_metrics.cost_per_click,
                ),
                cost_per_conversion=calculate_percentage_change(
                    current_metrics.cost_per_conversion,
                    before_metrics.cost_per_conversion,
                ),
                cost_per_impression=calculate_percentage_change(
                    current_metrics.cost_per_impression,
                    before_metrics.cost_per_impression,
                ),
                click_through_rate=calculate_percentage_change(
                    current_metrics.click_through_rate,
                    before_metrics.click_through_rate,
                ),
                conversion_rate=calculate_percentage_change(
                    current_metrics.conversion_rate, before_metrics.conversion_rate
                ),
            ),
        )

        return response
