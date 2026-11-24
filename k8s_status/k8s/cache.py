# -*- coding: utf-8 -*-
#
# This file is part of k8s-status
#
# Copyright (c) 2019 Bryan Davis and contributors
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Caching object."""

import functools
import json
import logging
import os

import flask
import redis

logger = logging.getLogger(__name__)


def key_prefix():
    """Get the redis key prefix."""
    prefix = os.environ.get("K8S_STATUS_REDIS_PREFIX")
    if not prefix:
        raise RuntimeError("K8S_STATUS_REDIS_PREFIX is not set")
    return prefix


@functools.lru_cache()
def connection():
    """Get redis connection."""
    return redis.Redis(host=flask.current_app.config["REDIS_HOST"])


def load(key):
    """Load a value from the cache."""
    value = connection().get(key_prefix() + key)
    if value is None:
        logger.debug("Cache miss for %s", key)
        return None
    return json.loads(value)


def store(key, value, expiry):
    """Store a value in the cache."""
    # Values are stored as JSON rather than pickle. The Toolforge redis
    # server is shared and has no access control, so nothing read back from
    # it should be able to create arbitrary objects.
    connection().set(key_prefix() + key, json.dumps(value), ex=expiry)
    logger.debug("Cached value for %s for %s", key, expiry)
