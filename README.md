K8s status
==========

Browse the Toolforge Kubernetes cluster.

Generate the requirements.txt file
----------------------------------

```
$ poetry export --without-hashes -f requirements.txt -o requirements.txt
````

Deploy on Toolforge
-------------------
Your tool will need a service account with rights to query across namespaces.

```
$ ssh dev.toolforge.org
$ become $TOOL_NAME
$ mkdir -p $HOME/www/python
$ git clone https://gitlab.wikimedia.org/toolforge-repos/k8s-status $HOME/www/python/src
$ webservice python3.13 shell
$ python3 -m venv $HOME/www/python/venv
$ source $HOME/www/python/venv/bin/activate
$ pip install --upgrade pip wheel
$ pip install -r $HOME/www/python/src/requirements.txt
$ exit
$ toolforge envvars create K8S_STATUS_REDIS_PREFIX "$(openssl rand -hex 32)"
$ www/python/src/bin/k8s_webservice.sh start
$ www/python/src/bin/k8s_webservice.sh cron-start
```

The `K8S_STATUS_REDIS_PREFIX` envvar is a secret prefix for the cache keys in
the shared Toolforge redis. The tool will not start without it.

How it works
------------
Pages about a single namespace, pod, ingress or node read their data directly
from the Kubernetes API when they are viewed. The rendered page is kept in
redis for 30 seconds so that reloading it does not query the API again.

The home, nodes, namespaces and images pages show data about the whole
cluster. Reading every pod in the cluster is slow, so a CronJob runs
`bin/refresh.py` every 5 minutes. It reads the cluster a page at a time, keeps
only the counts and names that are displayed, and stores the result in redis
as JSON. The webservice only ever reads this small summary.

The CronJob uses the same `$TOOL_NAME-obs` service account as the webservice,
so it is managed by `k8s_webservice.sh cron-start` and `cron-stop` rather than
`toolforge jobs`.

API
---
The same data is available as JSON for other tools to use, under `/api/v1/`.
Interactive documentation is at `/api/v1/docs/` and the OpenAPI description
at `/api/v1/openapi.json`. Responses allow cross-origin requests.

The cluster wide endpoints (`summary`, `namespaces`, `images`,
`webservices`) come from the summary built by the CronJob, so they are at
most 5 minutes old. The others read the Kubernetes API directly and keep the
result for 30 seconds. Every response has a `generated` field saying when the
data was collected.

The API code is in `k8s_status/api.py`. If you change a response, update
`k8s_status/static/openapi.json` to match.

License
-------
[GPL-3.0-or-later](//www.gnu.org/copyleft/gpl.html "GPL-3.0-or-later")
