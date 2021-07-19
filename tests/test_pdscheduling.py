from typing import Optional, List

import pytest
import responses

from pdscheduling import PagerDuty, PDSchedulingNetworkException


@responses.activate
def test_get_users():
    responses.add(
        responses.GET,
        url="https://api.pagerduty.com/users?limit=100&include%5B%5D=teams&offset=0",
        json={"users": [{"id": "abc"}], "total": 1, "more": False},
        status=200,
    )

    client = PagerDuty("123")
    result = client.get_users()
    assert result == [{"id": "abc"}]


@responses.activate
def test_incorrect_token():
    responses.add(
        responses.GET,
        url="https://api.pagerduty.com/users?limit=100&include%5B%5D=teams&offset=0",
        status=401,
    )
    client = PagerDuty("123")
    with pytest.raises(PDSchedulingNetworkException, match="PagerDuty request failed: Unauthorized") as exc:
        client.get_users()
    assert exc.value.status_code == 401
    assert exc.value.reason == "Unauthorized"


@pytest.mark.vcr()
def test_update_schedule():
    test_token = "REMOVED"
    client = PagerDuty(test_token)
    schedules = client.schedules()
    assert schedules == []
    users = client.get_users()
    users_idx = [u["id"] for u in users]
    assert users_idx == ["PIMHWDI", "PFQWW1V", "P7P7XIR", "PBE8VP5", "PY4KUZF"]
    hours: List[Optional[str]] = [None for _ in range(7 * 24)]
    hours[1] = "PIMHWDI"
    hours[3] = "PIMHWDI"
    client.create_schedule(name="Schedule Name", hours=hours)

    schedules = client.schedules()
    assert len(schedules) == 1
    schedule_id = schedules[0]["id"]

    # add new layer
    hours[1] = None
    hours[3] = "PIMHWDI"
    hours[5] = "PFQWW1V"

    client.update_schedule(
        schedule_id=schedule_id,
        name="OptDuty",
        hours=hours,
    )

    # remove one layer
    hours[3] = "PFQWW1V"
    hours[5] = None

    client.update_schedule(
        schedule_id=schedule_id,
        name="OptDuty",
        hours=hours,
    )
