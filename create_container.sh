#!/bin/bash -x

echo "Creating an endpoint with address $1"
IPADDR=$1

if [ "x$IPADDR" = "x" ]
then 
    echo "No IP addr"
    exit
fi

set -e

NAME=`echo $IPADDR | sed 's/\./_/g'`

# Create the container
rm -f /tmp/cid.txt
docker run -d --name=$NAME --cidfile /tmp/cid.txt --net=none ubuntu:14.04 sleep infinity

CID=`cat /tmp/cid.txt`
CPID=`docker inspect -f '{{.State.Pid}}' $CID`
IFACE=tap${CID:0:11}
echo "CID   = $CID"
echo "CPID  = $CPID"
echo "IFACE = $IFACE"

# Provision the networking
ln -s /proc/$CPID/ns/net /var/run/netns/$CPID

# Create the veth pair and move one end into container as eth0 :
ip link add $IFACE type veth peer name tmpiface
ip link set $IFACE up
ip link set tmpiface netns $CPID
ip netns exec $CPID ip link set dev tmpiface name eth0
ip netns exec $CPID ip link set eth0 up

# Add an IP address to that thing :
ip netns exec $CPID ip addr add $IPADDR/32 dev eth0
ip netns exec $CPID ip route add default dev eth0

# Get the MAC address.
MAC=`ip netns exec $CPID ip link show eth0 | grep ether | awk '{print $2}'`

FILE=/opt/plugin/data/$NAME.txt
echo "[endpoint $NAME]" >  $FILE 
echo "id=$CID"    >> $FILE
echo "ip=$IPADDR" >> $FILE
echo "mac=$MAC"   >> $FILE
echo "host=$HOSTNAME" >> $FILE
echo              >> $FILE

cat /opt/plugin/data/* > /opt/plugin/data.txt
