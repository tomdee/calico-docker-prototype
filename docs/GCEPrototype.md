# GCE Calico docker prototype
This prototype demonstrates Calico running in a docker environment on the Google Compute Engine (GCE). The GCE fabric itself provides L3 routing for endpoint addresses between hosts and so does not require the Calico routing function in order to provide endpoint connectivity.  However, as this prototype shows, the full Calico routing and security model can be run on GCE, allowing GCE to be used as a valid test environment for Calico.

The following instructions show how to set up GCE for Calico, install and configure the various Calico components, configure GCE's networking and the BIRD BGP client.

## How to install and run it.
You'll need two GCE hosts running CoreOS, each with a valid IP address that you'll need to set in a number of places (listed in the bullet points below). (You can add further servers, but it requires extra changes to the config files that is not documented in detail here.) There are a couple of gotchas here.

* You must make sure that you have configured both these hosts with the "IP forwarding" flag set (under advanced options in the web developer console).
* Our testing showed that several required kernel modules were missing from the default CoreOS image (`coreos-stable-444-5-0-v20141016`); these were included in `coreos-beta-494-1-0-v20141124` (at the time of writing), so you should create your hosts using this image (or a later one).

* A working OS on the servers, with docker installed. We recommend CoreOS, though any other flavour of Linux is likely to work, subject to the requirement that you need at least version 1.2 of docker (and we recommend using at least version 1.3).

_All commands from here assume that you are running as root._


The installation assumes two GCE hosts, each with a valid IP address.  You'll need to use these IP addresses in a number of places as documented below. In the example config, these IP addresses are 10.240.254.171 and 10.240.58.221 for the first and second server respectively - you should replace references to these IP addresses with your own host addresses.

#### Prerequisites

