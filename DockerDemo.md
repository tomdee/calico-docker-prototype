# Calico docker demonstration
This is the script for the demo of docker running in a Calico environmet.

## Pre-requisite setup
*This covers what you need to do in advance of the demo - getting machines ready etc.*

1. You'll need at least one host, and ideally two. The rest of the documentation assumes two.

2. On each host, run the following commands (as root).

        modprobe ip6_tables
        mkdir -p /var/log/calico
        mkdir -p /var/run/netns
        mkdir -p /opt/plugin
        mkdir -p /opt/plugin/data
        mkdir -p /opt/demo
        chmod 777 /var/log/calico /opt/plugin /opt/plugin/data /opt/demo

3. Copy the whole of this git repository to both host servers as `/opt/demo` (the location isn't important, except in so far as it is used in the instructions).

4. Edit the IP addresses for the servers. These need to change in various places.
    + `felix.txt` at the root of the repository, which must have both IP addresses and hostnames (without qualification - up to the first dot) modified.
    + The Dockerfiles under the directories `felix` and `bird`. *There is no need to change the `bird` files under GCE.*
    + The bird configuration assumes that your container addresses are in the `192.168.0.0/16` range; if they aren't, you'll need to edit `bird.conf`.

5. Build the four docker images, by executing the commands below. The fourth image is just a utility image that contains tools such as `wget`, `telnet` and `traceroute` - making testing connectivity easier - while the others contain real useful function.

        sudo docker build -t "calico:bird" /opt/demo/bird 
        sudo docker build -t "calico:plugin" /opt/demo/plugin
        sudo docker build -t "calico:felix" /opt/demo/felix
        sudo docker build -t "calico:util" /opt/demo/util

## Pre-test cleanup
*This covers adding the few bits and pieces required to get the demo into place - so that you have the right windows open, and so on.*

1. Ideally, reboot the hosts to clean out any old iptables rules.

2. Verify that the directories are still there, and that `ip6_tables` is still loaded (as above).

3. Make sure that you have no unexpected containers running on the hosts - for example, having an old Felix around from the last run can be confusing. Running `docker ps -a` and removing manually what you don't want is fine, or you can nuke all containers with the following.

        docker ps -a | awk '{print $1}' | grep -v CONTAINER | xargs -n 1 docker rm -f

4. Check that the directory /opt/plugin/data contains no unexpected files. The cleanest thing to do is to wipe it, then copy in the global config.

        rm /opt/plugin/data/*
        cp /opt/demo/felix.txt /opt/plugin/data
        cat /opt/plugin/data/* /opt/plugin/data.txt

5. On the first host, run the following as root (to start Felix, BIRD, ACL Manager and plugin containers).

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="aclmgr" --net=host --restart=always -t calico:felix calico-acl-manager --config-file=/etc/calico/acl_manager.cfg
        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird1.conf
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin1" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py network
        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="plugin2" --net=host -v /opt/plugin:/opt/plugin calico:plugin python /opt/scripts/plugin.py ep

5. On the second host, run the following as root (to start Felix and BIRD respectively).

        docker run -d -v /var/log/calico:/var/log/calico --privileged=true --name="felix" --net=host --restart=always -t calico:felix calico-felix --config-file=/etc/calico/felix.cfg
        docker run -d -v /var/log/bird:/var/log/bird --privileged=true --name="bird" --net=host --restart=always -t calico:bird /usr/bin/run_bird bird2.conf

7. Create two endpoints on the first host. Note that these will take over your terminal - you'll need to create a terminal for each command.

    * Create the containers themselves
    
            docker run -i -t --net=none --name=192_168_1_1 calico:util
            docker run -i -t --net=none --name=192_168_1_2 calico:util

    * It's not obligatory, but unless you want to go mad, it's a good idea to immediately set up the prompt in those new terminals that are running endpoints as follows. For example.

            PS1='1_1:\w>'

    * Network the containers. This adds container 1 to group1 and container 2 to group 2. The format here is `sh /opt/demo/network_container.sh CID PID GROUP`, but this saves you dull stuff with `docker ps`.
    
            sh /opt/demo/network_container.sh `docker ps | grep 192_168_1_1 | awk '{print $1}'` 192.168.1.1 group1
            sh /opt/demo/network_container.sh `docker ps | grep 192_168_1_2 | awk '{print $1}'` 192.168.1.2 group2

6. Create a single container on the second host. We'll want to start with a couple of containers already running (these 

    * Create the container itself (this uses up your prompt on that server).
    
            docker run -i -t --net=none --name=192_168_1_4 calico:util

    * Set the prompt in the container.
    
            PS1='1_4:\w>'

    * Network the container.

            sh /opt/demo/network_container.sh `docker ps | grep 192_168_1_4 | awk '{print $1}'` 192.168.1.4 group1

    * Copy the file `/opt/plugin/data/192_168_1_4.txt` from the second host to the same location on the first.

At this point, before you start, you now have three endpoints created. 1 and 2 are on host 1; 4 is on host 2. Since 1 and 4 are in the same group, they can ping one another. It's absolutely necessary to check that they can all ping each other as expected, and that connectivity is present.

## The demo itself
Note that this talks about demonstrating connectivity etc. from container 3, the newly created one. If for some reason something goes wrong, you can show off the working containers instead.

1. Create a new endpoint, endpoint 3, on host 1.

    * Create the container itself.
    
            docker run -i -t --net=none --name=192_168_1_3 calico:util

    * Set the prompt in the container.
    
            PS1='1_3:\w>'

    * Network the container. Container 3 is in group1.
        
            sh /opt/demo/network_container.sh `docker ps | grep 192_168_1_3 | awk '{print $1}'` 192.168.1.3 group1

2. Wait for Felix to notice - this can take up to a minute or so (though if you delete the Felix, ACL Manager and plugin containers on the two hosts then recreate them, it will happen right away; easier to wait). Best way to check is just to run `ip route` on both hosts, and soon a route will appear on host 1 then host 2.

3. Once networking is present, check that it works. That means :

    * Container 3 can ping container 1 and 4 - both of which can ping back.

    * Container 3 cannot ping container 2, because they are in different groups (we've arbitrarily chosen to set up the ACLs that way to demonstrate the point).

4. Optionally, show some of the behind the scenes magic.

    * `iptables` rules / chains and `ipset` entries related to the endpoint exist. Worth just running the commands below and saying "not going to talk you through this, but you can see the chains and tables labelled with `felix`".

            iptables -L
            ipset list
        
    * Routes. Just run `ip route`, and you'll see routes to the tap interface (really a badly named veth interface) for local endpoints, and routes via BGP through the switch for the remote endpoints.
    

## Diagnostics
If things do go wrong (and it can be a little fiddly setting it up), then you can either just try restarting some or all the processes or take a look at the logs.

* Logs from Felix, the ACL Manager, and the dummy plugin are in `/var/log/calico/`. Check that they are all running (and logging profusely).

* Logs from BIRD are in `/var/log/bird/`. But BIRD is pretty reliable if the config is right.

