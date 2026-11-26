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
"""Point the webservice and the refresh CronJob at a new build.

Run as the ``deployer`` component by the Toolforge components service. Each
deployment of a new build restarts this component with the new image, and
it copies that image to the webservice Deployment and the refresh CronJob
created by ``k8s_webservice.sh``. Those can't be managed by the components
service because they need the ``-obs`` service account to read objects in
all namespaces.

The tool's own credentials are used, so the component needs ``mount: all``
to read them from the tool's home directory.
"""

import logging
import os
import signal
import sys
import time

import kubernetes
import urllib3

NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


def api_client(tool):
    """Get an API client using the tool's credentials."""
    config = kubernetes.client.Configuration()
    kubernetes.config.load_kube_config(
        config_file=f"/data/project/{tool}/.kube/config",
        client_configuration=config,
    )
    # Same as k8s_status.k8s.client, the cluster CA fails Python's checks.
    config.verify_ssl = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return kubernetes.client.ApiClient(config)


def own_image(core, namespace):
    """Get the exact image this pod is running."""
    pod = core.read_namespaced_pod(os.environ["HOSTNAME"], namespace)
    for status in pod.status.container_statuses or []:
        if status.image_id:
            # image_id includes the digest, so later builds can't change it
            return status.image_id
    return pod.spec.containers[0].image


def patch(name, func, body):
    """Apply a patch, logging instead of failing if the object is missing."""
    try:
        func(body)
    except kubernetes.client.exceptions.ApiException as error:
        if error.status != 404:
            raise
        logging.warning("%s not found, start it with k8s_webservice.sh", name)
        return
    logging.info("Updated %s", name)


def main():
    """Copy this pod's image to the webservice and the refresh CronJob."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    # exit cleanly when a new deployment replaces this pod, instead of being
    # killed after the grace period and reported as a failed job.
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

    with open(NAMESPACE_FILE) as f:
        namespace = f.read().strip()
    tool = namespace.removeprefix("tool-")
    client = api_client(tool)
    core = kubernetes.client.CoreV1Api(client)
    apps = kubernetes.client.AppsV1Api(client)
    batch = kubernetes.client.BatchV1Api(client)

    image = own_image(core, namespace)
    logging.info("Deploying %s", image)
    patch(
        f"deployment {tool}",
        lambda body: apps.patch_namespaced_deployment(tool, namespace, body),
        {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": "webservice", "image": image}]
                    }
                }
            }
        },
    )
    patch(
        f"cronjob {tool}-refresh",
        lambda body: batch.patch_namespaced_cron_job(
            f"{tool}-refresh", namespace, body
        ),
        {
            "spec": {
                "jobTemplate": {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {"name": "refresh", "image": image}
                                ]
                            }
                        }
                    }
                }
            }
        },
    )

    # The components service runs this as a continuous job, so stay up until
    # the next deployment replaces it.
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
