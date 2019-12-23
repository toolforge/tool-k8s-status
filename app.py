#!/usr/bin/env python3
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
"""Web UI for exploring a Toolfroge Kubernetes cluster."""
import logging
import os

import flask
import werkzeug.contrib.fixers

import k8s.client


app = flask.Flask(__name__)
app.wsgi_app = werkzeug.contrib.fixers.ProxyFix(app.wsgi_app)

# Load configuration from YAML file(s).
# See default_config.yaml for more information
__dir__ = os.path.dirname(__file__)
app.config.update(
    yaml.safe_load(open(os.path.join(__dir__, "default_config.yaml"))))
try:
    app.config.update(
        yaml.safe_load(open(os.path.join(__dir__, "config.yaml"))))
except IOError:
    # It is ok if there is no local config file
    pass

logging.getLogger().addHandler(flask.logging.default_handler)


@app.route("/")
def home():
    """Show basic cluster info."""
    ctx = {}
    try:
        cached = "purge" not in flask.request.args
        ctx.update(
            {
                "version": k8s.client.get_version(),
                # FIXME: discover project prefix for filtering
                "pods": k8s.client.get_tool_pods("tools", cached=cached),
            }
        )
    except Exception:
        app.logger.exception("Error collecting statistics")
    return flask.render_template("home.html", **ctx)


@app.route("/namespace/")
def namespaces():
    """List namespaces."""
    ctx = {}
    try:
        cached = "purge" not in flask.request.args
        # FIXME: discover project prefix for filtering
        ctx.update(
            {
                "namespaces": k8s.client.get_tool_namespaces(
                    "tools", cached=cached
                ),
            }
        )
    except Exception:
        app.logger.exception("Error collecting namespaces")
    return flask.render_template("namespaces.html", **ctx)


@app.route("/namespace/<namespace>/")
def namespace(namespace):
    """Get details for a given namespace."""
    ctx = {
        "namespace": namespace,
    }
    return flask.render_template("namespace.html", **ctx)


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    flask.flash("Requested URL not found.", "error")
    return flask.redirect(flask.url_for("home"))


@app.template_filter('contains')
def contains(haystack, needle):
    return needle in haystack
