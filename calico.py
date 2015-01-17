"""Calico..

Usage:
  calico launch [--master] --ip=<IP> --peer=<IP>...
  calico run <IP> <Docker options>
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
from docopt import docopt
from subprocess import call


def validate_arguments(arguments):
    print(arguments)
    return True

def configure_bird(ip, peers):
    print peers[0]
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
    print base_config
    # Dump the file in the config directory

def configure_felix():
    pass
    # Fill in a felix.txt template and put it in the config directory

def launch(master, ip, peers):
    call("mkdir -p config", shell=True)
    configure_bird(ip, peers)
    configure_felix(ip, peers)

    # if master:
    #     call("sudo ./fig -f master.yml up", shell=True)
    # else:
    #     call("sudo ./fig -f node.yml up", shell=True)

def status():
    call("sudo ./fig ps", shell=True)
    #And maybe tail the "calico" log(s)

def run():
    # Bring create_container.sh inline here.

def reset(master):
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
            #TODO Pull out addresses and pass to launch
            run()
        if arguments["status"]:
            status()
        if arguments["reset"]:
            reset(arguments["--master"])
    else:
        print "Not yet"





