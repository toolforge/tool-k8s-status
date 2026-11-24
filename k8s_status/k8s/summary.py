# -*- coding: utf-8 -*-
#
# This file is part of k8s-status
#
# Copyright (c) 2026 Wikimedia Foundation and contributors
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
"""Cluster wide summary data."""

import decimal

from . import cache
from . import client

# The summary is rebuilt by bin/refresh.py every few minutes. Keep it for
# longer than that so that a single failed run does not empty the pages.
EXPIRY = 3600

KEYS = ["home", "namespaces", "nodes", "images", "webservices"]

DECIMAL_METRICS = [
    "cpu_total",
    "cpu_used",
    "mem_total_bytes",
    "mem_used_bytes",
]


def refresh():
    """Collect the cluster summary and store it in the cache."""
    data = client.get_cluster_summary()
    for key in KEYS:
        cache.store(f"summary:{key}", data[key], EXPIRY)
    return data


def get(key):
    """Get stored summary data, or None if it has not been collected."""
    data = cache.load(f"summary:{key}")
    if data and key == "home":
        for name in DECIMAL_METRICS:
            data["metrics"][name] = decimal.Decimal(data["metrics"][name])
    return data
