# Calico docker prototype
This prototype demonstrates Calico running in a docker environment. If you do try using it, let me know how you get on by email (or just add a comment to the wiki).

*Note that there are some changes since an earlier version of this prototype; in particular, it uses Dockerfiles rather than images, and automatically downloads a more recent version of the Felix code.*

Peter White (`peter.white@metaswitch.com`)


## What the prototype covers
The prototype is a demonstration / proof of concept of several things.

+ It shows that Felix and the ACL Manager can run in docker containers on the host.

+ It shows that bird (BGP) servers can be installed and run on a docker container on the host, and can configure routing between endpoints (containers in this case).

+ It shows that it is possible to write a plugin that interoperates successfully with Felix and the ACL Manager to report status and program endpoints.

It has some important restrictions.

+ Felix occasionally terminates with network errors, sometimes without restarting in a timely manner - if so, `pkill -9 felix` will make it restart (and you can tell by checking `/var/log/calico/felix`). If it repeatedly fails with cryptic errors about inserting rules, you are probably missing some kernel modules for `iptables`.

+ The plugin is just a simple script reading a text file, not a proper plugin that is associated with the orchestration. Although the Calico code supports an arbitrarily complex networking model with complex rules and groups, the plugin configures a single security group with hard-coded rules (that all endpoints can send traffic to one another and to external addresses, but no other traffic is permitted).

+ The "orchestration" in this prototype itself is just a script that configures the networking for a docker container and writes the content to file.

+ Last but not least, it isn't a fully fledged demo (let alone production quality), just a proof of concept. To run it on your own system you'll need to (for example) change the config manually to have the IP addresses of your own servers.


## How to install and run it.
The installation assumes two servers with IP addresses that you'll need to update these in a number of places (listed below). In the example config, these IP addresses are 10.240.254.171 and 10.240.58.221 for the first and second server respectively.

#### Prerequisites
You'll need at least one host, and ideally two (you can add more, but you'll need to make some further changes to the various configuration files).

1. Copy the whole of this git repository to both servers as `/tmp/data` (the location isn't important, except in so far as it is used in the instructions).

2. Edit the IP addresses for the servers. These need to change in various places.
    + `felix.txt` at the root of the repository, which must have both IP addresses and hostnames (without qualification - up to the first dot) modified.
    + The Dockerfiles under the directories `felix` and `bird`.

3. Build the three docker images, by executing the commands below.

        sudo docker build -t "felix:bird" /tmp/data/bird 
        sudo docker build -t "felix:plugin" /tmp/data/plugin
        sudo docker build -t "felix:felix" /tmp/data/felix

4. On each host, run the following commands (as root).

        modprobe ip6_tables
        mkdir /var/log/calico
        mkdir /opt/plugin
        mkdir /opt/plugin/data

5. Create a base config file with information about Felix and the ACL manager. You only need to run this command on the first host.

        cp /tmp/data/felix.txt /opt/plugin/data

#### Start the containers

1. On the first host, run the following as root (to start Felix, the ACL Manager, and bird respectively).

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t felix:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="aclmgr" --net=host --restart=always -t felix:felix calico-acl-manager --config-file=/etc/calico/acl_manager.cfg
        docker run -d --privileged=true --name="bird" --net=host --restart=always -t felix:bird /usr/bin/run_bird bird1.conf

2. On the second host, run the following as root (to start Felix and bird respectively). Note that the ACL Manager need only run on the first host.

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t felix:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d --privileged=true --name="bird" --net=host --restart=always -t felix:bird /usr/bin/run_bird bird2.conf


#### Create some configuration for Felix

+ Next create some containers with the script `create_container.sh`, which both creates a container and configures the networking. It doesn't do anything useful with the container at all; to test properly you'll want to tweak the script, but it does at least show you what commands need to be run and what the format of the config file is.

#### Trigger the plugin
The plugin would normally be the part of the orchestration that informs the Calico components about the current state of the system. In this prototype, the plugin is just a simple python script that loads text config. The easiest way to run the plugin is by creating two container with the right packages, and execute the plugin job from the command line. *The plugin must run on the first server only.*


    docker run -i -t --privileged=true --name="plugin1" --net=host -v /opt/plugin:/opt/plugin felix:plugin /bin/bash
    python /opt/scripts/plugin.py network

    docker run -i --privileged=true --name="plugin2" --net=host -v /opt/plugin:/opt/plugin -t felix:plugin /bin/bash
    python /opt/scripts/plugin.py ep

If you add more containers, you'll need to restart the plugin.

## Verifying that it works
Naturally, you'll want to check that it's doing what you expect. Good things to look at include the following.

* `ip route` shows you the routes on the servers. There should be one for each virtual interface (on both servers).

* `iptables` shows a whole range of rules controlling traffic.

* If the containers that you are installing are a little more sophisticated than the examples above, they will be able to open connections to each other (TCP / UDP / ICMP).

If things do go wrong (and it can be a little fiddly setting it up), then you can either just try restarting some or all the processes or take a look at the logs.

* Logs from Felix and the ACL Manager are in `/var/log/calico/`.

* The plugin reports to screen what it is doing, and if it hangs something is wrong. Note that the plugin runs until you interrupt it.

* Bird has its own logging too.

