#!/usr/bin/env bash
#
#/ Usage: k8s_webservice.sh {start,stop,status,restart,shell}
#/ Manage a webservice deployment on the Toolfroge Kubernetes cluster
#/
#/ positional arguments:
#/   {start,stop,status,restart,shell,debug,tail} Action to perform
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
    spec:
      # The serviceAccountName is special magic. Not for all tools.
      serviceAccountName: ${tool}-obs
      containers:
        #
        - name: webservice
          image: docker-registry.tools.wmflabs.org/toolforge-python39-sssd-web:latest
          command:
            - /usr/bin/webservice-runner
            - --type
            - uwsgi-python
            - --port
            - "8000"
          imagePullPolicy: Always
          ports:
          - containerPort: 8000
            name: http
            protocol: TCP
          workingDir: /data/project/${tool}/
          resources:
            limits:
              cpu: 1
              memory: 2Gi
            requests:
              cpu: 500m
              memory: 512Mi
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
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  labels:
    name: $tool
    toolforge: tool
    tool.toolforge.org/service: "true"
  name: $tool
spec:
  rules:
  - host: $tool.toolforge.org
    http:
      paths:
      - backend:
          service:
            name: $tool
            port:
              number: 8000
        path: /
        pathType: Prefix
EOF
}

function stopsvc {
    local tool=${1:?stopsvc expects a tool name}
    echo "Stopping webservice..."
    /usr/bin/kubectl delete ingress $tool
    /usr/bin/kubectl delete svc $tool
    /usr/bin/kubectl delete deployment $tool
}

function shell {
    local tool=${1:?shell expects a tool name}
    shift
    exec /usr/bin/kubectl run interactive \
        --image=docker-registry.tools.wmflabs.org/toolforge-python39-sssd-base:latest \
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

prefix=$(($(echo -n $wmcsproject | wc -c)+1))
tool="${USER:prefix}"
cmd=${1:-help}

case $cmd in
    start)
        startsvc "$tool"
    ;;
    stop)
        stopsvc "$tool"
    ;;
    status)
        /usr/bin/kubectl get pod $(_get_pod $tool)
    ;;
    restart)
        /usr/bin/kubectl delete pod $(_get_pod $tool)
    ;;
    shell)
        echo "Starting interactive shell..."
        shell "$tool" /bin/bash -il
    ;;
    debug)
        shell "$tool" bash -c "cd $HOME/www/python/src && $HOME/www/python/venv/bin/flask shell"
    ;;
    tail)
        /usr/bin/kubectl logs -f $(_get_pod $tool)
    ;;
    --help|-h|help)
        usage 0
    ;;
    *)
        echo "Unknown command: ${cmd}" 1>&2
        usage 1
    ;;
esac
