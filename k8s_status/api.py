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
"""Machine readable API.

Every response is plain JSON built from the raw Kubernetes API responses, so
no kubernetes model objects are created here.
"""

import datetime
import json
import logging

import flask
import kubernetes.client

from .k8s import cache
from .k8s import client

logger = logging.getLogger(__name__)

bp = flask.Blueprint("api", __name__, url_prefix="/api/v1")

# How long live responses are kept in redis
EXPIRY = 30


def response(data, status=200):
    """Send data as a JSON API response."""
    resp = flask.jsonify(data)
    resp.status_code = status
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def error(message, status):
    """Send an error as a JSON API response."""
    return response({"error": message}, status)


def generated():
    """Get the timestamp used in the generated field."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def live(key, func, *args):
    """Call func with args, keeping the result in redis for a short time."""
    key = f"api:{key}"
    try:
        data = cache.load(key)
    except Exception:
        logger.exception("Error loading %s from cache", key)
        data = None
    if data is None:
        data = func(*args)
        try:
            cache.store(key, data, EXPIRY)
        except Exception:
            logger.exception("Error storing %s in cache", key)
    return data


def from_summary(key):
    """Send stored summary data as a JSON API response."""
    data = cache.load(f"summary:{key}")
    if data is None:
        return error("Cluster data has not been collected yet.", 503)
    return response(data)


def known_namespace(namespace):
    """Check a namespace against the stored summary."""
    data = cache.load("summary:namespaces")
    # Without a summary there is no way to tell, so let the API decide
    return data is None or namespace in data["items"]


def without_managed_fields(obj):
    """Drop metadata.managedFields, which is large and not interesting."""
    obj.get("metadata", {}).pop("managedFields", None)
    return obj


def containers(spec):
    """List the name and image of each container in a pod spec."""
    return [
        {"name": c["name"], "image": c["image"]} for c in spec["containers"]
    ]


def pod_info(pod):
    """Summarize a pod."""
    status = pod.get("status", {})
    statuses = status.get("containerStatuses") or []
    return {
        "name": pod["metadata"]["name"],
        "namespace": pod["metadata"]["namespace"],
        "labels": pod["metadata"].get("labels") or {},
        "webservice": client.is_webservice(pod),
        "phase": status.get("phase"),
        "node": pod["spec"].get("nodeName"),
        "start_time": status.get("startTime"),
        "ready": sum(1 for cs in statuses if cs.get("ready")),
        "containers_total": len(pod["spec"]["containers"]),
        "restarts": sum(cs.get("restartCount", 0) for cs in statuses),
        "containers": containers(pod["spec"]),
    }


def workload_info(obj):
    """Summarize a deployment, replicaset, statefulset or daemonset."""
    status = obj.get("status", {})
    if "desiredNumberScheduled" in status:
        # DaemonSets count scheduled pods rather than replicas
        replicas = status.get("desiredNumberScheduled")
        ready = status.get("numberReady", 0)
    else:
        replicas = obj["spec"].get("replicas")
        ready = status.get("readyReplicas", 0)
    return {
        "name": obj["metadata"]["name"],
        "labels": obj["metadata"].get("labels") or {},
        "replicas": replicas,
        "ready": ready,
        "created": obj["metadata"].get("creationTimestamp"),
        "containers": containers(obj["spec"]["template"]["spec"]),
    }


def service_info(svc):
    """Summarize a service."""
    return {
        "name": svc["metadata"]["name"],
        "labels": svc["metadata"].get("labels") or {},
        "type": svc["spec"].get("type"),
        "cluster_ip": svc["spec"].get("clusterIP"),
        "ports": [
            {
                "name": p.get("name"),
                "port": p.get("port"),
                "protocol": p.get("protocol"),
                "target_port": p.get("targetPort"),
            }
            for p in svc["spec"].get("ports") or []
        ],
        "created": svc["metadata"].get("creationTimestamp"),
    }


def ingress_info(ing):
    """Summarize an ingress."""
    return {
        "name": ing["metadata"]["name"],
        "labels": ing["metadata"].get("labels") or {},
        "hosts": [r.get("host") for r in ing["spec"].get("rules") or [] if r],
        "created": ing["metadata"].get("creationTimestamp"),
    }


def cronjob_info(cron):
    """Summarize a cronjob."""
    tmpl = cron["spec"]["jobTemplate"]["spec"]["template"]
    return {
        "name": cron["metadata"]["name"],
        "labels": cron["metadata"].get("labels") or {},
        "schedule": cron["spec"]["schedule"],
        "suspend": cron["spec"].get("suspend", False),
        "last_schedule_time": cron.get("status", {}).get("lastScheduleTime"),
        "containers": containers(tmpl["spec"]),
    }


def job_info(job):
    """Summarize a job."""
    status = job.get("status", {})
    return {
        "name": job["metadata"]["name"],
        "labels": job["metadata"].get("labels") or {},
        "active": status.get("active", 0),
        "succeeded": status.get("succeeded", 0),
        "failed": status.get("failed", 0),
        "start_time": status.get("startTime"),
        "completion_time": status.get("completionTime"),
        "containers": containers(job["spec"]["template"]["spec"]),
    }


def quota_info(namespace):
    """Get used and hard quota values for a namespace."""
    quotas = list(
        client.list_raw(
            client.corev1_client().list_namespaced_resource_quota,
            namespace=namespace,
        )
    )
    if len(quotas) != 1:
        return {}
    status = quotas[0].get("status", {})
    used = status.get("used") or {}
    hard = status.get("hard") or {}
    return {
        key: {"used": used.get(key), "hard": hard.get(key)}
        for key in sorted(set(used) | set(hard))
    }


def collect_namespace(namespace):
    """Collect everything shown on the namespace page."""
    core = client.corev1_client()
    apps = client.appsv1_client()
    batch = client.batchv1_client()
    net = client.networkingv1_client()

    def items(func, info):
        return [info(o) for o in client.list_raw(func, namespace=namespace)]

    return {
        "namespace": namespace,
        "generated": generated(),
        "pods": items(core.list_namespaced_pod, pod_info),
        "services": items(core.list_namespaced_service, service_info),
        "ingresses": items(net.list_namespaced_ingress, ingress_info),
        "deployments": items(apps.list_namespaced_deployment, workload_info),
        "replicasets": items(apps.list_namespaced_replica_set, workload_info),
        "statefulsets": items(
            apps.list_namespaced_stateful_set, workload_info
        ),
        "daemonsets": items(apps.list_namespaced_daemon_set, workload_info),
        "cronjobs": items(batch.list_namespaced_cron_job, cronjob_info),
        "jobs": items(batch.list_namespaced_job, job_info),
        "quota": quota_info(namespace),
    }


def read_raw(func, *args):
    """Read a single object as plain JSON, or None if it does not exist."""
    try:
        resp = func(*args, _preload_content=False)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            return None
        raise
    return without_managed_fields(json.loads(resp.data))


def collect_pod(namespace, name):
    """Get a pod as returned by the Kubernetes API."""
    pod = read_raw(client.corev1_client().read_namespaced_pod, name, namespace)
    return {"generated": generated(), "pod": pod}


def collect_ingress(namespace, name):
    """Get an ingress as returned by the Kubernetes API."""
    ingress = read_raw(
        client.networkingv1_client().read_namespaced_ingress, name, namespace
    )
    return {"generated": generated(), "ingress": ingress}


def node_info(node, usage, pods):
    """Summarize a node."""
    status = node.get("status", {})
    ready = [
        c["status"] == "True"
        for c in status.get("conditions") or []
        if c["type"] == "Ready"
    ]
    return {
        "name": node["metadata"]["name"],
        "labels": node["metadata"].get("labels") or {},
        "ready": bool(ready and ready[0]),
        "unschedulable": node["spec"].get("unschedulable", False),
        "kubelet_version": status.get("nodeInfo", {}).get("kubeletVersion"),
        "allocatable": {
            k: status.get("allocatable", {}).get(k) for k in ["cpu", "memory"]
        },
        "usage": usage,
        "pods": pods,
        "created": node["metadata"].get("creationTimestamp"),
    }


def collect_nodes():
    """Collect a summary of every node."""
    metrics = {
        m["metadata"]["name"]: m["usage"]
        for m in client.get_nodes_metrics()["items"]
    }
    data = cache.load("summary:nodes")
    pods = data["pods"] if data else {}
    nodes = [
        node_info(
            n,
            metrics.get(n["metadata"]["name"]),
            pods.get(n["metadata"]["name"], 0),
        )
        for n in client.list_raw(client.corev1_client().list_node)
    ]
    return {"generated": generated(), "items": nodes}


def collect_node(name):
    """Collect details about a node and the pods running on it."""
    node = read_raw(client.corev1_client().read_node, name)
    if node is None:
        return {"generated": generated(), "node": None}
    try:
        usage = client.get_node_metrics(name)["metrics"]["usage"]
    except Exception:
        logger.exception("Error collecting metrics for node %s", name)
        usage = None
    pods = [
        pod_info(p)
        for p in client.list_raw(
            client.corev1_client().list_pod_for_all_namespaces,
            field_selector=f"spec.nodeName={name}",
        )
    ]
    return {
        "generated": generated(),
        "node": without_managed_fields(node),
        "usage": usage,
        "pods": pods,
    }


@bp.route("/")
def index():
    """Point to the API documentation."""
    return response(
        {
            "docs": flask.url_for("api.docs", _external=True),
            "openapi": flask.url_for("api.openapi", _external=True),
        }
    )


@bp.route("/docs/")
def docs():
    """Show the API documentation."""
    return flask.render_template("api_docs.html")


@bp.route("/openapi.json")
def openapi():
    """Get the OpenAPI description of the API."""
    return flask.send_from_directory(
        flask.current_app.static_folder, "openapi.json"
    )


@bp.route("/summary/")
def cluster_summary():
    """Get cluster totals."""
    return from_summary("home")


@bp.route("/namespaces/")
def namespaces():
    """Get all namespaces."""
    return from_summary("namespaces")


@bp.route("/images/")
def images():
    """Get images in use on the cluster."""
    return from_summary("images")


@bp.route("/webservices/")
def webservices():
    """Get images used by webservice pods in each namespace."""
    return from_summary("webservices")


@bp.route("/namespaces/<namespace>/")
def namespace(namespace):
    """Get everything in a namespace."""
    if not known_namespace(namespace):
        return error(f"Namespace {namespace} not found.", 404)
    try:
        data = live(f"namespace:{namespace}", collect_namespace, namespace)
    except Exception:
        logger.exception("Error collecting namespace %s", namespace)
        return error(f"Error collecting namespace {namespace}.", 503)
    return response(data)


@bp.route("/namespaces/<namespace>/pods/<name>/")
def pod(namespace, name):
    """Get a pod."""
    try:
        data = live(f"pod:{namespace}:{name}", collect_pod, namespace, name)
    except Exception:
        logger.exception("Error collecting pod %s/%s", namespace, name)
        return error(f"Error collecting pod {name}.", 503)
    if data["pod"] is None:
        return error(f"Pod {name} not found.", 404)
    return response(data)


@bp.route("/namespaces/<namespace>/ingresses/<name>/")
def ingress(namespace, name):
    """Get an ingress."""
    try:
        data = live(
            f"ingress:{namespace}:{name}", collect_ingress, namespace, name
        )
    except Exception:
        logger.exception("Error collecting ingress %s/%s", namespace, name)
        return error(f"Error collecting ingress {name}.", 503)
    if data["ingress"] is None:
        return error(f"Ingress {name} not found.", 404)
    return response(data)


@bp.route("/nodes/")
def nodes():
    """Get all nodes."""
    try:
        data = live("nodes", collect_nodes)
    except Exception:
        logger.exception("Error collecting nodes")
        return error("Error collecting nodes.", 503)
    return response(data)


@bp.route("/nodes/<name>/")
def node(name):
    """Get a node and the pods running on it."""
    try:
        data = live(f"node:{name}", collect_node, name)
    except Exception:
        logger.exception("Error collecting node %s", name)
        return error(f"Error collecting node {name}.", 503)
    if data["node"] is None:
        return error(f"Node {name} not found.", 404)
    return response(data)
