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
"""Kubernetes client and data collection."""

import collections
import datetime
import functools
import json

import kubernetes
import kubernetes.client
import kubernetes.utils.quantity

kubernetes.config.load_incluster_config()
configuration = kubernetes.client.Configuration.get_default_copy()
# Otherwise we get: Missing Authority Key Identifier
configuration.verify_ssl = False
kubernetes.client.Configuration.set_default(configuration)


# Number of objects to fetch per request when listing large collections.
# Keeping pages small keeps memory use low when listing every pod in the
# cluster.
PAGE_SIZE = 250


def parse_quantity(val):
    """Parse kubernetes quantity like 200Mi to a decimal number."""
    return kubernetes.utils.quantity.parse_quantity(val)


def parse_time(val):
    """Parse a kubernetes timestamp like 2019-03-10T22:13:41Z."""
    if not val:
        return None
    return datetime.datetime.fromisoformat(val)


def list_raw(func, **kwargs):
    """Iterate over all objects returned by a list_* API function.

    Results are fetched in pages and parsed as plain JSON. This avoids
    building kubernetes model objects, which use much more memory than the
    data they hold.
    """
    token = None
    while True:
        resp = func(
            limit=PAGE_SIZE,
            _continue=token,
            _preload_content=False,
            **kwargs,
        )
        data = json.loads(resp.data)
        yield from data["items"]
        token = data["metadata"].get("continue")
        if not token:
            return


def slim_pod(pod):
    """Keep only the parts of a pod that are shown in pod lists.

    The structure and names match the kubernetes model objects so that the
    same templates can display either.
    """
    status = pod.get("status", {})
    return {
        "metadata": {
            "name": pod["metadata"]["name"],
            "namespace": pod["metadata"]["namespace"],
            "labels": pod["metadata"].get("labels"),
        },
        "spec": {
            "node_name": pod["spec"].get("nodeName"),
        },
        "status": {
            "phase": status.get("phase"),
            "start_time": parse_time(status.get("startTime")),
            "container_statuses": [
                {
                    "ready": cs.get("ready"),
                    "restart_count": cs.get("restartCount", 0),
                }
                for cs in status.get("containerStatuses") or []
            ],
        },
    }


def is_webservice(pod):
    """Check if a pod was started by `webservice`."""
    labels = pod["metadata"].get("labels") or {}
    if labels.get("app.kubernetes.io/managed-by") == "webservice":
        return True
    # Label used by older versions of webservice
    return labels.get("tools.wmflabs.org/webservice") == "true"


@functools.lru_cache()
def corev1_client():
    """Get CoreV1 API client."""
    return kubernetes.client.CoreV1Api()


@functools.lru_cache()
def appsv1_client():
    """Get AppsV1 API client."""
    return kubernetes.client.AppsV1Api()


@functools.lru_cache()
def batchv1_client():
    """Get BatchV1 API client."""
    return kubernetes.client.BatchV1Api()


@functools.lru_cache()
def custom_client():
    """Get CustomObjects API client."""
    return kubernetes.client.CustomObjectsApi()


def get_version():
    """Get version information about the Kubernetes cluster."""
    return kubernetes.client.VersionApi().get_code()


