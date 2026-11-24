#!/usr/bin/env python3
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
"""Refresh the cluster summary shown by the web UI.

Run by the refresh CronJob created with `k8s_webservice.sh cron-start`.
"""

import logging
import os
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from k8s_status.app import app  # noqa: E402
from k8s_status.k8s import summary  # noqa: E402


def main():
    """Collect and store the cluster summary."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    start = time.monotonic()
    with app.app_context():
        data = summary.refresh()
    logging.info(
        "Refreshed summary for %d pods in %.1fs, peak memory %d MiB",
        data["home"]["total_pods"],
        time.monotonic() - start,
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
    )


if __name__ == "__main__":
    main()
