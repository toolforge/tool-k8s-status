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
import os
import pwd

import cachelib
import flask


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
                ";".join(args),
                ";".join(
                    "{}={}".format(k, v)
                    for k, v in kwargs.items()
                    if k != "cached"
                ),
            )
            cached = kwargs.get("cached", True)
            r = cache().get(cache_key) if cached else None
            if r is None:
                r = f(*args, **kwargs)
                cache().set(key, r, timeout=expiry)
            return r

        return wrapper

    return real_cached
