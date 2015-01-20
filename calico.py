#!venv/bin/python
"""Calico..

Usage:
  calico launch [--master] --ip=<IP> [--peer=<IP>...]
  calico run <IP> --host=<IP> [--group=<GROUP>] [--] <docker-options> ...
  calico status [--master]
  calico ps
  calico start
  calico stop
  calico attach
  calico detach
  calico expose
  calico hide
  calico reset [--delete-images]
  calico version

Options:
 --master     This is the master node, which runs ACL manager.
 --ip=<IP>    Our IP
 --peer=<IP>  TODO

"""
# Some pretty important things that the current docker demo can't do:
#   Demonstrate container mobility
#   Expose services externally
#   Stop a service and clean everything up...

#TODO - Implement all these commands
#TODO - Bash completion
#TODO - Logging
#TODO -  Files should be written to a more reliable location, either relative to the binary or in a fixed location.
# TODO - Currently assumes a single peer. It shouldbe easy to work with zero or more.

#Useful docker aliases
# alias docker_kill_all='sudo docker kill $(docker ps -q)'
# alias docker_rm_all='sudo docker rm -v `docker ps -a -q -f status=exited`'

from docopt import docopt
from subprocess import call, check_output, check_call, CalledProcessError

def validate_arguments(arguments):
    # print(arguments)
    return True

def configure_bird(ip, peers):
    # This shouldn't live here. Bird config should live with bird and another process in the bird container should process felix.txt.
    base_config = """router id %s;
#log "/var/log/bird/bird.log" all;

# Configure synchronization between routing tables and kernel.
protocol kernel {
  learn;          # Learn all alien routes from the kernel
  persist;        # Don't remove routes on bird shutdown
  scan time 2;    # Scan kernel routing table every 2 seconds
  import all;
  device routes;
  export all;     # Default is export none
}

# Watch interface up/down events.
protocol device {
  scan time 2;    # Scan interfaces every 2 seconds
}

protocol direct {
   debug all;
   interface "eth*", "em*", "ens*";
}

# Peer with all neighbours
protocol bgp bgppeer {
  debug all;
  description "Connection to BGP peer";
  local as 64511;
  neighbor %s as 64511;
  multihop;
  gateway recursive; # This should be the default, but just in case.
  import where net ~ 192.168.0.0/16;
  export where net ~ 192.168.0.0/16;
  next hop self;    # Disable next hop processing and always advertise our
                    # local address as nexthop
  source address %s;  # The local address we use for the TCP connection
}
""" % (ip, peers[0], ip)
    with open('config/bird.conf', 'w') as f:
        f.write(base_config)


def refresh_plugin_data():
    check_call("cat config/data/* >config/data.txt", shell=True)


def configure_felix(ip, peers):
    # TODO - DO we really need hostnames? Find out why.
    our_name = ip.replace('.', '_')
    peer_name = peers[0].replace('.', '_')
    base_config = """[felix %s]
ip=%s
host=%s

[felix %s]
ip=%s
host=%s
""" % (our_name, ip, our_name, peer_name, peers[0], peer_name)
    with open('config/data/felix.txt', 'w') as f:
        f.write(base_config)
    refresh_plugin_data()

    base_config = """
[global]
# Time between retries for failed endpoint operations
#EndpointRetryTimeMillis = 500
# Time between complete resyncs
ResyncIntervalSecs = 5
# Hostname to use in messages - defaults to server hostname
#FelixHostname = hostname
# Plugin and ACL manager addresses
PluginAddress = %s
ACLAddress    = %s
# Metadata IP (or host) and port. If no metadata configuration, set to None
MetadataAddr  = None
#MetadataPort  = 9697
# Address to bind to - either "*" or an IPv4 address (or hostname)
#LocalAddress = *

[log]
# Log file path. If LogFilePath is not set, felix will not log to file.
#LogFilePath = /var/log/calico/felix.log

# Log severities for the Felix log and for syslog.
#   Valid levels: NONE (no logging), DEBUG, INFO, WARNING, ERROR, CRITICAL
#LogSeverityFile   = INFO
#LogSeveritySys    = ERROR
LogSeverityScreen = DEBUG

[connection]
# Time with no data on a connection after which we give up on the
# remote entity
#ConnectionTimeoutMillis = 40000
# Time between sending of keepalives
#ConnectionKeepaliveIntervalMillis = 5000
""" % (ip, ip)

    with open('config/felix.cfg', 'w') as f:
        f.write(base_config)

    base_config = """
[global]
# Plugin address
PluginAddress = %s
# Address to bind to - either "*" or an IPv4 address (or hostname)
#LocalAddress = *

[log]
# Log file path.
# Log file path. If LogFilePath is not set, acl_manager will not log to file.
#LogFilePath = /var/log/calico/acl_manager.log

# Log severities for the Felix log and for syslog.
#   Valid levels: NONE (no logging), DEBUG, INFO, WARNING, ERROR, CRITICAL
#LogSeverityFile   = INFO
#LogSeveritySys    = ERROR
LogSeverityScreen = DEBUG
""" % ip

    with open('config/acl_manager.cfg', 'w') as f:
        f.write(base_config)


