#!venv/bin/python
"""Calico..

Usage:
  calico launch [--master] --ip=<IP> --peer=<IP>...
  calico run <IP> [--group=<GROUP>] [--] <docker-options> ...
  calico status
  calico ps
  calico start
  calico stop
  calico attach
  calico detach
  calico expose
  calico hide
  calico reset [--master]
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

#Useful docker aliases
# alias docker_kill_all='sudo docker kill $(sudo docker ps -q)'
# alias docker_rm_all='sudo docker rm -v `sudo docker ps -a -q -f status=exited`'

from docopt import docopt
from subprocess import call, check_output, check_call, CalledProcessError

def validate_arguments(arguments):
    print(arguments)
    return True

def configure_bird(ip, peers):
    # This shouldn't live here. Bird config should live with bird and another process in the bird container should process felix.txt.
    base_config = """router id %s;
log "/var/log/bird/bird.log" all;

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
    base_config = """[felix HOST1]
ip=%s
host=HOST1

[felix HOST2]
ip=%s
host=HOST2
""" % (ip, peers[0])
    with open('config/data/felix.txt', 'w') as f:
        f.write(base_config)
    refresh_plugin_data()

def launch(master, ip, peers):
    call("mkdir -p config/data", shell=True)
    configure_bird(ip, peers)
    configure_felix(ip, peers)

    # if master:
    #     call("sudo ./fig -f master.yml up", shell=True)
    # else:
    #     call("sudo ./fig -f node.yml up", shell=True)


def status(master):
    if master:
        call("sudo ./fig -f master.yml ps", shell=True)
    else:
        call("sudo ./fig -f node.yml ps", shell=True)
    #And maybe tail the "calico" log(s)


def run(ip, docker_options):
    # TODO need to tidy up after all this messy networking...
    name = ip.replace('.', '_')
    docker_command = 'docker run -d --net=none %s' % docker_options
    cid = check_output(docker_command, shell=True).strip()
    print cid
    cpid = check_output("docker inspect -f '{{.State.Pid}}' %s" % cid, shell=True).strip()
    # TODO - need to handle containers exiting straight away...
    print cpid
    iface = "tap" + cpid[:11]
    iface_tmp = "%s-tmp" % iface
    print iface
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

    # Get the MAC address.
    mac = check_output("ip netns exec %s ip link show eth0 | grep ether | awk '{print $2}'" % cpid, shell=True).strip()
    print mac

    base_config = """
[endpoint $NAME]
id=%s
ip=%s
mac=%s
host=$HOSTNAME
group=TEST

""" % (cid, ip, mac)

    with open('config/data/%s.txt' % name, 'w') as f:
        f.write(base_config)
    refresh_plugin_data()


def reset(master):
    try:
        interfaces_raw = check_output("ip link show | grep -Po ' (tap(.*?)):' |grep -Po '[^ :]+'", shell=True)
        print "Removing interfaces:\n%s" % interfaces_raw
        interfaces = interfaces_raw.splitlines()
        for interface in interfaces:
            call("ip link delete %s" % interface, shell=True)
    except CalledProcessError:
        print "No interfaces to clean up"

    if master:
        call("sudo ./fig -f master.yml stop", shell=True)
    else:
        call("sudo ./fig -f node.yml stop", shell=True)

if __name__ == '__main__':
    arguments = docopt(__doc__)
    if validate_arguments(arguments):
        if arguments["launch"]:
            launch(arguments["--master"], arguments["--ip"], arguments["--peer"])
        if arguments["run"]:
            run(arguments['<IP>'], ' '.join(arguments['<docker-options>']))
        if arguments["status"]:
            status(arguments["--master"])
        if arguments["reset"]:
            reset(arguments["--master"])
    else:
        print "Not yet"





