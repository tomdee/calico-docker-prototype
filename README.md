# Calico docker prototype
This prototype demonstrates Calico running in a docker environment. If you do try using it, let me know how you get on by email (or just add a comment to the wiki).

*Note that there are some changes since an earlier version of this prototype; in particular, it uses Dockerfiles rather than images, automatically downloads a more recent version of the Felix code, and has been updated to allow for install under GCE.*

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

### Installing under GCE
Under GCE, certain of these instructions are changed - in particular, bird routing is not used, and container IPs are added to the GCE fabric as static routes. These differences are flagged where appropriate.

#### Prerequisites

1. You'll need at least one host, and ideally two (you can add more, but you'll need to make some further changes to the various configuration files). *On GCE only,* there are a couple of extra gotchas.

    * You must make sure that you have configured both these hosts with the "IP forwarding" flag set (under advanced options in the web developer console).
    * Certain kernel modules seem to be missing from the default CoreOS image (`coreos-stable-444-5-0-v20141016`), but these do seem to be included in `coreos-beta-494-1-0-v20141124` (at the time of writing).

2. Copy the whole of this git repository to both host servers as `/tmp/data` (the location isn't important, except in so far as it is used in the instructions).

3. Edit the IP addresses for the servers. These need to change in various places.
    + `felix.txt` at the root of the repository, which must have both IP addresses and hostnames (without qualification - up to the first dot) modified.
    + The Dockerfiles under the directories `felix` and `bird`. *There is no need to change the `bird` files under GCE.*
    + The bird configuration assumes that your container addresses are in the `192.168.0.0/16` range; if they aren't, you'll need to edit `bird.conf`.

4. Build the four docker images, by executing the commands below. The fourth image is just a utility image that contains tools such as `wget`, `telnet` and `traceroute` - making testing connectivity easier - while the others contain real useful function.

        sudo docker build -t "calico:bird" /tmp/data/bird 
        sudo docker build -t "calico:plugin" /tmp/data/plugin
        sudo docker build -t "calico:felix" /tmp/data/felix
        sudo docker build -t "calico:util" /tmp/data/util

5. On each host, run the following commands (as root).

        modprobe ip6_tables
        mkdir /var/log/calico
        mkdir /var/run/netns
        mkdir /opt/plugin
        mkdir /opt/plugin/data

6. Create a base config file with information about Felix and the ACL manager. You only need to run this command on the first host.

        cp /tmp/data/felix.txt /opt/plugin/data

#### Start the containers

1. On the first host, run the following as root (to start Felix, the ACL Manager, and bird respectively). *If using GCE, do not run bird.*

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="aclmgr" --net=host --restart=always -t calico:felix calico-acl-manager --config-file=/etc/calico/acl_manager.cfg
        docker run -d --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird1.conf

2. On the second host, run the following as root (to start Felix and bird respectively). Note that the ACL Manager need only run on the first host, so is not started here. *If using GCE, do not run bird.*

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird2.conf

3. On the first host (only) start the plugin running. The plugin would normally be the part of the orchestration that informs the Calico components about the current state of the system. In this prototype, the plugin is just a simple python script that loads text config. Two instances are run, one for the network API and one for the Endpoint API. If you want more diagnostics, run them interactively from a bash container. *The plugin must run on the first server only.*

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin1" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py network
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin2" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py ep

    The plugin would normally be the part of the orchestration that informs the Calico components about the current state of the system. In this prototype, the plugin is just a simple python script that loads text config (which you will create shortly).
    
#### Create some configuration for Felix

Next create some containers, and network them. The simplest way of doing this is as follows.

+ Create the container with a command something like

        docker run -i -t --net=none --name=192_168_1_1 calico:util

    The name here is deliberately intended to be the IP address; picking sensible names makes it far simpler to keep track.

+ Now network the container. This would normally be done by the orchestration, but in this demo it is done by a shell script. Sample usage is as follows.

        sh /tmp/data/network_container.sh CID IP GROUP

    Here
    * `CID` is the container ID as reported on the command line from `docker ps` (or from `docker run`).
    * `IP` is the IP address to assign.
    * `GROUP` is the name of the group. In this prototype, each endpoint is in a single group, and the other endpoints only have access to it if they are in the same group. Names are arbitrary.

+ If you networked a container on the first host, then you are done - the script creates files in `/opt/plugin/data`, then `cat`s everything in that directory to `/opt/plugin/data.txt` where the plugin reads is. If you networked a container on the second host, then you need to copy across the relevant container config file into `/opt/plugin/data` and manually recreate `/opt/plugin/data.txt`. On the first host, this involves something like the following commands.

        scp host1:/opt/plugin/data/192_168_21_1.txt /opt/plugin/data
        cat /opt/plugin/data/*.txt > /opt/plugin/data.txt

+ The plugin checks for configuration dynamically, but it might take quite some time (up to a minute or two) before it notices and passes through changes to Calico.

#### Extra configuration for GCE.
If you are not using GCE, `bird` ensures that the routes are shared between hosts. On GCE, this process should be done by the orchestration, and here is done by manually running the `gcloud` utility (a production instance would almost certainly use the RESTful API).

* Spin up a VM and install gcloud as here. [https://cloud.google.com/compute/docs/gcloud-compute/](https://cloud.google.com/compute/docs/gcloud-compute/).

    The full set of steps that I ran are as follows.

        curl https://sdk.cloud.google.com | bash
        gcloud auth login

    Now verify that you can view your instances and lists.
    
        gcloud compute instances list
        gcloud compute routes list


* Install each route in turn; you'll need to set the IPs of your endpoints correctly, and also to put in the right host name and zone for your hosts.

        gcloud compute routes create ip-192-168-1-1 --next-hop-instance host-1 --next-hop-instance-zone asia-east1-a --destination-range 192.168.1.1/32
        gcloud compute routes create ip-192-168-1-2 --next-hop-instance host-1 --next-hop-instance-zone asia-east1-a --destination-range 192.168.1.2/32
        gcloud compute routes create ip-192-168-1-3 --next-hop-instance host-2 --next-hop-instance-zone us-central1-a --destination-range 192.168.1.3/32

    Note that these commands are slow; my tests suggested that they could take up to around 25 seconds to complete, and even after completion it could take a few seconds before connectivity was established. It's perfectly possible to assign entire networks of addresses in this way to avoid having vast numbers of static routes, so that (for example) the `192.168.2.0/24` range is assigned to the first host.

* Your endpoints can now ping one another, but cannot do TCP or UDP because the GCE firewalls do not permit it. To enable this, since I used the `192.168.1.0/24` range, I just added a rule to the default network allowing incoming traffic from that IP range.

* The endpoints cannot access the internet - that is because the internal range I am using is not routable. Hence to get external connectivity, SNAT is called for using the following `iptables` rule (on both hosts).

        iptables -t nat -A POSTROUTING -s 192.168.1.0/24 ! -d 192.168.1.0/24 -j MASQUERADE


## Verifying that it works
Naturally, you'll want to check that it's doing what you expect. Good things to look at include the following.

* `ip route` shows you the routes on the servers. There should be one for each virtual interface (on both servers).

* `iptables` shows a whole range of rules controlling traffic.

* If the containers that you are installing are a little more sophisticated than the examples above, they will be able to open connections to each other (TCP / UDP / ICMP).

If things do go wrong (and it can be a little fiddly setting it up), then you can either just try restarting some or all the processes or take a look at the logs.

* Logs from Felix and the ACL Manager are in `/var/log/calico/`.

* The plugin reports to screen what it is doing, including reporting exchanges of messages with Felix and / or the ACL Manager. Note that the plugin runs until you interrupt it.

* Bird has its own logging too.

## Running bird under GCE
With the instructions and configuration as above, GCE’s underlying L3 fabric provides routing for the endpoint addresses between hosts without having to run a Calico driven BGP client such as bird. In such an environment, Calico's role is to manage ACLs (ensuring isolation of different groups of containers) and routing to each container within the host.

However, to demonstrate the full Calico solution using the bird BGP client, you can do the following.

* Unfortunately, `bird` refuses to accept routes where the default gateway is not in the same subnet as the local IP on the interface, and for GCE the local IP is always a /32. The way to resolve this is to add a route that convinces bird that the default gateway really is OK. Here's how to do that (where 10.240.40.50 is the IP of the server, and 10.240.0.1 is the gateway address; obviously change those for your deployment!). Note that you must do this on both hosts.

        ip addr add 10.240.40.50 peer 10.240.0.1 dev ens4v1

    There's more on this situation here, in case you need to debug bird [http://marc.info/?l=bird-users&m=139809577125938&w=2](http://marc.info/?l=bird-users&m=139809577125938&w=2)

* So that `bird` is not just adding routes that have no effect (since they match the default route), you'll want to ban all traffic to the network that your endpoints are on. This unreachable route will be overridden by `bird`, one endpoint at a time.

        ip route add unreachable 192.168.1.0/24

* Now run bird as usual above, and you'll see that only routes that are explicitly configured via Felix are routable.
