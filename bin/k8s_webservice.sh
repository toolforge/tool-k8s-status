#!/usr/bin/env bash
#
#/ Usage: k8s_webservice.sh {start,stop,status,restart,shell,cron-start,cron-stop}
#/ Manage a webservice deployment on the Toolfroge Kubernetes cluster
#/
#/ positional arguments:
#/   {start,stop,status,restart,shell,debug,tail,cron-start,cron-stop}
#/     Action to perform
#
set -Eeuo pipefail

function usage {
    local status=${1:-0}
    # `grep` self for the usage message comment prefix and then cut off the
    # first few characters so that everything lines up.
    grep '^#/' <"$0" | cut -c4- 1>&2
    exit $status
}

function startsvc {
    local tool=${1:?startsvc expects a tool name}
    local domain="$(python3 -c 'from toolsws.config import load_config; print(load_config()["public_domain"])')"
    echo "Starting webservice..."
    cat <<EOF | /usr/bin/kubectl apply -f -
---
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    name: $tool
    toolforge: tool
    tool.toolforge.org/service: "true"
  name: $tool
spec:
  replicas: 1
  revisionHistoryLimit: 2
  selector:
    matchLabels:
      name: $tool
      toolforge: tool
      tool.toolforge.org/service: "true"
  template:
    metadata:
      labels:
        name: $tool
        toolforge: tool
        tool.toolforge.org/service: "true"
        # Everything is in the image, so skip the NFS mounts
        toolforge.org/mount-storage: none
    spec:
      # The serviceAccountName is special magic. Not for all tools.
      serviceAccountName: ${tool}-obs
      containers:
        #
        - name: webservice
          image: $image
          command:
            - launcher
            - web
          imagePullPolicy: Always
          ports:
          - containerPort: 8000
            name: http
            protocol: TCP
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 15
          resources:
            limits:
              cpu: 1
              memory: 2Gi
            requests:
              cpu: 250m
              memory: 768Mi
---
apiVersion: v1
kind: Service
metadata:
  labels:
    name: $tool
    toolforge: tool
    tool.toolforge.org/service: "true"
  name: $tool
spec:
  ports:
  - name: http
    port: 8000
    protocol: TCP
    targetPort: 8000
  selector:
    name: $tool
  type: ClusterIP
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  labels:
    name: $tool
    toolforge: tool
    tool.toolforge.org/service: "true"
  name: $tool
spec: 
  parentRefs:
    - namespace: istio-gateway
      name: toolforge
  hostnames:
    - $tool.$domain
  rules: 
    - backendRefs:
        - name: $tool
          port: 8000
EOF
}

function startcron {
    local tool=${1:?startcron expects a tool name}
    echo "Starting refresh cronjob..."
    # Not managed by `toolforge jobs` because the job needs the same service
    # account as the webservice to read objects in all namespaces.
    cat <<EOF | /usr/bin/kubectl apply -f -
---
apiVersion: batch/v1
kind: CronJob
metadata:
  labels:
    name: ${tool}-refresh
    toolforge: tool
  name: ${tool}-refresh
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Forbid
  startingDeadlineSeconds: 120
  successfulJobsHistoryLimit: 1
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 0
      activeDeadlineSeconds: 240
      ttlSecondsAfterFinished: 600
      template:
        metadata:
          labels:
            name: ${tool}-refresh
            toolforge: tool
            toolforge.org/mount-storage: none
        spec:
          serviceAccountName: ${tool}-obs
          restartPolicy: Never
          containers:
            - name: refresh
              image: $image
              imagePullPolicy: Always
              command:
                - launcher
                - refresh
              resources:
                limits:
                  cpu: 1
                  memory: 1536Mi
                requests:
                  cpu: 500m
                  memory: 1Gi
EOF
}
function stopcron {
    local tool=${1:?stopcron expects a tool name}
    echo "Stopping refresh cronjob..."
    /usr/bin/kubectl delete cronjob ${tool}-refresh
}
function stopsvc {
    local tool=${1:?stopsvc expects a tool name}
    echo "Stopping webservice..."
    /usr/bin/kubectl delete httproute $tool
    /usr/bin/kubectl delete svc $tool
    /usr/bin/kubectl delete deployment $tool
}

function shell {
    local tool=${1:?shell expects a tool name}
    local shell_image=${2:?shell expects an image}
    shift 2
    exec /usr/bin/kubectl run interactive \
        --image=$shell_image \
        --restart=Never \
        --command=true \
        --env=HOME=$HOME \
        --labels='toolforge=tool' \
        --rm=true \
        --overrides="{ \"spec\": { \"serviceAccount\": \"${tool}-obs\" } }" \
        --stdin=true \
        --tty=true \
        -- "$@"
}

function _get_pod {
    local tool=${1:?_get_pod expects a tool name}
    /usr/bin/kubectl get pods \
        --output=jsonpath={.items..metadata.name} \
        --selector=name=${tool}
}

wmcsproject=$(</etc/wmcs-project)
if ! [[ $USER == "${wmcsproject}."* ]]; then
    printf >&2 '%s: user name does not start with "%s": %s\n' "$0" "$wmcsproject" "$USER"
    usage 1
fi

prefix=$(($(echo -n $wmcsproject | wc -c) + 1))
tool="${USER:prefix}"
# Use the image of the deployer component when push-to-deploy is set up,
# otherwise the one from a manual `toolforge build start`.
if /usr/bin/kubectl get deployment deployer >/dev/null 2>&1; then
    default_image="tools-harbor.wmcloud.org/tool-${tool}/deployer:latest"
else
    default_image="tools-harbor.wmcloud.org/tool-${tool}/tool-${tool}:latest"
fi
image="${K8S_STATUS_IMAGE:-$default_image}"
cmd=${1:-help}

case $cmd in
start)
    startsvc "$tool"
    ;;
stop)
    stopsvc "$tool"
    ;;
cron-start)
    startcron "$tool"
    ;;
cron-stop)
    stopcron "$tool"
    ;;
status)
    /usr/bin/kubectl get pod $(_get_pod $tool)
    ;;
restart)
    /usr/bin/kubectl delete pod $(_get_pod $tool)
    ;;
shell)
    echo "Starting interactive shell..."
    shell "$tool" docker-registry.tools.wmflabs.org/toolforge-python313-sssd-base:latest /bin/bash -il
    ;;
debug)
    shell "$tool" "$image" launcher "flask --app app shell"
    ;;
tail)
    /usr/bin/kubectl logs -f $(_get_pod $tool)
    ;;
--help | -h | help)
    usage 0
    ;;
*)
    echo "Unknown command: ${cmd}" 1>&2
    usage 1
    ;;
esac
