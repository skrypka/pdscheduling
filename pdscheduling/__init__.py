import copy
import json
from typing import List, Optional

import requests

__version__ = "0.1.2"


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


def _generate_schedule_data(name, hours, layers_ids, schedule_id):
    assert len(hours) == 7 * 24
    all_users = list(set([id for id in hours if id]))
    assert len(all_users)
    layers = []
    for i, user in enumerate(all_users):
        restrictions = []
        for day in range(7):
            for hour in range(24):
                if hours[day * 24 + hour] == user:
                    restrictions.append(
                        {
                            "type": "weekly_restriction",
                            "start_day_of_week": day + 1,
                            "start_time_of_day": f"{hour:02d}:00:00",
                            "duration_seconds": 3600,
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

    def get_users(self):
        """Fetches all users

        :return: A list of users
        """

        # TODO: add support for pagination
        result = None
        try:
            result = requests.get(
                url="https://api.pagerduty.com/users?include%5B%5D=teams&limit=100",
                headers=self.headers(),
            )
            result.raise_for_status()
        except requests.RequestException as e:
            raise _create_scheduling_exception(result) from e
        return result.json()["users"]

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

        try:
            result = requests.put(
                url=f"https://api.pagerduty.com/schedules/{schedule_id}",
                headers=self.headers(),
                data=json.dumps(data),
            )
            result.raise_for_status()
        except requests.RequestException as e:
            raise PDSchedulingNetworkException from e
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
