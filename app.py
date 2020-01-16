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
import collections
import datetime
import logging
import os

import flask
import jinja2
import natsort
import werkzeug.contrib.fixers
import yaml

import k8s.client


app = flask.Flask(__name__)
app.wsgi_app = werkzeug.contrib.fixers.ProxyFix(app.wsgi_app)

# Load configuration from YAML file(s).
# See default_config.yaml for more information
__dir__ = os.path.dirname(__file__)
app.config.update(
    yaml.safe_load(open(os.path.join(__dir__, "default_config.yaml")))
)
try:
    app.config.update(
        yaml.safe_load(open(os.path.join(__dir__, "config.yaml")))
    )
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
                "pods": k8s.client.get_pods_by_namespace(cached=cached),
                "metrics": k8s.client.get_summary_metrics(cached=cached),
                "namespaces": k8s.client.get_active_namespaces(cached=cached)[
                    "namespaces"
                ],
            }
        )
    except Exception:
        app.logger.exception("Error collecting statistics")
    return flask.render_template("home.html", **ctx)


@app.route("/nodes/")
def nodes():
    """List nodes."""
    ctx = {}
    try:
        cached = "purge" not in flask.request.args
        pods = collections.defaultdict(int)
        for pod in k8s.client.get_all_pods(cached=cached)["items"]:
            pods[pod.spec.node_name] += 1

        ctx.update(
            {
                "nodes": k8s.client.get_nodes(cached=cached),
                "metrics": {
                    m["metadata"]["name"]: m
                    for m in k8s.client.get_nodes_metrics(cached=cached)[
                        "items"
                    ]
                },
                "pods": pods,
            }
        )
    except Exception:
        app.logger.exception("Error collecting nodes")
    return flask.render_template("nodes.html", **ctx)


@app.route("/nodes/<name>/")
def node(name):
    """Describe a node."""
    ctx = {}
    try:
        cached = "purge" not in flask.request.args
        ctx.update(
            {
                "node": k8s.client.get_node(name, cached=cached)["node"],
                "metrics": k8s.client.get_node_metrics(name, cached=cached)[
                    "metrics"
                ],
                "pods": [
                    pod
                    for pod in k8s.client.get_all_pods(cached=cached)["items"]
                    if pod.spec.node_name == name
                ],
            }
        )
    except Exception:
        app.logger.exception("Error collecting node")
    return flask.render_template("node.html", **ctx)


@app.route("/namespaces/")
def namespaces():
    """List namespaces."""
    ctx = {}
    try:
        cached = "purge" not in flask.request.args
        ctx.update(
            {
                "namespaces": k8s.client.get_namespaces(cached=cached),
                "active": k8s.client.get_active_namespaces(cached=cached)[
                    "namespaces"
                ],
            }
        )
    except Exception:
        app.logger.exception("Error collecting namespaces")
    return flask.render_template("namespaces.html", **ctx)


@app.route("/namespaces/<namespace>/")
def namespace(namespace):
    """Get details for a given namespace."""
    ctx = {
        "namespace": namespace,
    }
    try:
        cached = "purge" not in flask.request.args
        ctx.update(
            {
                "pods": k8s.client.get_pods(namespace, cached=cached),
                "services": k8s.client.get_services(namespace, cached=cached),
                "ingresses": k8s.client.get_ingresses(
                    namespace, cached=cached
                ),
                "daemonsets": k8s.client.get_daemonsets(
                    namespace, cached=cached
                ),
                "deployments": k8s.client.get_deployments(
                    namespace, cached=cached
                ),
                "replicasets": k8s.client.get_replicasets(
                    namespace, cached=cached
                ),
                "statefulsets": k8s.client.get_statefulsets(
                    namespace, cached=cached
                ),
                "jobs": k8s.client.get_jobs(namespace, cached=cached),
            }
        )
    except Exception:
        app.logger.exception("Error collecting namespace %s", namespace)
    return flask.render_template("namespace.html", **ctx)