def get_pods(namespace):
    """Get a list of all pods in a namespace."""
    v1 = corev1_client()
    return {
        "items": [
            slim_pod(pod)
            for pod in list_raw(v1.list_namespaced_pod, namespace=namespace)
        ],
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_services(namespace):
    """Get a list of all services in a namespace."""
    v1 = corev1_client()
    return {
        "items": v1.list_namespaced_service(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_httproutes(namespace):
    """Get a list of all HTTPRoutes in a namespace."""
    items = list(
        list_raw(
            custom_client().list_namespaced_custom_object,
            group="gateway.networking.k8s.io",
            version="v1",
            namespace=namespace,
            plural="httproutes",
        )
    )
    for item in items:
        item["metadata"]["creationTimestamp"] = parse_time(
            item["metadata"].get("creationTimestamp")
        )
    return {
        "items": items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_daemonsets(namespace):
    """Get a list of all daemonsets in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_daemon_set(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_deployments(namespace):
    """Get a list of all deployments in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_deployment(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_replicasets(namespace):
    """Get a list of all replicasets in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_replica_set(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_statefulsets(namespace):
    """Get a list of all statefulsets in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_stateful_set(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_cronjobs(namespace):
    """Get a list of all cronjobs in a namespace."""
    v1 = batchv1_client()
    return {
        "items": v1.list_namespaced_cron_job(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_jobs(namespace):
    """Get a list of all jobs in a namespace."""
    v1 = batchv1_client()
    return {
        "items": v1.list_namespaced_job(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_pod(namespace, pod):
    """Get details for a pod."""
    v1 = corev1_client()
    try:
        pod = v1.read_namespaced_pod(name=pod, namespace=namespace)
    except kubernetes.client.exceptions.ApiException as error:
        if error.status == 404:
            pod = {}
        else:
            raise
    return {
        "pod": pod,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_nodes_metrics():
    """Get information about active CPU and memory usage per node."""
    custom = custom_client()
    return {
        "items": custom.list_cluster_custom_object(
            "metrics.k8s.io", "v1beta1", "nodes"
        )["items"],
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_node_metrics(name):
    """Get information about active CPU and memory usage for a node."""
    custom = custom_client()
    return {
        "metrics": custom.get_cluster_custom_object(
            "metrics.k8s.io", "v1beta1", "nodes", name
        ),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_pods_metrics():
    """Get information about active CPU and memory usage per pod."""
    custom = custom_client()
    return {
        "items": custom.list_cluster_custom_object(
            "metrics.k8s.io", "v1beta1", "pods"
        )["items"],
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_nodes():
    """Get a list of all nodes in the cluster."""
    v1 = corev1_client()
    return {
        "items": v1.list_node().items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_node_pods(name):
    """Get a list of all pods running on a node."""
    v1 = corev1_client()
    return {
        "items": [
            slim_pod(pod)
            for pod in list_raw(
                v1.list_pod_for_all_namespaces,
                field_selector=f"spec.nodeName={name}",
            )
        ],
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_node(name):
    """Get data for a node in the cluster."""
    v1 = corev1_client()
    return {
        "node": v1.read_node(name),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_summary_metrics():
    """Get a set of summary metrics about the cluster."""
    data = {
        "control_nodes": 0,
        "worker_nodes": 0,
        "special_nodes": 0,
        "cpu_total": 0,
        "cpu_used": 0,
        "mem_total_bytes": 0,
        "mem_used_bytes": 0,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    for node in get_nodes()["items"]:
        if "-control-" in node.metadata.name:
            data["control_nodes"] += 1
        elif "-worker-" in node.metadata.name:
            data["worker_nodes"] += 1
            # Only count workers in system capacity numbers
            data["mem_total_bytes"] += parse_quantity(
                node.status.allocatable["memory"]
            )
            data["cpu_total"] += parse_quantity(node.status.allocatable["cpu"])
        else:
            data["special_nodes"] += 1

    for node in get_nodes_metrics()["items"]:
        if "-worker-" in node["metadata"]["name"]:
            data["mem_used_bytes"] += parse_quantity(node["usage"]["memory"])
            data["cpu_used"] += parse_quantity(node["usage"]["cpu"])

    return data


def get_quota(namespace):
    """Get quota information for a namespace."""
    v1 = corev1_client()

    quotas = v1.list_namespaced_resource_quota(namespace)
    if len(quotas.items) != 1:
        return {
            "quotas": {},
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    quota: kubernetes.client.V1ResourceQuotaStatus = quotas.items[0].status
    # A new quota has no usage reported yet
    used = quota.used or {}
    hard = quota.hard or {}

    data = {
        key: {
            "used": used.get(key, None),
            "hard": hard.get(key, None),
        }
        for key in sorted(set(list(used.keys()) + list(hard.keys())))
    }

    return {
        "quotas": data,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_cluster_summary():
    """Collect cluster wide data for the home, nodes and images pages.

    Every pod, cronjob and namespace in the cluster is read once,
    a page at a time, and only the counts and names that are displayed are
    kept. The result only contains plain values so it can be stored as
    JSON.
    """
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    v1 = corev1_client()
    active = set()
    node_pods = collections.defaultdict(int)
    images = collections.defaultdict(list)
    webservices = collections.defaultdict(set)
    total_pods = 0
    active_pods = 0

    for pod in list_raw(v1.list_pod_for_all_namespaces):
        ns = pod["metadata"]["namespace"]
        name = pod["metadata"]["name"]
        phase = pod.get("status", {}).get("phase")
        node = pod["spec"].get("nodeName")
        active.add(ns)
        total_pods += 1
        if phase in ["Pending", "Running"]:
            active_pods += 1
        if node and phase != "Succeeded":
            node_pods[node] += 1
        # Finished job pod (or similar), so ignore.
        if phase in ("Succeeded", "Failed"):
            continue
        for container in pod["spec"]["containers"]:
            images[container["image"]].append(
                [ns, name, container["name"], "pod"]
            )
            if is_webservice(pod):
                webservices[ns].add(container["image"])

    # T342848: track images from cronjobs
    # FIXME: this will double count any running job captured above
    for cron in list_raw(batchv1_client().list_cron_job_for_all_namespaces):
        ns = cron["metadata"]["namespace"]
        active.add(ns)
        tmpl = cron["spec"]["jobTemplate"]
        for container in tmpl["spec"]["template"]["spec"]["containers"]:
            images[container["image"]].append(
                [ns, cron["metadata"]["name"], container["name"], "cron"]
            )

    namespaces = [ns["metadata"]["name"] for ns in list_raw(v1.list_namespace)]

    metrics = get_summary_metrics()
    for key in ["cpu_total", "cpu_used", "mem_total_bytes", "mem_used_bytes"]:
        # Quantities are Decimal values which JSON cannot store
        metrics[key] = str(metrics[key])

    return {
        "home": {
            "generated": generated,
            "total_pods": total_pods,
            "active_pods": active_pods,
            "active_namespaces": len(active),
            "metrics": metrics,
        },
        "namespaces": {
            "generated": generated,
            "items": namespaces,
            "active": sorted(active),
        },
        "nodes": {
            "generated": generated,
            "pods": node_pods,
        },
        "images": {
            "generated": generated,
            "items": images,
        },
        "webservices": {
            "generated": generated,
            "items": {ns: sorted(i) for ns, i in webservices.items()},
        },
    }
