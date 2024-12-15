from decimal import Decimal
import pytest

from app.schema import CampaignUpdateRequest
from app.service import CampaignService, ComparisonError


@pytest.fixture(scope="module")
def campaign_service(db) -> CampaignService:
    return CampaignService(db)


def test_get_campaign(campaign_service: CampaignService):
    campaigns = campaign_service.get_campaigns()

    assert campaigns != []


def test_update_campaign_name(campaign_service: CampaignService):
    campaign_id = 21294453254
    original_name = "Competitors"
    new_name = "Competitors 2"

    campaign_service.update_campaign(campaign_id, CampaignUpdateRequest(name=new_name))

    updated_campaign = campaign_service.get_campaign(campaign_id)
    assert updated_campaign.name == new_name

    # Change it back
    campaign_service.update_campaign(
        campaign_id, CampaignUpdateRequest(name=original_name)
    )
    updated_campaign = campaign_service.get_campaign(campaign_id)
    assert updated_campaign.name == original_name


@pytest.mark.parametrize(
    "aggregate_by,campaign_ids,start_date,end_date",
    [
        ("day", None, None, None),
        ("week", None, None, None),
        ("month", None, None, None),
        ("month", [21294453254], None, None),
        ("month", [21294453254, 21358147155], None, None),
        ("month", None, "2023-10-02", None),
        ("month", None, None, "2024-09-17"),
        ("month", [21294453254, 21358147155], None, None),
    ],
)
def test_get_time_series_performance_valid_inputs(
    campaign_service: CampaignService, aggregate_by, campaign_ids, start_date, end_date
):
    results = campaign_service.get_time_series_performance(
        aggregate_by, campaign_ids, start_date, end_date
    )

    for result in results:
        if campaign_ids:
            assert result.campaign_id in campaign_ids

        if start_date:
            assert result.date >= start_date

        if end_date:
            assert result.date <= end_date


def test_get_time_series_performance_invalid_aggregation(
    campaign_service: CampaignService,
):
    with pytest.raises(ValueError, match="Invalid aggregation level"):
        campaign_service.get_time_series_performance(aggregate_by="year")


def test_get_time_series_performance_invalid_dates(campaign_service: CampaignService):
    with pytest.raises(ComparisonError, match="start_date cannot be after end_date."):
        campaign_service.get_time_series_performance(
            "month", None, "2024-09-17", "2023-10-02"
        )

    with pytest.raises(ComparisonError, match="Invalid date format. Use YYYY-MM-DD."):
        campaign_service.get_time_series_performance(
            "month", None, "10-02-2023", "17-09-2024"
        )


def test_compare_performance(campaign_service: CampaignService):
    result = campaign_service.compare_performance(
        "2023-10-02", "2024-09-17", "previous_month"
    )

    def calculate_change_in_percentage(before, after):
        percentage = round(((after - before) / before) * 100, 2)
        return Decimal("{:.2f}".format(percentage))

    assert result.change_in_percentage.total_cost == calculate_change_in_percentage(
        result.before_period.total_cost, result.current_period.total_cost
    )
    assert result.change_in_percentage.total_clicks == calculate_change_in_percentage(
        result.before_period.total_clicks, result.current_period.total_clicks
    )
    assert (
        result.change_in_percentage.total_conversions
        == calculate_change_in_percentage(
            result.before_period.total_conversions,
            result.current_period.total_conversions,
        )
    )
    assert result.change_in_percentage.cost_per_click == calculate_change_in_percentage(
        result.before_period.cost_per_click, result.current_period.cost_per_click
    )
    assert (
        result.change_in_percentage.cost_per_conversion
        == calculate_change_in_percentage(
            result.before_period.cost_per_conversion,
            result.current_period.cost_per_conversion,
        )
    )
    assert (
        result.change_in_percentage.cost_per_impression
        == calculate_change_in_percentage(
            result.before_period.cost_per_impression,
            result.current_period.cost_per_impression,
        )
    )
    assert (
        result.change_in_percentage.click_through_rate
        == calculate_change_in_percentage(
            result.before_period.click_through_rate,
            result.current_period.click_through_rate,
        )
    )
    assert (
        result.change_in_percentage.conversion_rate
        == calculate_change_in_percentage(
            result.before_period.conversion_rate, result.current_period.conversion_rate
        )
    )
