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
import datetime
import functools

import kubernetes

from .cache import cache


kubernetes.config.load_incluster_config()


@functools.lru_cache()
def corev1_client():
    """Get CoreV1 API client."""
    return kubernetes.client.CoreV1Api()


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


def get_tool_namespaces(cached=True):
    """Get a list of all tool namespaces in the cluster."""
    all_ns = get_namespaces(cached)
    return {
        "items": [
            ns
            for ns in all_ns["items"]
            if ns.metadata.name.startswith("tool-")
        ],
        "generated": all_ns["generated"],
    }


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


def get_tool_pods(cached=True):
    """Get a collection of all Pods belonging to tools in the cluster."""
    key = "toolpods"
    data = cache().get(key) if cached else None
    if not data:
        data = {
            "namespaces": {},
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "active_namespaces": 0,
            "total": 0,
        }
        tool_ns = get_tool_namespaces(cached)
        for ns in tool_ns["items"]:
            name = ns.metadata.name
            data["namespaces"][name] = get_pods(name)
            pods = len(data["namespaces"][name])
            data["total"] += pods
            if pods > 0:
                data["active_namespaces"] += 1
        cache().set(key, data, timeout=300)
    return data
