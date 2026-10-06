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
$ www/python/src/bin/k8s_webservice.sh start
$ toolforge jobs load $HOME/www/python/src/jobs.yaml
```

License
-------
[GPL-3.0-or-later](//www.gnu.org/copyleft/gpl.html "GPL-3.0-or-later")