def launch(master, ip, peers):
    call("mkdir -p config/data", shell=True)
    call("modprobe ip6_tables", shell=True)
    call("modprobe xt_set", shell=True)
    # ipset install is required for ubuntu only. Could at least check it's available.

    configure_bird(ip, peers)
    configure_felix(ip, peers)

    if master:
        call("./fig -f master.yml up -d", shell=True)
    else:
        call("./fig -f node.yml up -d", shell=True)


def status(master):
    if master:
        call("./fig -f master.yml ps", shell=True)
    else:
        call("./fig -f node.yml ps", shell=True)
    #And maybe tail the "calico" log(s)


def run(ip, host, group, docker_options):
    # TODO need to tidy up after all this messy networking...
    name = ip.replace('.', '_')
    docker_command = 'docker run -d --net=none %s' % docker_options
    cid = check_output(docker_command, shell=True).strip()
    cpid = check_output("docker inspect -f '{{.State.Pid}}' %s" % cid, shell=True).strip()
    # TODO - need to handle containers exiting straight away...
    iface = "tap" + cpid[:11]
    iface_tmp = "%s-tmp" % iface
    # Provision the networking
    call("mkdir -p /var/run/netns", shell=True)
    check_call("ln -s /proc/%s/ns/net /var/run/netns/%s" % (cpid, cpid), shell=True)

    # Create the veth pair and move one end into container as eth0 :
    check_call("ip link add %s type veth peer name %s" % (iface, iface_tmp), shell=True)
    check_call("ip link set %s up" % iface, shell=True)
    check_call("ip link set %s netns %s" % (iface_tmp, cpid), shell=True)
    check_call("ip netns exec %s ip link set dev %s name eth0" % (cpid, iface_tmp), shell=True)
    check_call("ip netns exec %s ip link set eth0 up" % cpid, shell=True)

    # Add an IP address to that thing :
    check_call("ip netns exec %s ip addr add %s/32 dev eth0" % (cpid, ip), shell=True)
    check_call("ip netns exec %s ip route add default dev eth0" % cpid, shell=True)

    print cid

    # Get the MAC address.
    mac = check_output("ip netns exec %s ip link show eth0 | grep ether | awk '{print $2}'" % cpid, shell=True).strip()

    base_config = """
[endpoint $NAME]
id=%s
ip=%s
mac=%s
host=%s
group=%s

""" % (cid, ip, mac, host, group)

    with open('config/data/%s.txt' % name, 'w') as f:
        f.write(base_config)
    refresh_plugin_data()


def reset(delete_images):
    call("./fig -f master.yml stop", shell=True)
    call("./fig -f node.yml stop", shell=True)

    call("./fig -f master.yml kill", shell=True)
    call("./fig -f node.yml kill", shell=True)

    call("./fig -f master.yml rm", shell=True)
    call("./fig -f node.yml rm", shell=True)

    if (delete_images):
        call("docker rmi calicodockerprototype_pluginep", shell=True)
        call("docker rmi calicodockerprototype_pluginnetwork", shell=True)
        call("docker rmi calicodockerprototype_bird", shell=True)
        call("docker rmi calicodockerprototype_felix", shell=True)
        call("docker rmi calicodockerprototype_aclmanager", shell=True)


    try:
        interfaces_raw = check_output("ip link show | grep -Po ' (tap(.*?)):' |grep -Po '[^ :]+'", shell=True)
        print "Removing interfaces:\n%s" % interfaces_raw
        interfaces = interfaces_raw.splitlines()
        for interface in interfaces:
            call("ip link delete %s" % interface, shell=True)
    except CalledProcessError:
        print "No interfaces to clean up"


if __name__ == '__main__':
    import os
    if os.geteuid() != 0:
        print "Calico must be run as root"
    else:
        arguments = docopt(__doc__)
        if validate_arguments(arguments):
            if arguments["launch"]:
                launch(arguments["--master"], arguments["--ip"], arguments["--peer"])
            if arguments["run"]:
                run(arguments['<IP>'], arguments['--host'], arguments['--group'], ' '.join(arguments[
                    '<docker-options>']))
            if arguments["status"]:
                status(arguments["--master"])
            if arguments["reset"]:
                reset(arguments["--delete-images"])
        else:
            print "Not yet"





