# L2 Routed Docker Prototype
This prototype demonstrates Calico running in a docker environment with L2 routed compute hosts.

## How to install and run it.
The installation assumes two servers with IP addresses that you'll need to update these in a number of places (listed below). In the example config, these IP addresses are 10.240.254.171 and 10.240.58.221 for the first and second server respectively.

#### Prerequisites

1. You'll need at least one host, and ideally two (you can add more, but you'll need to make some further changes to the various configuration files). These should normally be running CoreOS.

2. Copy the whole of this git repository to both host servers as `/opt/demo` (the location isn't important, except in so far as it is used in the instructions).

3. Edit the IP addresses for the servers. These need to change in various places.
    + `felix.txt` at the root of the repository, which must have both IP addresses and hostnames (without qualification - up to the first dot) modified.
    + The Dockerfiles under the directories `felix` and `bird`.
    + The bird configuration assumes that your container addresses are in the `192.168.0.0/16` range; if they aren't, you'll need to edit `bird.conf`.

4. Build the four docker images, by executing the commands below. The fourth image is just a utility image that contains tools such as `wget`, `telnet` and `traceroute` - making testing connectivity easier - while the others contain real useful function.

        sudo docker build -t "calico:bird" /opt/demo/bird 
        sudo docker build -t "calico:plugin" /opt/demo/plugin
        sudo docker build -t "calico:felix" /opt/demo/felix
        sudo docker build -t "calico:util" /opt/demo/util

5. On each host, run the following commands (as root).

        modprobe ip6_tables
        modprobe xt_set
        mkdir /var/log/calico
        mkdir /var/run/netns
        mkdir /opt/plugin
        mkdir /opt/plugin/data

6. Copy the base config file with information about Felix and the ACL manager (recall that you editted this above). You only need to run this command on the first host.

        cp /opt/demo/felix.txt /opt/plugin/data

#### Start the containers

1. On the first host, run the following as root (to start Felix, the ACL Manager, and bird respectively).

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="aclmgr" --net=host --restart=always -t calico:felix calico-acl-manager --config-file=/etc/calico/acl_manager.cfg
        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird1.conf

2. On the second host, run the following as root (to start Felix and bird respectively). Note that the ACL Manager need only run on the first host, so is not started here.

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird2.conf

3. On the first host (only) start the plugin running. The plugin would normally be the part of the orchestration that informs the Calico components about the current state of the system. In this prototype, the plugin is just a simple python script that loads text config. Two instances are run, one for the network API and one for the Endpoint API. If you want more diagnostics, run them interactively from a bash container. *The plugin must run on the first server only.*

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin1" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py network
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin2" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py ep

    The plugin would normally be the part of the orchestration that informs the Calico components about the current state of the system. In this prototype, the plugin is just a simple python script that loads text config (which you will create shortly).
    
#### Create some configuration for Felix

Next create some containers, and network them. The simplest way of doing this is as follows.

+ Create the container with a command something like

        docker run -i -t --net=none --name=192_168_1_1 calico:util

    The name here is deliberately intended to be the IP address; picking sensible names makes it far simpler to keep track. *This creates an interactive container - so you'll need to keep creating ssh sessions for each container you create.*

+ Now network the container. This would normally be done by the orchestration, but in this demo it is done by a shell script. Sample usage is as follows.

        sh /opt/demo/network_container.sh CID IP GROUP

    Here
    * `CID` is the container ID as reported on the command line from `docker ps` (or from `docker run`).
    * `IP` is the IP address to assign.
    * `GROUP` is the name of the group. In this prototype, each endpoint is in a single group, and the other endpoints only have access to it if they are in the same group. Names are arbitrary.

+ If you networked a container on the first host, then you are done - the script creates files in `/opt/plugin/data`, then `cat`s everything in that directory to `/opt/plugin/data.txt` where the plugin reads is. If you networked a container on the second host, then you need to copy across the relevant container config file into `/opt/plugin/data` and manually recreate `/opt/plugin/data.txt`. On the first host, this involves something like the following commands.

        scp host1:/opt/plugin/data/192_168_1_1.txt /opt/plugin/data
        cat /opt/plugin/data/*.txt > /opt/plugin/data.txt

+ The plugin checks for configuration dynamically, but it might take quite some time (up to a minute or two) before it notices and passes through changes to Calico.

## Verifying that it works
Naturally, you'll want to check that it's doing what you expect. Good things to look at include the following.

* `ip route` shows you the routes on the servers. There should be one for each virtual interface (on both servers).

* `iptables` shows a whole range of rules controlling traffic.

* Verify that you can ping and telnet between the containers that you created above, if and only if you specified the same group name for them.

If things do go wrong (and it can be a little fiddly setting it up), then you can either just try restarting some or all the processes or take a look at the logs.

* Logs from Felix and the ACL Manager are in `/var/log/calico/`.

* The plugin logs are also in `/var/log/calico/`.

* Bird has its own logging too, and logs are sent to `/var/log/bird`.
