from httpx import Client


def test_get_campaigns_endpoint(app_client: Client):
    response = app_client.get("/campaigns")

    assert response.status_code == 200
    # response not empty
    assert response.json()


def test_update_campaign_name_endpoint(app_client: Client):
    response = app_client.get("/campaigns")

    # grab the first campaign
    campaign_to_change = response.json()[0]
    campaign_id = campaign_to_change["campaign_id"]
    original_name = campaign_to_change["campaign_name"]
    new_name = "New name"

    # change campaign name
    response = app_client.patch(f"/campaigns/{campaign_id}", json={"name": new_name})

    # check name is changed
    response = app_client.get("/campaigns")
    changed_campaign = response.json()[0]
    assert changed_campaign["campaign_name"] == new_name

    # change it back
    response = app_client.patch(
        f"/campaigns/{campaign_id}", json={"name": original_name}
    )

    # check name is changed
    response = app_client.get("/campaigns")
    changed_campaign = response.json()[0]
    assert changed_campaign["campaign_name"] == original_name


def test_get_time_series_performance_endpoint_ok(app_client: Client):
    params = {
        "aggregate_by": "month",
        "campaign_ids": [21294453254],
        "start_date": "2023-10-02",
        "end_date": "2024-09-17",
    }
    response = app_client.get("/performance-time-series", params=params)

    assert response.status_code == 200
    assert response.json()


def test_get_time_series_performance_endpoint_bad_aggregate(app_client: Client):
    params = {
        "aggregate_by": "year",
        "campaign_ids": [21294453254],
        "start_date": "2023-10-02",
        "end_date": "2024-09-17",
    }
    response = app_client.get("/performance-time-series", params=params)

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Invalid aggregation level. Valid values are 'day', 'week' or 'month'"
    )


def test_get_time_series_performance_endpoint_bad_dates(app_client: Client):
    # start date after end date
    params = {
        "aggregate_by": "month",
        "campaign_ids": [21294453254],
        "start_date": "2024-09-17",
        "end_date": "2023-10-02",
    }
    response = app_client.get("/performance-time-series", params=params)

    assert response.status_code == 400
    assert response.json()["detail"] == "start_date cannot be after end_date."

    # bad date format
    params = {
        "aggregate_by": "month",
        "campaign_ids": [21294453254],
        "start_date": "02-10-2023",
        "end_date": "17-09-2024",
    }
    response = app_client.get("/performance-time-series", params=params)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid date format. Use YYYY-MM-DD."


def test_compare_performance_endpoint_ok(app_client: Client):
    params = {
        "start_date": "2023-10-02",
        "end_date": "2024-09-17",
        "compare_mode": "previous_month",
    }
    response = app_client.get("/compare-performance", params=params)

    assert response.status_code == 200
    assert response.json()


def test_compare_performance_endpoint_bad_compare_mode(app_client: Client):
    params = {
        "start_date": "2023-10-02",
        "end_date": "2024-09-17",
        "compare_mode": "random",
    }
    response = app_client.get("/compare-performance", params=params)

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Invalid compare_mode. Valid values are 'preceding' and 'previous_month'."
    )


def test_compare_performance_endpoint_bad_dates(app_client: Client):
    # start date after end date
    params = {
        "start_date": "2024-09-11",
        "end_date": "2024-09-10",
        "compare_mode": "preceding",
    }
    response = app_client.get("/compare-performance", params=params)

    assert response.status_code == 400
    assert response.json()["detail"] == "start_date cannot be after end_date."

    # bad date format
    params = {
        "start_date": "10-09-2024",
        "end_date": "11-09-2024",
        "compare_mode": "previous_month",
    }
    response = app_client.get("/compare-performance", params=params)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid date format. Use YYYY-MM-DD."
