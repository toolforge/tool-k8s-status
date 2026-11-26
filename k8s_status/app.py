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
"""Web UI for exploring a Toolfroge Kubernetes cluster."""

import collections
import datetime
import functools
import logging
import os

import flask
import natsort
import yaml

from . import api
from .k8s import cache
from .k8s import client
from .k8s import summary

app = flask.Flask(__name__)

# Load configuration from YAML file(s).
# See default_config.yaml for more information
__dir__ = os.path.dirname(__file__)
app.config.update(
    yaml.safe_load(open(os.path.join(__dir__, "../default_config.yaml")))
)
try:
    app.config.update(
        yaml.safe_load(open(os.path.join(__dir__, "../config.yaml")))
    )
except OSError:
    # It is ok if there is no local config file
    pass
# Build service images don't mount NFS, so the secret key can also come from
# a Toolforge envvar.
if "K8S_STATUS_SECRET_KEY" in os.environ:
    app.config["SECRET_KEY"] = os.environ["K8S_STATUS_SECRET_KEY"]

logging.getLogger().addHandler(flask.logging.default_handler)

app.register_blueprint(api.bp)


def collect(ctx, name, func, *args, default=None):
    """Add the result of func(*args) to ctx as name.

    Errors are logged and default is used instead, so that one failed API
    call does not leave the rest of the page empty.
    """
    try:
        ctx[name] = func(*args)
    except Exception:
        app.logger.exception("Error collecting %s", name)
        flask.g.collect_failed = True
        ctx[name] = default


