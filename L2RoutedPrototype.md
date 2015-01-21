# L2 Routed Docker Prototype

This prototype demonstrates Calico running in a docker environment
with L2 routed compute hosts. It comprises steps for the following.

* Installing and configuring Calico and the required components.
* Creating and networking containers.
* Verifying connectivity between containers.

## How to install and run it.

You'll need the following.

* Two servers with IP addresses that you'll need to update in a number
  of places (listed in the bullet points below).  (You can add further
  servers, but it requires extra changes to the config files that is
  not documented in detail here.)
  
* The two servers need to be able to ping each other
    * If you're using VMs in VirtualBox, here's one way:
        * Configure 2 network interfaces
            * Attach the first interface to NAT
            * Attach the second interface to a host-only network with these settings:
                * 10.0.3.0/24, dchp server at 10.0.3.100, pool 10.0.3.101 -> 254
        * On the server: see if the new interface has an IP address.  If not, 
          run something like:
          
                  dhclient eth1 
                  
          on the server to bring it up.
  
* A working OS on the servers, with docker installed.  Any flavour of
  Linux is likely to work, subject to providing at least version 1.2
  of docker (and we recommend using at least version 1.3), but we have
  tested recently on CoreOS and Ubuntu Trusty (14.04).

  On Ubuntu Trusty, the following instructions got Docker 1.3
  installed:

        sudo apt-add-repository ppa:james-page/docker
        sudo apt-get update
        sudo apt-get install docker.io

* ipset and unzip installed, on each server.  For example, on Ubuntu:

        sudo apt-get install ipset unzip

_All commands from here on assume that you are running as root._

<a id="setup"></a>
#### Setup and installation

The instructions below take the form of a description of what the step does, followed by the commands required to perform that step.

1. Copy the whole of this git repository to both host servers as
`/opt/demo` (the location isn't important, except in so far as it is
used in the instructions). For example:

        wget https://github.com/Metaswitch/calico-docker-prototype/archive/master.zip
        unzip master.zip
        mv calico-docker-prototype-master /opt/demo    

2. Edit the IP addresses for the servers. These need to change in
various places.

    + `felix.txt` at the root of the repository, which must have both
    IP addresses and hostnames. The hostnames in the example are
    `instance-1` and `instance-2`; these must match the hostnames
    returned by `hostname` on your compute hosts.
    
    + The Dockerfiles under the directory `felix` needs to have the IP
    addresses changed.
    
    + The Dockerfile under the directory `bird` needs to have the IP
    addresses changed.

    If your code is in `/opt/demo`, and the two IP addresses in use
    are `1.2.3.4` and `2.3.4.5`, using hostname `host_1` and `host_2`,
    then the following commands will do it.
    
            IP1=1.2.3.4
            IP2=2.3.4.5
            HOST1=host_1
            HOST2=host_2
            for file in /opt/demo/felix.txt /opt/demo/felix/Dockerfile /opt/demo/bird/Dockerfile;
            do
              sed -i "s/IP1/$IP1/" $file
              sed -i "s/IP2/$IP2/" $file
              sed -i "s/HOST1/$HOST1/" $file
              sed -i "s/HOST2/$HOST2/" $file
            done

3. The BIRD configuration provided in the repo assumes that you are willing to assign
container addresses in the `192.168.0.0/16` range; if for some reason
you need to use another range, you'll need to edit `/opt/demo/bird/bird.conf` in the
(hopefully) obvious way.

4. Build the four docker images, by executing the commands below. The
fourth image is just a utility image that contains tools such as
`wget`, `telnet` and `traceroute` - making testing connectivity easier -
while the others contain real useful function.

        docker build -t "calico:bird" /opt/demo/bird 
        docker build -t "calico:plugin" /opt/demo/plugin
        docker build -t "calico:felix" /opt/demo/felix
        docker build -t "calico:util" /opt/demo/util

    <a id="restart"></a>

5. On each host, run the following commands (as root).

        modprobe ip6_tables
        modprobe xt_set
        mkdir /var/log/calico
        mkdir /var/run/netns
        mkdir -p /opt/plugin/data

6. Copy the base config file with information about Felix and the ACL
manager (recall that you edited this above). You only need to run this
command on the first host.

        cp /opt/demo/felix.txt /opt/plugin/data

#### Start the containers

