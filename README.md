# PDScheduling - a library to create schedules in PagerDuty

[![CI](https://github.com/skrypka/pdscheduling/workflows/CI/badge.svg?branch=master)](https://github.com/skrypka/pdscheduling/actions)
[![PyPI](https://img.shields.io/pypi/v/pdscheduling)](https://pypi.org/project/pdscheduling/)

Just generate an array with a user for every hour for the next week - and the library will push it to PagerDuty.

Install: `pip install pdscheduling`

## Example:

```python
import random
from pdscheduling import PagerDuty

pd = PagerDuty("token")
users = pd.get_users()
schedule = []
for day in range(7):
    user = random.choice(users) # your fancy algorithm to select a user for the day
    for hour in range(24): # btw, the week starts in UTC timezone
        schedule += [user["id"]]
pd.create_or_update_schedule(name="Automatic Schedule", hours=schedule)
```

## Why library? Can I just use PagerDuty API?

You can, but it will be harder. PagerDuty don't give straightforward API for this, instead you need to create schedule
with a layer for every developer with proper restriction.

## Users of the library

The library is used by [https://optduty.com](https://optduty.com). A SaaS to schedule On-Call in a smart way.

## Consultancy

[DisOpt consultancy](https://disopt.com/) could help you use the library.
