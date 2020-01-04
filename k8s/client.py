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
"""Kubernetes client and data collection."""
import collections
import datetime
import functools

import kubernetes

from .cache import cached


kubernetes.config.load_incluster_config()


@functools.lru_cache()
def corev1_client():
    """Get CoreV1 API client."""
    return kubernetes.client.CoreV1Api()


@functools.lru_cache()
def appsv1_client():
    """Get CoreV1 API client."""
    return kubernetes.client.AppsV1Api()


@functools.lru_cache()
def extV1b1_client():
    """Get ExtensionsV1beta1 API client."""
    return kubernetes.client.ExtensionsV1beta1Api()


@functools.lru_cache()
def custom_client():
    """Get CustomObjects API client."""
    return kubernetes.client.CustomObjectsApi()


def get_version():
    """Get version information about the Kuberenetes cluster."""
    return kubernetes.client.VersionApi().get_code()


@cached("namespaces", 600)
def get_namespaces(cached=True):
    """Get a list of all namespaces in the cluster."""
    v1 = corev1_client()
    return {
        "items": v1.list_namespace().items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("pods", 300)
def get_pods(namespace, cached=True):
    """Get a list of all pods in a namespace."""
    v1 = corev1_client()
    return {
        "items": v1.list_namespaced_pod(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("services", 300)
def get_services(namespace, cached=True):
    """Get a list of all services in a namespace."""
    v1 = corev1_client()
    return {
        "items": v1.list_namespaced_service(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("ingresses", 300)
def get_ingresses(namespace, cached=True):
    """Get a list of all ingresses in a namespace."""
    v1 = extV1b1_client()
    return {
        "items": v1.list_namespaced_ingress(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("daemonsets", 300)
def get_daemonsets(namespace, cached=True):
    """Get a list of all daemonsets in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_daemon_set(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("deployments", 300)
def get_deployments(namespace, cached=True):
    """Get a list of all deployments in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_deployment(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("replicasets", 300)
def get_replicasets(namespace, cached=True):
    """Get a list of all replicasets in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_replica_set(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("statefulsets", 300)
def get_statefulsets(namespace, cached=True):
    """Get a list of all statefulsets in a namespace."""
    v1 = appsv1_client()
    return {
        "items": v1.list_namespaced_stateful_set(namespace=namespace).items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("pods:__all__", 300)
def get_all_pods(cached=True):
    """Get a list of all pods."""
    v1 = corev1_client()
    return {
        "items": v1.list_pod_for_all_namespaces().items,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("toolpods", 300)
def get_pods_by_namespace(cached=True):
    """Get a collection of all Pods grouped by namespace."""
    data = {
        "namespaces": collections.defaultdict(list),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "active_namespaces": 0,
        "total_pods": 0,
    }
    for pod in get_all_pods(cached=cached)["items"]:
        ns = pod.metadata.namespace
        data["namespaces"][ns].append(pod)
        data["total_pods"] += 1
    data["active_namespaces"] = len(data["namespaces"].keys())
    return data


@cached("pods", 300)
def get_pod(namespace, pod, cached=True):
    """Get details for a pod."""
    v1 = corev1_client()
    return {
        "pod": v1.read_namespaced_pod(name=pod, namespace=namespace),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("images", 300)
def get_images(cached=True):
    """Get information about Docker images in use in the cluster."""
    data = {
        "items": collections.defaultdict(list),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    for pod in get_all_pods(cached=cached)["items"]:
        for container in pod.spec.containers:
            data["items"][container.image].append(
                (pod.metadata.namespace, pod.metadata.name)
            )
    return data


@cached("metrics:nodes", 300)
def get_node_metrics(cached=True):
    """Get information about active CPU and memory usage per node."""
    custom = custom_client()
    return {
        "items": custom.list_cluster_custom_object(
            "metrics.k8s.io", "v1beta1", "nodes"
        )["items"],
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("metrics:pods", 300)
def get_pod_metrics(cached=True):
    """Get information about active CPU and memory usage per pod."""
    custom = custom_client()
    return {
        "items": custom.list_cluster_custom_object(
            "metrics.k8s.io", "v1beta1", "pods"
        )["items"],
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@cached("metrics:summary", 300)
def get_summary_metrics(cached=True):
    """Get a set of summary metrics about the cluster."""
    data = {
        "control_nodes": 0,
        "worker_nodes": 0,
        "cpu_used": 0,
        "mem_used_mb": 0,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    for node in get_node_metrics(cached=cached)["items"]:
        if "-control-" in node["metadata"]["name"]:
            data["control_nodes"] += 1
        elif "-worker-" in node["metadata"]["name"]:
            data["worker_nodes"] += 1
        # Convert Ki to Mi
        data["mem_used_mb"] += int(node["usage"]["memory"][:-2]) * 2 ** -10
        # Convert nano to whole
        data["cpu_used"] += int(node["usage"]["cpu"][:-1]) * 10 ** -9
    return data
