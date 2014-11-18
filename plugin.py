# This is a dummy plugin. It takes a file, loads it all up, then throws it over
# the interfaces.
import ConfigParser
import json
import logging
import sys
import time
import zmq

zmq_context = zmq.Context()

# Logging
log  = logging.getLogger(__name__)

log.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s %(lineno)d: %(message)s')

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
log.addHandler(handler)


class Endpoint:
    """
    Endpoint as seen by the plugin. Enough to know what to put in an endpoint created message.
    """
    def __init__(self, id, mac, ip):
        self.id = id
        self.mac = mac
        self.ip = ip


#*****************************************************************************#
#* Global variables for system state. These will be set up in load_files.    *#
#*****************************************************************************#
all_ips     = set()
eps_by_host = dict()
felix_ip    = dict()
acl_ip      = None

def load_files(config_file):
    """
    Load a config file with the data in it. Each section is an endpoint.
    """
    parser = ConfigParser.ConfigParser()
    parser.read(config_file)

    # Build up the list of sections.
    for section in parser.sections():
        items = dict(parser.items(section))
        if section.lower().startswith("endpoint"):
            #*****************************************************************#
            #* Endpoint. Note that we just fall over if there are missing    *#
            #* lines.                                                        *#
            #*****************************************************************#
            id   = items['id']
            mac  = items['mac']
            ip   = items['ip']
            host = items['host']

            if not host in eps_by_host:
                eps_by_host[host] = set()
            eps_by_host[host].add(Endpoint(id, mac, ip))
            all_ips.add(ip)
            log.debug("Found configured endpoint %s (host=%s, mac=%s, ip=%s)" %
                      (id, host, mac, ip))
        elif section.lower().startswith("acl"):
            acl_ip = items['ip']
            log.debug("Found ACL manager at %s" % (acl_ip))
        elif section.lower().startswith("felix"):
            ip = items['ip']
            host = items['host']
            felix_ip[host] = ip
            log.debug("Found configured Felix %s at %s" % (host, ip))

def do_ep_api():
    # Create both EP sockets
    resync_socket = zmq_context.socket(zmq.REP)
    resync_socket.bind("tcp://*:9901")
    log.debug("Created EP socket for resync")

    #*************************************************************************#
    #* Wait for a resync request, and send the response. We wait for a       *#
    #* resync from every Felix, so it may take a while (if a Felix is down,  *#
    #* we have to wait for connection timeout, which can take 30s).          *#
    #*************************************************************************#
    count = 0

    while count < len(felix_ip):
        data   = resync_socket.recv()
        fields = json.loads(data)
        log.debug("Got %s EP msg : %s" % (fields['type'], fields))
        if fields['type'] == "RESYNCSTATE":
            resync_id = fields['resync_id']
            host      = fields['hostname']
            if host in eps_by_host:
                eps = eps_by_host[host]
            else:
                eps = set()

            rsp = {"rc": "SUCCESS",
                   "message": "Hooray",
                   "type": fields['type'],
                   "endpoint_count": str(len(eps))}
            resync_socket.send(json.dumps(rsp))

            create_socket = zmq_context.socket(zmq.REQ)
            create_socket.connect("tcp://%s:9902" % felix_ip[host])
        
            # Send all of the ENDPOINTCREATED messages.
            for ep in eps:
                msg = {"type": "ENDPOINTCREATED",
                       "mac": ep.mac,
                       "endpoint_id": ep.id,
                       "resync_id": resync_id,
                       "issued": int(time.time()* 1000),
                       "state": "enabled",
                       "addrs": [{"addr": ep.ip}]}
                log.debug("Sending ENDPOINTCREATED to %s : %s" % (host, msg))
                create_socket.send(json.dumps(msg))
                create_socket.recv()
                log.debug("Got endpoint created response")

            count += 1
        else:
            rsp = {"rc": "SUCCESS", "message": "Hooray", "type": fields['type']}
            resync_socket.send(json.dumps(rsp))
  
    # Tear down the resync_socket to allow faster restart.
    resync_socket.close()

def do_network_api():
    # Create the sockets
    rep_socket = zmq_context.socket(zmq.REP)
    rep_socket.bind("tcp://*:9903")

    pub_socket = zmq_context.socket(zmq.PUB)
    pub_socket.bind("tcp://*:9904")
  
    # ACL manager needs to send us a GETGROUPS request - wait for it.
    got_groups = False
    while not got_groups:
        data   = rep_socket.recv()
        fields = json.loads(data)
        log.debug("Got %s network msg : %s" % (fields['type'], fields))
        if fields['type'] == "GETGROUPS":
            rsp = {"rc": "SUCCESS",
                   "message": "Hooray",
                   "type": fields['type']}
            rep_socket.send(json.dumps(rsp))
            got_groups = True
        else:
            # Heartbeat. Whatever.
            rsp = {"rc": "SUCCESS", "message": "Hooray", "type": fields['type']}
            rep_socket.send(json.dumps(rsp))

    # Tear down the rep_socket to allow faster restart.
    rep_socket.close()
 
    # Now the PUB socket.
    log.debug("Build data to publish")
    members = dict()
    for host in eps_by_host:
        endpoints = eps_by_host[host]
        for endpoint in endpoints:
            members[endpoint.id] = [endpoint.ip]

    rules = dict()

    rule1 = {"group": "dummy_security_group",
             "cidr": None,
             "protocol": None,
             "port": None}

    rule2 = {"group": None,
             "cidr": "0.0.0.0/0",
             "protocol": None,
             "port": None}

    rules["inbound"] = [rule1]
    rules["outbound"] = [rule1, rule2]
    rules["inbound_default"] = "deny"
    rules["outbound_default"] = "deny"
    
    data = {"type": "GROUPUPDATE",
            "group": "dummy_security_group",
            "rules": rules, # all outbound, inbound from SG
            "members": members, # all endpoints
            "issued": int(time.time() * 1000)}

    while True:
        # Send the data over and over, until the ACL manager is listening.
        log.debug("Sending data about all groups : %s", data)
        pub_socket.send_multipart(['groups'.encode('utf-8'),
                                   json.dumps(data).encode('utf-8')])
        time.sleep(5)


def main():
    # Load files.
    load_files("/opt/plugin/data.txt")

    # Do what we need to over the endpoint API.
    do_ep_api()

    # Do what we need to over the network API.
    do_network_api()
      
main()
