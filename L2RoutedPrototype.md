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

* A working OS on the servers, with docker installed.  We recommend
  CoreOS, though any other flavour of Linux is likely to work, subject
  to the requirement that you need at least version 1.2 of docker (and
  we recommend using at least version 1.3).

  On Ubuntu Trusty, the following instructions got Docker 1.3
  installed:

        sudo apt-add-repository ppa:james-page/docker
        sudo apt-get update
        sudo apt-get install docker.io

_All commands from here on assume that you are running as root._

#### Setup and installation

1. Copy the whole of this git repository to both host servers as
`/opt/demo` (the location isn't important, except in so far as it is
used in the instructions).

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
              sed -i 's/IP1/$IP1/' $file
              sed -i 's/IP2/$IP2/' $file
              sed -i 's/HOST1/$HOST1/' $file
              sed -i 's/HOST2/$HOST2/' $file
            done

3. The BIRD configuration assumes that you are willing to assign
container addresses in the `192.168.0.0/16` range; if for some reason
you need to use another range, you'll need to edit `bird.conf` in the
(hopefully) obvious way.

4. Build the four docker images, by executing the commands below. The
fourth image is just a utility image that contains tools such as
`wget`, `telnet` and `traceroute` - making testing connectivity easier -
while the others contain real useful function.

        docker build -t "calico:bird" /opt/demo/bird 
        docker build -t "calico:plugin" /opt/demo/plugin
        docker build -t "calico:felix" /opt/demo/felix
        docker build -t "calico:util" /opt/demo/util

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
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin1" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py network
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin2" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py ep

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

+ Create the container with a command something like

        docker run -i -t --net=none --name=192_168_1_1 calico:util

    The name here is deliberately intended to be the IP address;
    picking sensible names makes it far simpler to keep track. *This
    creates an interactive container - so you'll need to keep creating
    ssh sessions for each container you create.*

+ Now network the container. This would normally be done by the
orchestration, but in this demo it is done by a shell script. Sample
usage is as follows.

        bash /opt/demo/network_container.sh CID IP GROUP

    Here:
    
    * `CID` is the container ID as reported on the command line from
      `docker ps` (or from `docker run`).
      
    * `IP` is the IP address to assign.
    
    * `GROUP` is the name of the group. In this prototype, each
      endpoint is in a single group, and the other endpoints only have
      access to it if they are in the same group. Names are arbitrary.
      

+ If you networked a container on the first host, then you are done -
the script creates files in `/opt/plugin/data`, then `cat`s everything
in that directory to `/opt/plugin/data.txt` where the plugin reads
is. If you networked a container on the second host, then you need to
copy across the relevant container config file into `/opt/plugin/data`
and manually recreate `/opt/plugin/data.txt`. On the first host, this
involves something like the following commands.

        scp host2:/opt/plugin/data/192_168_1_1.txt /opt/plugin/data
        cat /opt/plugin/data/*.txt > /opt/plugin/data.txt

+ The plugin checks for configuration dynamically, but it might take
quite some time (up to a minute or two) before it notices and passes
through changes to Calico.

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

### Logging and diagnostics

If things do go wrong (and it can be a little fiddly setting it up),
then you can either just try restarting some or all the processes or
take a look at the logs.

* Logs from Felix and the ACL Manager are in `/var/log/calico/`.

* The plugin logs are also in `/var/log/calico/`.

* BIRD has its own logging too, and logs are sent to `/var/log/bird`.

### Known issues

*__There is a known issue where the plugin and ACL Manager can lose
 connectivity; if you restart the plugins, or you find that ACLs are
 not being populated (typically in that endpoints cannot ping one
 another, but routes exist), then restart the ACL manager.__*

A set of commands that will do this is as follows.

        docker rm -f aclmgr
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="aclmgr" --net=host --restart=always -t calico:felix calico-acl-manager --config-file=/etc/calico/acl_manager.cfg

