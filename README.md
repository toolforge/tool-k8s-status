K8s status
==========

Browse the Toolforge Kubernetes cluster.

Deploy on Toolforge
-------------------
Your tool will need a service account with rights to query across namespaces.

```
$ ssh dev.toolforge.org
$ become $TOOL_NAME
$ toolforge envvars create K8S_STATUS_REDIS_PREFIX "$(openssl rand -hex 32)"
$ toolforge envvars create K8S_STATUS_SECRET_KEY "$(openssl rand -hex 32)"
$ curl -s https://gitlab.wikimedia.org/toolforge-repos/k8s-status/-/raw/main/toolforge.yaml | toolforge components config create
$ toolforge components deployment create
$ curl -s https://gitlab.wikimedia.org/toolforge-repos/k8s-status/-/raw/main/bin/k8s_webservice.sh | bash -s start
$ curl -s https://gitlab.wikimedia.org/toolforge-repos/k8s-status/-/raw/main/bin/k8s_webservice.sh | bash -s cron-start
```

`K8S_STATUS_REDIS_PREFIX` is a secret prefix for the cache keys in the shared
Toolforge redis. The tool will not start without it.

The webservice and the refresh CronJob need the `-obs` service account, so
they are created by `bin/k8s_webservice.sh` instead of `webservice` or
`toolforge jobs`. The image is built by the Toolforge build service for the
`deployer` component in `toolforge.yaml`. Each time it is deployed, the
deployer sets the webservice and the CronJob to the new image.

Pushes to `main` are deployed by GitLab CI. Create a token with
`toolforge components deploy-token create` and add it as a masked and
protected `TOOLS_DEPLOY_TOKEN` CI/CD variable. Without it the deploy job is
skipped.

How it works
------------
Pages about a single namespace, pod or node read their data directly
from the Kubernetes API when they are viewed. The rendered page is kept in
redis for 30 seconds so that reloading it does not query the API again.

The home, nodes, namespaces and images pages show data about the whole
cluster. Reading every pod in the cluster is slow, so a CronJob runs
`bin/refresh.py` every 5 minutes. It reads the cluster a page at a time, keeps
only the counts and names that are displayed, and stores the result in redis
as JSON. The webservice only ever reads this small summary.

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