def cached_page(expiry=30):
    """Cache the rendered HTML of a page for a short time.

    Pages are only cached when every API call worked, and are never cached
    or served from cache while there are flashed messages waiting to be
    shown.
    """

    def real_cached_page(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if "_flashes" in flask.session:
                return f(*args, **kwargs)
            key = "page:" + flask.request.path
            try:
                html = cache.load(key)
            except Exception:
                app.logger.exception("Error loading %s from cache", key)
                html = None
            if html is not None:
                return html
            r = f(*args, **kwargs)
            if isinstance(r, str) and not flask.g.get("collect_failed"):
                try:
                    cache.store(key, r, expiry)
                except Exception:
                    app.logger.exception("Error storing %s in cache", key)
            return r

        return wrapper

    return real_cached_page


@app.route("/")
def home():
    """Show basic cluster info."""
    ctx = {}
    collect(ctx, "version", client.get_version)
    data = summary.get("home")
    if data:
        ctx.update(
            {
                "pods": data,
                "metrics": data["metrics"],
                "active_namespaces": data["active_namespaces"],
            }
        )
    return flask.render_template("home.html", **ctx)


@app.route("/robots.txt")
def robots_txt():
    """Return a deny-all robots policy."""
    return flask.Response(
        "User-Agent: *\nDisallow: /\n", mimetype="text/plain"
    )


@app.route("/favicon.ico")
def favicon():
    """Redirect browsers looking for a favicon to the real one."""
    return flask.redirect(flask.url_for("static", filename="favicon.png"))


@app.route("/healthz")
def healthz():
    """Respond to health check requests."""
    return "ok"


@app.route("/nodes/")
def nodes():
    """List nodes."""
    ctx = {}
    collect(ctx, "nodes", client.get_nodes, default={"items": []})
    collect(ctx, "metrics", client.get_nodes_metrics, default={"items": []})
    ctx["nodes"] = natsort.natsorted(
        ctx["nodes"]["items"], key=lambda node: node.metadata.name
    )
    ctx["metrics"] = {
        m["metadata"]["name"]: m for m in ctx["metrics"]["items"]
    }
    data = summary.get("nodes")
    ctx["pods"] = collections.defaultdict(int, data["pods"] if data else {})
    return flask.render_template("nodes.html", **ctx)


@app.route("/nodes/<name>/")
@cached_page()
def node(name):
    """Describe a node."""
    ctx = {}
    try:
        ctx["node"] = client.get_node(name)["node"]
    except Exception:
        app.logger.exception("Error collecting node %s", name)
        flask.flash(f"Node {name} not found.", "danger")
        return flask.redirect(flask.url_for("nodes"))
    collect(ctx, "metrics", client.get_node_metrics, name, default={})
    collect(ctx, "pods", client.get_node_pods, name, default={"items": []})
    ctx["metrics"] = ctx["metrics"].get("metrics", {})
    ctx["pods"] = ctx["pods"]["items"]
    return flask.render_template("node.html", **ctx)


@app.route("/namespaces/")
def namespaces():
    """List namespaces."""
    ctx = {}
    data = summary.get("namespaces")
    if data:
        ctx.update(
            {
                "namespaces": {
                    "items": [
                        {"metadata": {"name": name}} for name in data["items"]
                    ],
                },
                "active": set(data["active"]),
            }
        )
    else:
        ctx.update({"namespaces": {"items": []}, "active": set()})
    return flask.render_template("namespaces.html", **ctx)


@app.route("/namespaces/<namespace>/")
@cached_page()
def namespace(namespace):
    """Get details for a given namespace."""
    ctx = {
        "namespace": namespace,
    }
    empty = {"items": []}
    collect(ctx, "pods", client.get_pods, namespace, default=empty)
    collect(ctx, "services", client.get_services, namespace, default=empty)
    collect(ctx, "httproutes", client.get_httproutes, namespace, default=empty)
    collect(ctx, "daemonsets", client.get_daemonsets, namespace, default=empty)
    collect(
        ctx, "deployments", client.get_deployments, namespace, default=empty
    )
    collect(
        ctx, "replicasets", client.get_replicasets, namespace, default=empty
    )
    collect(
        ctx, "statefulsets", client.get_statefulsets, namespace, default=empty
    )
    collect(ctx, "cronjobs", client.get_cronjobs, namespace, default=empty)
    collect(ctx, "jobs", client.get_jobs, namespace, default=empty)
    collect(ctx, "quota", client.get_quota, namespace, default={"quotas": {}})
    return flask.render_template("namespace.html", **ctx)


@app.route("/namespaces/<namespace>/pods/<pod>/")
@cached_page()
def pod(namespace, pod):
    """Get details for a given pod."""
    ctx = {
        "namespace": namespace,
    }
    try:
        ctx.update({"pod": client.get_pod(namespace, pod)["pod"]})
    except Exception:
        app.logger.exception("Error collecting namespace %s", namespace)
        flask.flash(f"Error collecting pod {pod}.", "danger")
        return flask.redirect(flask.url_for("namespace", namespace=namespace))
    if ctx.get("pod"):
        return flask.render_template("pod.html", **ctx)
    else:
        flask.flash(f"Pod {pod} not found.", "danger")
        return flask.redirect(flask.url_for("namespace", namespace=namespace))


@app.route("/images/")
def images():
    """List all images in use on the cluster."""
    data = summary.get("images")
    return flask.render_template(
        "images.html", images=data if data else {"items": {}}
    )


@app.route("/images/<path:name>/")
def image(name):
    """List pods using an image."""
    data = summary.get("images")
    pods = data["items"].get(name, []) if data else []
    return flask.render_template("image.html", image=name, pods=pods)


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    if flask.request.path.startswith("/api/"):
        return api.response({"error": "Requested URL not found."}, 404)
    flask.flash("Requested URL not found.", "danger")
    return flask.redirect(flask.url_for("home"))


@app.template_filter("contains")
def contains(haystack, needle):
    """Search a haystack for a needle."""
    return needle in haystack


@app.template_filter("duration")
def duration(start, end=None, max_parts=3):
    """Compute a duration relative to the current time or a given time."""
    if start is None:
        return ""
    if end is None:
        end = datetime.datetime.now(tz=start.tzinfo)
    diff_secs = abs((end - start).total_seconds())
    parts = []
    if diff_secs > 31556952:
        parts.append(f"{int(diff_secs // 31556952)}y")
        diff_secs = diff_secs % 31556952
    if diff_secs > 604800:
        parts.append(f"{int(diff_secs // 604800)}w")
        diff_secs = diff_secs % 604800
    if diff_secs > 86400:
        parts.append(f"{int(diff_secs // 86400)}d")
        diff_secs = diff_secs % 86400
    if diff_secs > 3600:
        parts.append(f"{int(diff_secs // 3600)}h")
        diff_secs = diff_secs % 3600
    if diff_secs > 60:
        parts.append(f"{int(diff_secs // 60)}m")
        diff_secs = diff_secs % 60
    if diff_secs >= 1:
        parts.append(f"{int(diff_secs)}s")
    if not parts:
        parts.append(f"{int(diff_secs * 1000)}ms")
    parts = parts[:max_parts]
    return "".join(parts)


@app.template_filter("yaml")
def pprint_yaml(obj):
    """Dump an object as YAML."""
    return yaml.dump(obj, explicit_start=True, width=79, indent=2)


@app.template_filter("parse_quantity")
def parse_quantity(obj):
    """Parse kubernetes quantity like 200Mi to a decimal number."""
    return client.parse_quantity(obj)


@app.context_processor
def inject_base_variables():
    """Variables to be usable on all templates."""
    return {
        "project": app.config["PROJECT"],
        "toolsadmin_url": app.config["TOOLSADMIN_URL"],
        "banner": app.config.get("BANNER"),
    }
