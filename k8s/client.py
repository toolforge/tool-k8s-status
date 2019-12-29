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

from .cache import cache


kubernetes.config.load_incluster_config()


@functools.lru_cache()
def corev1_client():
    """Get CoreV1 API client."""
    return kubernetes.client.CoreV1Api()


@functools.lru_cache()
def appsv1_client():
    """Get CoreV1 API client."""
    return kubernetes.client.AppsV1Api()


def get_version():
    """Get version information about the Kuberenetes cluster."""
    return kubernetes.client.VersionApi().get_code()


def get_namespaces(cached=True):
    """Get a list of all namespaces in the cluster."""
    key = "namespaces"
    data = cache().get(key) if cached else None
    if not data:
        v1 = corev1_client()
        data = {
            "items": v1.list_namespace().items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=600)
    return data


def get_pods(namespace, cached=True):
    """Get a list of all pods in a namespace."""
    key = "pods:{}".format(namespace)
    data = cache().get(key) if cached else None
    if not data:
        v1 = corev1_client()
        data = {
            "items": v1.list_namespaced_pod(namespace=namespace).items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_services(namespace, cached=True):
    """Get a list of all services in a namespace."""
    key = "services:{}".format(namespace)
    data = cache().get(key) if cached else None
    if not data:
        v1 = corev1_client()
        data = {
            "items": v1.list_namespaced_service(namespace=namespace).items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_daemonsets(namespace, cached=True):
    """Get a list of all daemonsets in a namespace."""
    key = "daemonsets:{}".format(namespace)
    data = cache().get(key) if cached else None
    if not data:
        v1 = appsv1_client()
        data = {
            "items": v1.list_namespaced_daemon_set(namespace=namespace).items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_deployments(namespace, cached=True):
    """Get a list of all deployments in a namespace."""
    key = "deployments:{}".format(namespace)
    data = cache().get(key) if cached else None
    if not data:
        v1 = appsv1_client()
        data = {
            "items": v1.list_namespaced_deployment(namespace=namespace).items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_replicasets(namespace, cached=True):
    """Get a list of all replicasets in a namespace."""
    key = "replicasets:{}".format(namespace)
    data = cache().get(key) if cached else None
    if not data:
        v1 = appsv1_client()
        data = {
            "items": v1.list_namespaced_replica_set(namespace=namespace).items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_statefulsets(namespace, cached=True):
    """Get a list of all statefulsets in a namespace."""
    key = "statefulsets:{}".format(namespace)
    data = cache().get(key) if cached else None
    if not data:
        v1 = appsv1_client()
        data = {
            "items": v1.list_namespaced_stateful_set(
                namespace=namespace
            ).items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_all_pods(cached=True):
    """Get a list of all pods."""
    key = "pods:__all__"
    data = cache().get(key) if cached else None
    if not data:
        v1 = corev1_client()
        data = {
            "items": v1.list_pod_for_all_namespaces().items,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_pods_by_namespace(cached=True):
    """Get a collection of all Pods grouped by namespace."""
    key = "toolpods"
    data = cache().get(key) if cached else None
    if not data:
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
        cache().set(key, data, timeout=300)
    return data


def get_pod(namespace, pod, cached=True):
    """Get details for a pod."""
    key = "pods:{}:{}".format(namespace, pod)
    data = cache().get(key) if cached else None
    if not data:
        v1 = corev1_client()
        data = {
            "pod": v1.read_namespaced_pod(name=pod, namespace=namespace),
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        cache().set(key, data, timeout=300)
    return data


def get_images(cached=True):
    """Get information about Docker images in use in the cluster."""
    key = "images"
    data = cache().get(key) if cached else None
    if not data:
        data = {
            "items": collections.defaultdict(list),
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        for pod in get_all_pods(cached=cached)["items"]:
            for container in pod.spec.containers:
                data["items"][container.image].append(
                    (pod.metadata.namespace, pod.metadata.name)
                )
        cache().set(key, data, timeout=300)
    return data
