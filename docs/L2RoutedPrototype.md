# L2 Routed Docker Prototype

This prototype demonstrates Calico running in a docker environment
with L2 routed compute hosts.

## How to install and run it.

To run this prototype, you'll need a Windows, Mac or Linux computer.

The prototype is presented on a two node CoreOS cluster which can be run under VirtualBox and brought up using Vagrant. The config for doing this is stored in git.

### Initial environment setup
So, to get started, install Vagrant, Virtualbox and GIt for your OS.
* https://www.virtualbox.org/wiki/Downloads
* https://www.vagrantup.com/downloads.html
* http://git-scm.com/downloads

Clone this repo so the Vagrant file is available.
* `git clone https://github.com/tomdee/calico-docker-prototype.git`

From git (calico-docker-prototyp) directory, use Vagrant to start the CoreOS servers
* `vagrant up`

Congratulations, you now have two CoreOS servers with the Calico code checked out on them. The servers are named core-01 and core-02.  By default these have IP addresses 172.17.8.101 and 172.17.8.102. If you want to start again at any point, you can run

* `vagrant destroy`
* `vagrant up`

To connect to your servers
* Linux/MacOSX
   * `vagrant ssh core-01`
   * `vagrant ssh core-02`
* Windows
   * Follow instructions from https://github.com/nickryand/vagrant-multi-putty
   * `vagrant putty core-01`
   * `vagrant putty core-02`

At this point, it's worth checking that your two servers can ping each other.
* From core-01
   * `ping 172.17.8.102`
* From core-02
   * `ping 172.17.8.101`


<a id="setup"></a>
### Starting Calico
Calico currently requires that some components are run only on a single compute host on the network. For this prototype, we'll designate core-01 our "master" node and core-02 will be a secondary node.

For now, the script requires you to provide the IP address of the local CoreOS server the --host parameter.

All commands need to be run from the calico-docker-prototype directory
* `cd calico-docker-prototype`

* On core-01
   * `sudo ./calico launch --master --host=172.17.8.101 --peer=172.17.8.102`

* On core-02
   * `sudo ./calico launch --host=172.17.8.102 --peer=172.17.8.101`

This will start a number of Docker containers. Check they are running
* `sudo docker ps`

All the calico containers should share similar CREATED and STATUS values.


### Starting and networking containers
For this prototype, all containers need to be assigned IPs in the `192.168.0.0/16` range.

The general way to start a new container:  (Hint: don't run this yet; specific examples to run below.)
* `CID=$(sudo ./calico run CONTAINER_IP --master_ip=MASTER_IP --host=MY_IP --group=GROUP -- -ti  ubuntu)`
    * `CONTAINER_IP`, is the IP address to assign to the container; this must be unique address from the 192.168.0.0/16 range.
    * `--master_ip` points at the IP of the master node.
    * `--host` points at the IP of the current node.
    * `GROUP` is the name of the group.  Only containers in the same group can ping each other, groups are created on-demand so you can choose any name here.
    * `CID` will be set ot the container ID of the new container. 

You can attach to the container created above using
* `docker attach $CID`

Hit enter a few times to get a prompt. To get back out of the container and leave it running, remember to use `Ctrl-P,Q` rather than `exit`.

So, go ahead and start a couple of containers on each host.
* On core-01 (Note: the `--master_ip` parameter is not required on the master itself)
   * `A=$(sudo ./calico run 192.168.1.1 --host=172.17.8.101 --group=A_GROUP -- -ti  ubuntu)`
   * `B=$(sudo ./calico run 192.168.1.2 --host=172.17.8.101 --group=SHARED_GROUP -- -ti  ubuntu)`
* On core-02
   * `C=$(sudo ./calico run 192.168.1.3 --host=172.17.8.102 --master_ip=172.17.8.101 --group=C_GROUP -- -ti  ubuntu)`
   * `D=$(sudo ./calico run 192.168.1.4 --host=172.17.8.102 --master_ip=172.17.8.101 --group=SHARED_GROUP -- -ti  ubuntu)`

At this point, it should be possible to attach to B (`docker attach $B`) and check that it can ping D (192.168.1.4) but not A or C. A and C are in their own groups so shouldn't be able to ping anyone else.


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
>        sudo apt-add-repository ppa:james-page/docker
>        sudo apt-get update
>        sudo apt-get install docker.io


Development
- Create a virtualenv "virtualenv venv"
- Active venv ". venv/bin/activate"
- Install requirements "pip install -r requirements.txt"

Debugging
- Bring up individual host
- Destroy and recreate images
- Logging