@app.route("/namespaces/<namespace>/pods/<pod>/")
def pod(namespace, pod):
    """Get details for a given pod."""
    ctx = {
        "namespace": namespace,
    }
    try:
        cached = "purge" not in flask.request.args
        ctx.update(
            {"pod": k8s.client.get_pod(namespace, pod, cached=cached)["pod"]}
        )
    except Exception:
        app.logger.exception("Error collecting namespace %s", namespace)
    if "pod" in ctx and ctx["pod"]:
        tpl = "pod_dbg.html" if "debug" in flask.request.args else "pod.html"
        return flask.render_template(tpl, **ctx)
    else:
        flask.flash("Pod {} not found.".format(pod), "danger")
        return flask.redirect(flask.url_for("namespace", namespace=namespace))


@app.route("/namespaces/<namespace>/ingresses/<name>/")
def ingress(namespace, name):
    """Get details for a given ingress."""
    ctx = {
        "namespace": namespace,
    }
    try:
        cached = "purge" not in flask.request.args
        ctx.update(
            {
                "ingress": k8s.client.get_ingress(
                    namespace, name, cached=cached
                )["ingress"],
            }
        )
    except Exception:
        app.logger.exception("Error collecting namespace %s", namespace)
    if "ingress" in ctx and ctx["ingress"]:
        return flask.render_template("ingress.html", **ctx)
    else:
        flask.flash("Ingress {} not found.".format(name), "danger")
        return flask.redirect(flask.url_for("namespace", namespace=namespace))


@app.route("/images/")
def images():
    """List all images in use on the cluster."""
    ctx = {}
    try:
        cached = "purge" not in flask.request.args
        ctx.update({"images": k8s.client.get_images(cached=cached)})
    except Exception:
        app.logger.exception("Error collecting images")
    return flask.render_template("images.html", **ctx)


@app.route("/images/<path:name>/")
def image(name):
    """List pods using an image."""
    ctx = {
        "image": name,
    }
    try:
        cached = "purge" not in flask.request.args
        ctx.update(
            {"pods": k8s.client.get_images(cached=cached)["items"][name]}
        )
    except Exception:
        app.logger.exception("Error collecting image '%s'", name)
    return flask.render_template("image.html", **ctx)


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    flask.flash("Requested URL not found.", "danger")
    return flask.redirect(flask.url_for("home"))


@app.template_filter("contains")
def contains(haystack, needle):
    """Search a haystack for a needle."""
    return needle in haystack


@app.template_filter("duration")
def duration(start, end=None, max_parts=3):
    """Compute a duration relative to the current time or a given time."""
    if end is None:
        end = datetime.datetime.now(tz=start.tzinfo)
    diff_secs = abs((end - start).total_seconds())
    parts = []
    if diff_secs > 31556952:
        parts.append("{}y".format(int(diff_secs // 31556952)))
        diff_secs = diff_secs % 31556952
    if diff_secs > 604800:
        parts.append("{}w".format(int(diff_secs // 604800)))
        diff_secs = diff_secs % 604800
    if diff_secs > 86400:
        parts.append("{}d".format(int(diff_secs // 86400)))
        diff_secs = diff_secs % 86400
    if diff_secs > 3600:
        parts.append("{}h".format(int(diff_secs // 3600)))
        diff_secs = diff_secs % 3600
    if diff_secs > 60:
        parts.append("{}m".format(int(diff_secs // 60)))
        diff_secs = diff_secs % 60
    if diff_secs >= 1:
        parts.append("{}s".format(int(diff_secs)))
    if not parts:
        parts.append("{}ms".format(int(diff_secs * 1000)))
    parts = parts[:max_parts]
    return "".join(parts)


@app.template_filter("yaml")
def pprint_yaml(obj):
    """Dump an object as YAML."""
    return yaml.dump(obj, explicit_start=True, width=79, indent=2)


@app.template_filter("parse_quantity")
def parse_quantity(obj):
    """Parse kubernetes quantity like 200Mi to a decimal number."""
    return k8s.client.parse_quantity(obj)


@app.template_filter("natsort")
@jinja2.filters.environmentfilter
def filter_natsort(env, itr, reverse=False, attribute=None):
    """Sort an iterator by "natural" order."""
    key_func = jinja2.filters.make_attrgetter(env, attribute)
    return natsort.natsorted(itr, key=key_func, reverse=reverse)
