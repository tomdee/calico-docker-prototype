#!venv/bin/python
"""Calico..

Usage:
  calico launch --host=<IP> [--master_ip=<IP>] [--peer=<IP>...]
  calico run <IP> --host=<IP> [--master_ip=<IP>] --group=<GROUP> [--] <docker-options> ...
  calico status [--master]
  calico reset [--delete-images]
  calico version


Options:
 --host=<IP>  Set to the IP of the current running machine.
 --master     Set this flag when running on the master node.
 --peer=<IP>  The IP of other compute node. Can be specified multiple times.
 --group=<GROUP>  The group to place the container in. Communication is only possible
                  with containers in the same group.
  --master_ip=<IP>  The IP address of the master node.
 <IP>         The IP to assign to the container.

"""
#   calico ps
#   calico start
#   calico stop
#   calico attach
#   calico detach
#   calico expose
#   calico hide
#   calico version
# Some pretty important things that the current docker demo can't do:
#   Demonstrate container mobility
#   Expose services externally
#   Stop a service and clean everything up...

# TODO - Implement all these commands
# TODO - Bash completion
# TODO - Logging
# TODO -  Files should be written to a more reliable location, either relative to the binary or
# in a fixed location.

#Useful docker aliases
# alias docker_kill_all='sudo docker kill $(docker ps -q)'
# alias docker_rm_all='sudo docker rm -v `docker ps -a -q -f status=exited`'

from docopt import docopt
from subprocess import call, check_output, check_call, CalledProcessError
from string import Template
BIRD_TEMPLATE = Template("""router id $ip;
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
$neighbours
  multihop;
  gateway recursive; # This should be the default, but just in case.
  import where net ~ 192.168.0.0/16;
  export where net ~ 192.168.0.0/16;
  next hop self;    # Disable next hop processing and always advertise our
                    # local address as nexthop
  source address $ip;  # The local address we use for the TCP connection
}
""")

PLUGIN_TEMPLATE = Template("""[felix $name]
ip=$ip
host=$name

$peers
""")

FELIX_TEMPLATE = Template("""
[global]
# Time between retries for failed endpoint operations
#EndpointRetryTimeMillis = 500
# Time between complete resyncs
ResyncIntervalSecs = 5
# Hostname to use in messages - defaults to server hostname
FelixHostname = $hostname
# Plugin and ACL manager addresses
PluginAddress = $ip
ACLAddress    = $ip
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
""")

ACL_TEMPLATE = Template("""
[global]
# Plugin address
PluginAddress = $ip
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
""")

def validate_arguments(arguments):
    # print(arguments)
    return True

def configure_bird(ip, peers):
    # Config shouldn't live here. Bird config should live with bird and another process in the
    # bird container (which should process felix.txt)
    neighbours = ""
    for peer in peers:
        neighbours += "  neighbor %s as 64511;\n" % peer

    bird_config = BIRD_TEMPLATE.substitute(ip=ip, neighbours=neighbours)
    with open('config/bird.conf', 'w') as f:
        f.write(bird_config)

def configure_felix(ip, master_ip, peers):
    our_name = ip.replace('.', '_')

    peer_config = ""

    for peer in peers:
        peer_name = peer.replace('.', '_')
        peer_config += "[felix {host}]\nip={ip}\nhost={host}\n\n".format(host=peer_name, ip=peer)

    plugin_config = PLUGIN_TEMPLATE.substitute(ip=ip, name=our_name, peers=peer_config)
    with open('config/data/felix.txt', 'w') as f:
        f.write(plugin_config)

    felix_config = FELIX_TEMPLATE.substitute(ip=master_ip, hostname=our_name)
    with open('config/felix.cfg', 'w') as f:
        f.write(felix_config)

    aclmanager_config = ACL_TEMPLATE.substitute(ip=ip)
    with open('config/acl_manager.cfg', 'w') as f:
        f.write(aclmanager_config)


