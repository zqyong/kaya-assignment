from decimal import Decimal
from typing import Any, Optional
from fastapi.encoders import decimal_encoder
from pydantic import BaseModel, ConfigDict, field_validator


class CampaignStats(BaseModel):
    campaign_id: int
    campaign_name: str
    num_ad_groups: int
    ad_group_names: list[str]
    average_monthly_cost: Decimal
    average_cost_per_conversion: Decimal

    model_config = ConfigDict(json_encoders={Decimal: decimal_encoder})

    @field_validator("*")
    @classmethod
    def decimal_percision_rounded_to_two(cls, v: Any) -> Any:
        if isinstance(v, Decimal):
            return round(Decimal(v), 2)
        return v


class CampaignUpdateResponse(BaseModel):
    id: int
    name: str
    type: str


class CampaignUpdateRequest(BaseModel):
    name: str


class PerformanceTimeSeriesResponse(BaseModel):
    date: str
    campaign_id: int
    campaign_name: str
    total_cost: Decimal
    total_clicks: int
    total_conversions: Decimal
    avg_cost_per_click: Optional[Decimal]
    avg_cost_per_conversion: Optional[Decimal]
    avg_click_through_rate: Optional[Decimal]
    avg_conversion_rate: Optional[Decimal]

    model_config = ConfigDict(json_encoders={Decimal: decimal_encoder})

    @field_validator("*")
    @classmethod
    def decimal_percision_rounded_to_two(cls, v: Any) -> Any:
        if isinstance(v, Decimal):
            return round(Decimal(v), 2)
        return v


class PeriodPerformance(BaseModel):
    start_date: str
    end_date: str
    total_cost: Decimal
    total_clicks: int
    total_conversions: Decimal
    cost_per_click: Optional[Decimal] = None
    cost_per_conversion: Optional[Decimal] = None
    cost_per_impression: Optional[Decimal] = None
    click_through_rate: Optional[Decimal] = None
    conversion_rate: Optional[Decimal] = None

    model_config = ConfigDict(json_encoders={Decimal: decimal_encoder})

    @field_validator("*")
    @classmethod
    def decimal_percision_rounded_to_two(cls, v: Any) -> Any:
        if isinstance(v, Decimal):
            return round(Decimal(v), 2)
        return v


class ChangeMetrics(BaseModel):
    total_cost: Optional[Decimal] = None
    total_clicks: Optional[Decimal] = None
    total_conversions: Optional[Decimal] = None
    cost_per_click: Optional[Decimal] = None
    cost_per_conversion: Optional[Decimal] = None
    cost_per_impression: Optional[Decimal] = None
    click_through_rate: Optional[Decimal] = None
    conversion_rate: Optional[Decimal] = None

    model_config = ConfigDict(json_encoders={Decimal: decimal_encoder})

    @field_validator("*")
    @classmethod
    def decimal_percision_rounded_to_two(cls, v: Any) -> Any:
        if isinstance(v, Decimal):
            return round(Decimal(v), 2)
        return v


class PerformanceComparisonResponse(BaseModel):
    before_period: PeriodPerformance
    current_period: PeriodPerformance
    change_in_percentage: ChangeMetrics
