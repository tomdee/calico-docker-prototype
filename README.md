# Calico docker prototype
This prototype demonstrates Calico running in a docker environment.

## What the prototype consists of
There are several components to the prototype.

+ It shows that Felix and the ACL Manager can run in docker containers on the host.

+ It shows that bird (BGP) servers can be installed and run on a docker container on the host, and can configure routing between endpoints (containers in this case).

+ It shows that it is possible to write a plugin that interoperates successfully with Felix and the ACL Manager to report status and program endpoints.

It has some important restrictions.

+ Although a sample Felix and ACL Manager install is provided, it is not of the latest code (although there is no good reason why it cannot be updated).

+ The plugin is just a simple script reading a text file, not a proper plugin that is associated with the orchestration. Although the Calico code supports an arbitrarily complex networking model with complex rules and groups, the plugin configures a single security group with hard-coded rules.

+ The "orchestration" itself is just a script that configures the networking for a docker container and writes the content to file.

+ Last but not lease, it isn't a fully fledged demo; to run it on your own system you'll need to (for example) change the code to have the IP addresses of your own servers.


## How to install and run it.
The installation assumes two servers with IP addresses 172.18.197.87 and 172.18.197.88; you'll need to update these in a number of places.

### Prerequisites
You'll need at least one host, and ideally two.

+ Various docker images are provided - load them on your hosts.

+ This assumes a CoreOS installation. It probably works on other installations too.

+ On each host, run the following commands.

    modprobe ip6_tables
    mkdir /var/log/calico
    mkdir /opt/plugin
    mkdir /opt/plugin/data
    

### Felix and the ACL manager

+ There are IP addresses in the config files in `/etc/calico/` of the felix:v3 image. Change them to the IP address of the first host then update the image.

+ Start up Felix and the ACL manager on each host.

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="Felix" --net=host --restart=always -t felix:v3 /usr/bin/calico-felix --config-file /etc/calico/felix.cfg
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="ACLMgr" --net=host --restart=always -t felix:v3 /usr/bin/calico-acl-manager --config-file /etc/calico/acl_manager.cfg

The ACL manager should only run once (due to limited prototype plugin code), but it is fine to have two instances of Felix.

### Start up bird.

+ There are bird configuration files in `/etc/bird/bird72.conf` and `/etc/bird/bird73.conf`; you'll need to edit these with your configuration changing IPs appropriately.

+ Start up bird on each host.

        docker run -d --privileged=true --name="bird" --net=host --restart=always -t felix:bird /usr/bin/run_bird -c /etc/bird/bird72.conf -s /var/run/bird.ctl

### Create some configuration for Felix
+ First, you'll need to create a config file with information about Felix and the ACL manager. Use `felix.txt` as a base and copy it into `/opt/plugin/data`.

+ Next create some containers with the script `create_container.sh`, which both creates a container and configures the networking. It doesn't do anything useful with the container at all; to test properly you'll want to
  try tweaking the script, but it does at least show you what commands need to be run and what the format of the config file is.

### Trigger the plugin
The easiest way to run the plugin is by creating a container with the right packages, but run it from the command line.

    docker run -i --privileged=true --name="plugin" --net=host -v /opt/plugin:/opt/plugin -t felix:plugin /bin/bash
    cd /opt/plugin
    python plugin.py