def launch(ip, master_ip, peers):
    call("mkdir -p config/data", shell=True)
    call("modprobe ip6_tables", shell=True)
    call("modprobe xt_set", shell=True)

    plugin_ip = master_ip
    if not plugin_ip:
        plugin_ip = ip

    configure_bird(ip, peers)
    configure_felix(ip, plugin_ip, peers)

    if master_ip:
        call("./fig -f node.yml up -d", shell=True)
    else:
        call("./fig -f master.yml up -d", shell=True)


def status(master):
    if master:
        call("./fig -f master.yml ps", shell=True)
    else:
        call("./fig -f node.yml ps", shell=True)
    #And maybe tail the "calico" log(s)


def run(ip, host, group, master_ip, docker_options):
    # TODO need to tidy up after all this messy networking...
    name = ip.replace('.', '_')
    host = host.replace('.', '_')
    docker_command = 'docker run -d --net=none %s' % docker_options
    cid = check_output(docker_command, shell=True).strip()
    #Important to print this, since that's what docker run does when running a detached container.
    print cid
    cpid = check_output("docker inspect -f '{{.State.Pid}}' %s" % cid, shell=True).strip()
    # TODO - need to handle containers exiting straight away...
    iface = "tap" + cid[:11]
    iface_tmp = "tap" + "%s-" % cid[:10]
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

    base_config = """
[endpoint %s]
id=%s
ip=%s
mac=%s
host=%s
group=%s
    """ % (name, cid, ip, mac, host, group)

    if master_ip:
        #copy the file to master ip
        command = "echo '{config}' | ssh -o 'StrictHostKeyChecking no' {host} 'cat " \
                  ">/home/core/calico-docker-prototype/config/data/{" \
        "filename}.txt'".format(config=base_config, host=master_ip, filename=name)
        check_call(command, shell=True)

    else:
        with open('config/data/%s.txt' % name, 'w') as f:
            f.write(base_config)


def reset(delete_images):
    call("./fig -f master.yml stop", shell=True)
    call("./fig -f node.yml stop", shell=True)

    call("./fig -f master.yml kill", shell=True)
    call("./fig -f node.yml kill", shell=True)

    call("./fig -f master.yml rm", shell=True)
    call("./fig -f node.yml rm", shell=True)

    call("rm -rf config", shell=True)

    if (delete_images):
        call("docker rmi calicodockerprototype_pluginep", shell=True)
        call("docker rmi calicodockerprototype_pluginnetwork", shell=True)
        call("docker rmi calicodockerprototype_bird", shell=True)
        call("docker rmi calicodockerprototype_felix", shell=True)
        call("docker rmi calicodockerprototype_aclmanager", shell=True)

    try:
        interfaces_raw = check_output("ip link show | grep -Eo ' (tap(.*?)):' |grep -Eo '[^ :]+'", shell=True)
        print "Removing interfaces:\n%s" % interfaces_raw
        interfaces = interfaces_raw.splitlines()
        for interface in interfaces:
            call("ip link delete %s" % interface, shell=True)
    except CalledProcessError:
        print "No interfaces to clean up"


def version():
    call('docker run --rm  -ti calicodockerprototype_felix  apt-cache policy calico-felix', shell=True)

if __name__ == '__main__':
    import os
    if os.geteuid() != 0:
        print "Calico must be run as root"
    else:
        arguments = docopt(__doc__)
        if validate_arguments(arguments):
            if arguments["launch"]:
                launch(arguments["--host"], arguments['--master_ip'], arguments["--peer"])
            if arguments["run"]:
                run(arguments['<IP>'],
                    arguments['--host'],
                    arguments['--group'],
                    arguments['--master_ip'],
                    ' '.join(arguments['<docker-options>']))
            if arguments["status"]:
                status(arguments["--master"])
            if arguments["reset"]:
                reset(arguments["--delete-images"])
            if arguments["version"]:
                version()
        else:
            print "Not yet"
