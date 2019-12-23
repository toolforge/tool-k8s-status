K8s status
==========

Browse the Toolforge Kubernetes cluster.

Deploy on Toolforge
-------------------
Your tool will need a service account with rights to query across namespaces.

```
$ ssh dev.tools.wmflabs.org
$ become $TOOL_NAME
$ mkdir -p $HOME/www/python
$ git clone https://phabricator.wikimedia.org/source/tool-k8s-status.git \
  $HOME/www/python/src
$ webservice --backend=kubernetes python3.7 shell
$ python3 -m venv $HOME/www/python/venv
$ source $HOME/www/python/venv/bin/activate
$ pip install --upgrade pip
$ pip install -r $HOME/www/python/src/requirements.txt
$ exit
$ www/python/bin/k8s_webservice.sh start
```

License
-------
[GPL-3.0-or-later](//www.gnu.org/copyleft/gpl.html "GPL-3.0-or-later")
