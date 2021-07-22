import copy
import json
from typing import List, Optional

import requests

__version__ = "0.2.2"

from pdpyras import APISession, PDClientError


class PDSchedulingException(Exception):
    pass


class PDSchedulingNetworkException(PDSchedulingException):
    status_code = None
    reason = ""

    def __init__(
        self, message, status_code: Optional[int] = None, reason: Optional[str] = None
    ):
        self.status_code = status_code
        self.reason = reason or "Unknown"
        super().__init__(message)


def _calculate_consecutive_hours(hours: List[str]) -> int:
    consecutive_hours = 0

    target_user = hours[0]
    for user in hours:
        if consecutive_hours > 23:
            break
        elif user == target_user:
            consecutive_hours += 1
        else:
            break
    return consecutive_hours


def _generate_schedule_data(name, hours, layers_ids, schedule_id):
    assert len(hours) == 7 * 24
    all_users = list(set([id for id in hours if id]))
    assert len(all_users)
    layers = []
    for i, user in enumerate(all_users):
        restrictions = []
        for day in range(7):
            for hour in range(24):
                hours_idx = day * 24 + hour
                if hours[hours_idx] == user and (
                    hours_idx == 0 or hours[hours_idx - 1] != user
                ):
                    consecutive_hours = _calculate_consecutive_hours(hours[hours_idx:])

                    # hacky way break sequence and limit maximum duration to 24 hours
                    # this is some PD limit
                    hours[hours_idx + consecutive_hours - 1] = None

                    restrictions.append(
                        {
                            "type": "weekly_restriction",
                            "start_day_of_week": day + 1,
                            "start_time_of_day": f"{hour:02d}:00:00",
                            "duration_seconds": consecutive_hours * 3600,
                        }
                    )

        assert len(restrictions) < 90
        layer = {
            "start": "2015-11-06T20:00:00-05:00",
            "users": [{"user": {"id": user, "type": "user"}}],
            "rotation_turn_length_seconds": 604800,
            "rotation_virtual_start": "2015-11-06T20:00:00-05:00",
            "restrictions": restrictions,
        }
        try:
            layer_id = layers_ids[i]
            layer["id"] = layer_id
        except IndexError:
            pass
        layers.append(layer)

    if len(layers_ids) > len(all_users):
        layers_to_remove = layers_ids[len(all_users) :]
        for layer_id in layers_to_remove:
            new_layer = copy.deepcopy(layers[0])
            new_layer["id"] = layer_id
            layers.append(new_layer)

    data = {
        "schedule": {
            "name": name,
            "type": "schedule",
            "time_zone": "UTC",
            "description": "Automatically created by PDScheduling",
            "schedule_layers": layers,
        }
    }
    if schedule_id:
        data["id"] = schedule_id
    return data


def _create_scheduling_exception(result):
    if result is None:
        message = "PagerDuty request failed with unknown status code"
    else:
        message = f"PagerDuty request failed: {result.reason}"

    return PDSchedulingNetworkException(
        message=message,
        status_code=None if result is None else result.status_code,
        reason=None if result is None else result.reason,
    )


class PagerDuty:
    def __init__(self, token):
        self.token = token

    def headers(self):
        return {
            "content-type": "application/json",
            "Authorization": f"Token token={self.token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

    def get_users(self, teams: Optional[List[str]] = None):
        """Fetches all users

        :return: A list of users
        """

        # TODO: add support for pagination
        session = APISession(self.token)
        try:
            params = {"include[]": "teams"}
            if teams:
                params["team_ids[]"] = ",".join(teams)
            users = list(session.iter_all("users", params=params))
        except PDClientError as e:
            raise _create_scheduling_exception(e.response) from e
        return users

    def schedules(self, query=""):
        """Fetches all schedules by default or some specific by name

        :param query: Use query to fetch specific schedule
        :return: A list of schedules
        """
        # TODO: add support for pagination
        result = None
        try:
            result = requests.get(
                url=f"https://api.pagerduty.com/schedules?limit=100&query={query}",
                headers=self.headers(),
            )
            result.raise_for_status()
        except requests.RequestException as e:
            raise _create_scheduling_exception(result) from e
        return result.json()["schedules"]

    def get_schedule(self, *, schedule_id):
        """Fetches specific schedule by id

        :param schedule_id:
        :return: A schedule
        """
        result = None
        try:
            result = requests.get(
                url=f"https://api.pagerduty.com/schedules/{schedule_id}",
                headers=self.headers(),
            )
            result.raise_for_status()
        except requests.RequestException as e:
            raise _create_scheduling_exception(result) from e
        return result.json()

    def create_schedule(self, *, name: str, hours: List[Optional[str]]):
        """Creates a schedule with specific name and assignments based on hours array

        :param name: A schedule name
        :param hours: A list of size 24*7 with each entry a user id assigned for the hour
        :return: Created schedule
        """
        data = _generate_schedule_data(name, hours, [], None)

        result = None
        try:
            result = requests.post(
                url="https://api.pagerduty.com/schedules",
                headers=self.headers(),
                data=json.dumps(data),
            )
            result.raise_for_status()
        except requests.RequestException as e:
            raise _create_scheduling_exception(result) from e
        return result

    def update_schedule(
        self, *, schedule_id: str, name: str, hours: List[Optional[str]]
    ):
        """Updates existing schedule in place

        :param schedule_id: A schedule id
        :param name: A name which will be assigned to schedule
        :param hours: A list of size 24*7 with each entry a user id assigned for the hour
        :return: Updated schedule
        """
        current_schedule = self.get_schedule(schedule_id=schedule_id)
        layers_ids = [
            layer["id"] for layer in current_schedule["schedule"]["schedule_layers"]
        ]

        data = _generate_schedule_data(name, hours, layers_ids, schedule_id)

        result = None
        try:
            result = requests.put(
                url=f"https://api.pagerduty.com/schedules/{schedule_id}",
                headers=self.headers(),
                data=json.dumps(data),
            )
            result.raise_for_status()
        except requests.RequestException as e:
            raise _create_scheduling_exception(result) from e
        return result

    def create_or_update_schedule(self, *, name: str, hours: List[Optional[str]]):
        """Creates or updates a schedule with specific name and assignments users based on hours array

        :param name: A schedule name
        :param hours: A list of size 24*7 with each entry a user id assigned for the hour
        :return: Created or updated schedule
        """
        schedules = self.schedules(query=name)
        if schedules:
            assert len(schedules) == 1
            self.update_schedule(schedule_id=schedules[0]["id"], name=name, hours=hours)
        else:
            self.create_schedule(name=name, hours=hours)