1. On the first host, start BIRD and the plugins.  Two instances are
run, one for the network API and one for the Endpoint API.  If you
want more diagnostics, run them interactively from a bash container.
*The plugins must run on the first server only.*

        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird1.conf
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin1" --net=host --restart=always -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py network
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin2" --net=host --restart=always -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py ep

    The plugins would normally be the part of the orchestration that
    informs the Calico components about the current state of the
    system.  In this prototype the plugins are simple python script
    that load text config (which you will create shortly).  _Note that
    the plugins and Felix poll for configuration - this is just a
    limitation of the prototype code, and means that there may be a
    delay of some seconds before endpoints are fully networked._

2. On the first host, run the following as root (to start Felix and
the ACL Manager).

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="aclmgr" --net=host --restart=always -t calico:felix calico-acl-manager --config-file=/etc/calico/acl_manager.cfg

3. On the second (and any further) hosts, run the following to start
Felix and BIRD.  (ACL Manager need only run on the first host, so is
not started here.)

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird2.conf
  
#### Create some configuration for Felix

Next create some containers, and network them. The simplest way of
doing this is as follows.

+ Create another ssh session to the host you want the container on, and create 
the container with a command something like:

        docker run -i -t --net=none --name=192_168_1_1 calico:util

    The name here is deliberately intended to be the IP address;
    picking sensible names makes it far simpler to keep track. *This
    creates an interactive container - so you'll need to keep creating
    ssh sessions for each container you create.*

+ Now network the container. This would normally be done by the orchestration, 
but in this demo it is done by a shell script. Sample usage is as follows (as 
root).  Run this on the host hosting the container:

        bash /opt/demo/network_container.sh CID IP GROUP

    Here:
    
    * `CID` is the container ID as reported on the command line from
      `docker ps` (or from `docker run` or the command prompt of the 
      interactive session to that container).
      
    * `IP` is the IP address to assign.
    
    * `GROUP` is the name of the group. In this prototype, each
      endpoint is in a single group, and the other endpoints only have
      access to it if they are in the same group. Names are arbitrary.
      

+ If you networked a container on the first host, then you are done -
the script creates files in `/opt/plugin/data`, where the plugin reads
is. If you networked a container on the second host, then you need to
copy across the relevant container config file into `/opt/plugin/data`.
On the first host, this involves something like the following command.

        scp host2:/opt/plugin/data/192_168_1_1.txt /opt/plugin/data

+ The plugin checks for configuration dynamically, but it might take
quite some time (up to a minute or two) before it notices and passes
through changes to Calico.

+ Finally, you may want to delete one of the containers that you have
created. Just exiting from the shell will get rid of the container (and hence
the interface and routes); however, there will still be some resources created
by Felix (such as the `iptables` rules and `ipsets`) left around. To remove
these, remove the relevant text file from the first host. For example :

        rm /opt/plugin/data/192_168_1_1.txt

     If the container is on the second host, you should run the `rm` command in
     both places to avoid confusion (though the plugin only reads from the
     first host).

## Verifying that it works

Naturally, you'll want to check that it's doing what you expect. Good
things to look at include the following.

* `ip route` shows you the routes on the servers. There should be one
  for each virtual interface (on both servers).
  
* `iptables` shows a whole range of rules controlling traffic.

* Verify that you can ping and telnet between the containers that you
  created above, if and only if you specified the same group name for
  them.

## Troubleshooting

### Basic checks

If things do go wrong (and it can be a little fiddly setting it up),
then here are some good initial debug steps.

1. Are all of the containers running on the first host?

    * `plugin1`
    * `plugin2`
    * `felix`
    * `aclmgr`
    * `bird`

    All of these should restart on failure, so not running is probably a configuration error.

2. Are all of the containers running on the second host?

    * `felix`
    * `bird`

    Again, these should restart on failure.

3. If you have rebooted your hosts, then some configuration gets lost. Rerun the instructions from [here](#restart)
to make sure that they are all in a good state.

4. Did you do all of the IP addresses and hostnames correctly in the various files? It's worth rechecking all of the steps in [the whole setup section](#setup) again.

### Logging and diagnostics

* Logs from Felix and the ACL Manager are in `/var/log/calico/`.

* The plugin logs are also in `/var/log/calico/`.

* BIRD has its own logging too, and logs are sent to `/var/log/bird`.

If you are stuck, and you want to raise an issue to ask for support, collect diagnostics by running the script `diags.sh` from this repository (`bash diags.sh` as `root`). That generates a compressed tar file under `/tmp` (name reported by the tool) that contains enough information to allow analysis.