1. Copy the whole of this git repository to both host servers as `/opt/demo` (the location isn't important, except in so far as it is used in the instructions).

2. Edit the IP addresses for the servers. These need to change in various places.
    + `felix.txt` at the root of the repository, which must have both IP addresses and hostnames. The hostnames in the example are `instance-1` and `instance-2`; these must match the hostnames returned by `hostname` on your compute hosts.
    + The Dockerfiles under the directory `felix` needs to have the IP addresses changed.
    + The Dockerfile under the directory  `bird` needs to have the IP addresses changed.

    If your code is in `/opt/demo`, and the two IP addresses in use are `1.2.3.4` and `2.3.4.5`, using hostname `host_1` and `host_2`, then the following commands will do it.
    
            IP1=1.2.3.4
            IP2=2.3.4.5
            HOST1=host_1
            HOST2=host_2
            for file in /opt/demo/felix.txt /opt/demo/felix/Dockerfile /opt/demo/bird/Dockerfile;
            do
              sed -i 's/IP1/$IP1/' $file
              sed -i 's/IP2/$IP2/' $file
              sed -i 's/HOST1/$HOST1/' $file
              sed -i 's/HOST2/$HOST2/' $file
            done

3. The BIRD configuration assumes that you are willing to assign container addresses in the `192.168.0.0/16` range; if for some reason you need to use another range, you'll need to edit `bird.conf` in the (hopefully) obvious way, but also modify the instructions later.

4. Build the four docker images, by executing the commands below. The fourth image is just a utility image that contains tools such as `wget`, `telnet` and `traceroute` - making testing connectivity easier - while the others contain real useful function.

        docker build -t "calico:bird" /opt/demo/bird 
        docker build -t "calico:plugin" /opt/demo/plugin
        docker build -t "calico:felix" /opt/demo/felix
        docker build -t "calico:util" /opt/demo/util

5. On each host, run the following commands (as root).

        modprobe ip6_tables
        modprobe xt_set
        mkdir -p /var/log/calico
        mkdir -p /var/run/netns
        mkdir -p /opt/plugin/data

6. Copy the base config file with information about Felix and the ACL manager (recall that you editted this above). You only need to run this command on the first host.

        cp /opt/demo/felix.txt /opt/plugin/data

### Configure the network

1. In order for routing to work correctly between hosts, you must notify GCE of the network address configuration you are using for your endpoints. For this demo we do this by manually running the `gcloud` utility; a production instance would almost certainly use the RESTful API. In these instructions, we'll assume that you plan on hosting addresses in the 192.168.1.0/24 range on host 1, and addresses in the 192.168.2.0/24 range on host 2. The instructions for doing this are as follows.

    * Spin up a GCE VM (you can use another OS if you prefer, but a GCE Ubuntu VM is quick and easy). Full documentation on how to install gcloud on that VM are given here : [https://cloud.google.com/compute/docs/gcloud-compute/](https://cloud.google.com/compute/docs/gcloud-compute/). For purposes of this demo, you should execute the following commands on the VM.

            curl https://sdk.cloud.google.com | bash
            gcloud auth login

        Now verify that you can view your instances and lists.
    
            gcloud compute instances list
            gcloud compute routes list

    * Install each route in turn.

            gcloud compute routes create ip-192-168-1-0 --next-hop-instance host-1 --next-hop-instance-zone asia-east1-a --destination-range 192.168.1.0/24
            gcloud compute routes create ip-192-168-2-0 --next-hop-instance host-2 --next-hop-instance-zone us-central1-a --destination-range 192.168.2.0/24

        Note that this assumes that your hosts are called `host-1` and `host-2` in zones `asia-east1-a` and `us-central1-a` respectively; change as appropriate for your configuration.

2. When you come to create endpoints (i.e. test containers) they will be able to ping one another but not do TCP or UDP because the GCE firewalls do not permit it. To enable this, since I used the `192.168.1.0/24` and `192.168.2.0/24` ranges, I just added a rule to the default network allowing incoming traffic from those ranges. This can be done as follows.

    * On the web Google Developers' Console, select Compute / Compute Engine / VM Instances.
    * Click on the network for your instances (typically `default` if you have not modified the networking).
    * Click `create new` next to `Firewall rules`.
    * Give your rule a name, set the source IP to `192.168.0.0/16`, and the protocols and ports field to `tcp:1-65535`.
    * Save the rule.

3. The test endpoints will be unable to access the internet - that is because the internal range we are using is not routable. Hence to get external connectivity, SNAT is called for using the following `iptables` rule (on both hosts).

        iptables -t nat -A POSTROUTING -s 192.168.0.0/16 ! -d 192.168.0.0/16 -j MASQUERADE

4. BIRD will not accept routes where the default gateway is not in the same subnet as the local IP on the interface, and for GCE the local IP is always a /32 (so no routes are in the same subnet). To resolve this, you must add a route that convinces BIRD that the default gateway really is valid by running a command such as that given below (where 10.240.40.50 is the IP of the server, and 10.240.0.1 is the gateway address; obviously change those for your deployment!). Note that you must do this on *both* hosts.

        ip addr add 10.240.40.50 peer 10.240.0.1 dev ens4v1

    There's more on this situation here, in case you want to understand this further [http://marc.info/?l=bird-users&m=139809577125938&w=2](http://marc.info/?l=bird-users&m=139809577125938&w=2)

5. So that BIRD is not just adding routes that have no effect (since they match the default route), we want to ban all traffic to the network that your endpoints are on. This unreachable route will be overridden when endpoints are created; on each host, the Calico Felix agent will add the route locally which will then be picked up and distributed by the BIRD clients.

        ip route add unreachable 192.168.0.0/16

#### Start the containers

1. On the first host, start BIRD and the plugins. The plugin would normally be the part of the orchestration that informs the Calico components about the current state of the system. In this prototype, the plugin is just a simple python script that loads text config. Two instances are run, one for the network API and one for the Endpoint API. If you want more diagnostics, run them interactively from a bash container. *The plugin must run on the first server only.*

        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird1.conf
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin_net" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py network
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin_ep" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py ep

    The plugin would normally be the part of the orchestration that informs the Calico components about the current state of the system. In this prototype, the plugin is just a simple python script that loads text config (which you will create shortly). _Note that the plugin and Felix poll for configuration - this is just a limitation of the prototype code, and means that there may be a delay of some seconds before endpoints are fully networked._

2. On the first host, run the following as root (to start Felix and the ACL Manager).

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="aclmgr" --net=host --restart=always -t calico:felix calico-acl-manager --config-file=/etc/calico/acl_manager.cfg

3. Finally, on the second (and any further) hosts, run the following to start Felix and BIRD. Note that the ACL Manager need only run on the first host, so is not started here.

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird2.conf
  
#### Create some container endpoints

Next create some test containers, and network them. You'll want to create containers on both hosts, remembering that we have assigned the address range `192.168.1.0/24` to `host-1` and `192.168.2.0/24` to `host-2`. This can be done as follows.

+ Create the container with a command something like

        docker run -i -t --net=none --name=192_168_1_1 calico:util

    The name here is deliberately intended to be the IP address; picking sensible names makes it far simpler to keep track. *This creates an interactive container - so you'll need to keep creating ssh sessions for each container you create.* It is strongly recommended that you enter a command like `PS1='1_1:\w>'` in the container so that the command prompt reminds you which test container you are in!

+ Now network the container. This would be done by the orchestration in a production deployment, but in this demo it is done by a shell script. Sample usage is as follows.

        bash /opt/demo/network_container.sh CID IP GROUP

    Here
    
    * `CID` is the container ID as reported on the command line from `docker ps` (or from `docker run`).
    * `IP` is the IP address to assign.
    * `GROUP` is the name of the security group. In this prototype, each endpoint is in a single security group, and the other endpoints only have access to it if they are in the same security group. Names are arbitrary.

    The function performed by this script is as follows.

    * Create a new network namespace for the test container.
    * Create a `veth` interface pair, moving one end into the container as `eth0`.
    * Add an IP address to the `veth` interface.
    * Write a file in `/opt/plugin/data` which contains information about the endpoint (to be picked up by the dummy plugin).

+ If you networked a container on the first host, then you are done - the script creates files in `/opt/plugin/data` where the Calico plugin reads it. If instead you networked a container on the second host, then you need to copy across the relevant container config file into `/opt/plugin/data`. This involves running the following commands on the first host (change the hostname and the name of the file being copied appropriately).

        scp host2:/opt/plugin/data/192_168_2_1.txt /opt/plugin/data

+ The Calico plugin checks for configuration dynamically, but it might take quite some time (up to a minute or two) before it notices and passes through changes to the other Calico components.

## Verifying that it works
Naturally, you'll want to check that it's doing what you expect. Good things to look at include the following.

* `ip route` shows you the routes on the servers. There should be one for each virtual interface (on both servers).

* `iptables` shows a whole range of rules controlling traffic.

* Verify that you can ping and telnet between the containers that you created above, if and only if you specified the same security group name for them.

If things do go wrong (and it can be a little fiddly setting it up), then you can either just try restarting some or all the processes or take a look at the logs.

* Logs from Felix and the ACL Manager are in `/var/log/calico/`.

* The plugin logs are also in `/var/log/calico/`.

* BIRD has its own logging too, and logs are sent to `/var/log/bird`.

