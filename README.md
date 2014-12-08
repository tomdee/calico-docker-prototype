# Calico docker prototype
This prototype demonstrates Calico running in a docker environment. If you do try using it, let me know how you get on by email (or just add a comment to the wiki).

*Note that there are some changes since an earlier version of this prototype; in particular, it uses Dockerfiles rather than images, automatically downloads a more recent version of the Felix code, and has been updated to allow for install under GCE.*

Peter White (`peter.white@metaswitch.com`)


## What the prototype covers
The prototype is a demonstration / proof of concept of several things.

+ It shows that Felix and the ACL Manager can run in docker containers on the host.

+ It shows that bird (BGP) servers can be installed and run on a docker container on the host, and can configure routing between endpoints (containers in this case).

+ It shows that it is possible to write a plugin that interoperates successfully with Felix and the ACL Manager to report status and program endpoints.

It has some important restrictions.

+ Felix occasionally terminates with network errors, sometimes without restarting in a timely manner - if so, `pkill -9 felix` will make it restart (and you can tell by checking `/var/log/calico/felix`). If it repeatedly fails with cryptic errors about inserting rules, you are probably missing some kernel modules for `iptables`.

+ The plugin is just a simple script reading a text file, not a proper plugin that is associated with the orchestration. Although the Calico code supports an arbitrarily complex networking model with complex rules and groups, the plugin configures a single security group with hard-coded rules (that all endpoints can send traffic to one another and to external addresses, but no other traffic is permitted).

+ The "orchestration" in this prototype itself is just a script that configures the networking for a docker container and writes the content to file.

There are two flavours of prototype, one for a Google Compute Engine environment (which relies both on having an L3 routed network and also on certain GCE commands), and one for a more general environment using an L2 routed network without GCE specific commands (such as a simple test environment where the compute servers are standard VMs). The documentation files are here for the [GCE prototype](src/master/GCEPrototype.md), and here for the [L2 routed prototype](src/master/L2RoutedPrototype.md).

