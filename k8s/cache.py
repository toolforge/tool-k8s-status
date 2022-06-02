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
import hashlib
import logging
import os
import pwd

import cachelib
import flask


logger = logging.getLogger(__name__)


@functools.lru_cache()
def cache():
    """Get cachelib cache."""
    return cachelib.RedisCache(
        host=flask.current_app.config["REDIS_HOST"],
        key_prefix=hashlib.sha256(
            "{0.pw_name}/{0.pw_dir}".format(pwd.getpwuid(os.getuid())).encode(
                "utf-8"
            )
        ).hexdigest(),
    )


def cached(key, expiry=3600):
    """Cache decorated function return value."""

    def real_cached(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            cache_key = "{}:{}{}".format(
                key,
                ";".join(str(arg) for arg in args),
                ";".join(
                    "{}={}".format(k, v)
                    for k, v in sorted(kwargs.items())
                    if k != "cached"
                ),
            )
            cached = kwargs.get("cached", True)
            r = cache().get(cache_key) if cached else None
            if r is None:
                if cached:
                    logger.debug("Cache miss for %s", cache_key)
                r = f(*args, **kwargs)
                cache().set(cache_key, r, timeout=expiry)
                logger.debug("Cached value for %s for %s", cache_key, expiry)
            return r

        return wrapper

    return real_cached
