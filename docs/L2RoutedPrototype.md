# L2 Routed Docker Prototype

This prototype demonstrates Calico running in a docker environment
with L2 routed compute hosts.

## How to install and run it.

To run this prototype, you'll need a Windows, Mac or Linux computer.

The prototype is presented on a two node CoreOS cluster which can be run under VirtualBox and brought up using Vagrant. The config for doing this is stored in git.

### Initial setup
So, to get started, install Vagrant, Virtualbox and GIt for your OS.
* https://www.virtualbox.org/wiki/Downloads
* https://www.vagrantup.com/downloads.html
* http://git-scm.com/downloads

Clone this repo
* `git clone https://github.com/tomdee/calico-docker-prototype.git`

Start the CoreOS servers
* `vagrant up`

If you want to start again at any point, you can run
* `vagrant destroy -f core-01 core-02`
* `vagrant up`

Congratulations, you now have two CoreOS servers with the Calico code checked out on them.
To connect to your servers
* Linux/MacOSX
** `vagrant ssh core-01`
** `vagrant ssh core-02`
* Windows
** Follow instructions from https://github.com/nickryand/vagrant-multi-putty
** `vagrant putty core-01`
** `vagrant putty core-02`

At this point, it's worth checking that your two servers can ping each other.
#### From core-01
* `ping 172.17.8.102`
#### From core-01
* `ping 172.17.8.101`


<a id="setup"></a>
### Starting Calico
Calico currently requires that some components are run only on a single compute host on the network. For this prototype, we'll designate core-01 our "master" node and core-02 will be a secondary node.

#### On core-01
* `sudo ./calico launch --master --ip=172.17.8.101 --peer=172.17.8.102`

#### On core-02
* `sudo ./calico launch --ip=172.17.8.102 --peer=172.17.8.101`

This will start a number of Docker containers. Check they are running
* `sudo docker ps`

All the calico containers should share similar CREATED and STATUS values.


### Starting and networking containers
For this prototype, all containers need to be assigned IPs in the `192.168.0.0/16` range.

To start a new container
* `C=$(sudo ./calico run 192.168.1.2 --master=TODO --group=GROUP -- -ti  ubuntu)`
    * The first `IP`, is the IP address to assign to the container.
    * `--master` points at the IP of the master node.
    * `GROUP` is the name of the group. In this prototype, each
      endpoint is in a single group, and the other endpoints only have
      access to it if they are in the same group. Names are arbitrary.

Attach to the container created above using
* `sudo docker attach $C`

So, go ahead and start a couple of containers on each host.
#### On core-01
* `A=$(sudo ./calico run 192.168.1.1 --master=172.17.8.101 --group=A_GROUP -- -ti  ubuntu)`
* `B=$(sudo ./calico run 192.168.1.2 --master=172.17.8.101 --group=SHARED_GROUP -- -ti  ubuntu)`
#### On core-02
* `C=$(sudo ./calico run 192.168.1.3 --master=172.17.8.101 --group=C_GROUP -- -ti  ubuntu)`
* `D=$(sudo ./calico run 192.168.1.4 --master=172.17.8.101 --group=SHARED_GROUP -- -ti  ubuntu)`

The plugin checks for configuration dynamically, but it might take
quite some time (up to a minute or two) before it notices and passes
through changes to Calico.

TODO:
attach to B and check it can ping D (192.168.1.4) but not A or C
attach to D and check it can ping B (192.168.1.2) but not A or C
attach to A or C and see they can't ping anyone else




Finally, after all your containers have finished running, to ensure everything is cleaned up, you can run
* sudo ./calico reset

## Troubleshooting

### Basic checks
If you have rebooted your hosts, then some configuration gets lost. Rerun the instructions from [here](#restart)
to make sure that they are all in a good state.


### Logging and diagnostics
* Tail logs from all components with TODO
* View all logs from a single component with
  * `sudo docker logs calicodockerprototype_aclmanager_1`


### Hacking on the code
The recommended development platform is Ubuntu 14.04 with the latest version of Docker.
On Ubuntu Trusty, the following instructions got Docker 1.3
  installed:
        sudo apt-add-repository ppa:james-page/docker
        sudo apt-get update
        sudo apt-get install docker.io


Development
- Create a virtualenv "virtualenv venv"
- Active venv ". venv/bin/activate"
- Install requirements "pip install -r requirements.txt"

Debugging
- Bring up individual host
- Destroy and recreate images
- Logging

