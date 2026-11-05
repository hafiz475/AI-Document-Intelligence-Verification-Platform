"""Dramatiq composition root.

Actors are introduced with Milestone 1 so the Milestone 0 worker never pretends
to process documents. Importing this module is sufficient for a healthy idle worker.
"""

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

redis_url = os.getenv("ASSUREAI_REDIS_URL", "redis://redis:6379/0")
dramatiq.set_broker(RedisBroker(url=redis_url))
