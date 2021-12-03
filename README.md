# CRPD Topology Builder
cRPD is Juniper Networks containerized routing stack. It can run on top of Linux distros to program kernel routing tables. This
project allows to bring up random cRPD topologies to help build networks and test cRPD related features. This script relies on 
docker APIs and the links created between containers would be a veth interface.

The definition of the topology is an input from a yaml file and we can also pass initial configuration to all cRPD containers.
The configuration can be passed into the container in 2 ways. we can either use a file input with set commands present with each in a new line,
or directly prebuild the configuration file and paste it in the config directory which would have been mounted as a volume before starting
the container.  

we can also use this for other containers in order to bring them up, but in order to connect, we make the container a named
network namespace (docker usually keeps them unnamed) and use ip link commands to move the interfaces into the respective
container and assign an IP address to it. 

Note: This works only on linux distros

## Required packages

Ensure that /var/run/netns directory exists on the host. if not create the below on the underlying host
```
mkdir -p /var/run/netns
```

### Below are the required packages for this script to work
```
1. docker 
2. docker python APIs 
3. iproute2 package must be installed in the container image (The container image must be able to handle ip link and ip route commands)
4. Python2/Python3
5. pyyaml (This is used for import the yaml definitions into python)
```
### Known issues
The docker APIs used are a little old. It looks like exec_run lowlevel docker API is depricated and this script relies on that. so ensure 
the correct version is used. The newer APIs use exec_create and exec_run calls in order to work in the latest APIs. Will update this soon
to ensure correct APIs are used.

This was tested on the below version
```
root@vNTC-4:/home/csim/aravind/20.3/vmx# pip freeze | grep docker
docker==4.2.0

root@vNTC-4:/home/csim/aravind/20.3/vmx# docker --version
Docker version 18.09.7, build 2d0083d
```
This version does not support addition of IPv6 addresses yet. When an interface is brought up, it automatically comes up with only 
the link local address. Passing IPV6 addresses for links in the yaml file would not work.

## Topology template definition 
The template is a YAML file definition where we mention the container name, image and link to which container. Below is the template
for one of the nodes.

```
nodes:
  - name: tof1
    image: crpd-rift:latest
    link:
      - name: spine1
        prefix: 192.168.50.1/30
      - name: spine2
        prefix: 192.168.50.5/30
      - name: spine3
        prefix: 192.168.50.9/30
    volume:
        - name: config
          path: /config
        - name: varlog
          path: /var/log
```
- name: Defines the name of the container
- image: image to use to spin up the container. This script assumes that the image is already present and loaded. 
       Verify if the image is present using "docker images"
- link: defines the link to be created between the nodes . In the above mentioned template links will be created 
      between tof1 and spine1 , tof1 and spine2, tof1 and spine3 with the respective prefixes mentioned.  
- volume: defines the volumes to be mounted on each container. In the above mentioned template volumes for configuration and logs are mounted to the provided paths. Configurations can be pre-provisioned by coping them to the config volume before starting the container.
The interface name would be as tof1_spine1, tof1_spine2 and tof1_spine3.

## Configuration template
There are two methods in which you can have the configuration sent to all the containers. 

1. Configuration file containing the set commands 
    * The configuration template should be a file with all Junos configuration in set format. This configuration would 
      be passed into all the cRPD containers and get committed. Ensure that the configuration is valid else Junos may 
      reject the configuration. The action arg "-a" should be "config"
    * You can pass the config file with arg -cfg to have the common config across all
      containers
    * Optionally you can pass the arg -c to pass the config  to pass the configuration to a specific container.
    * Check the example section below.

2. Prebuild the configuration and paste it in the respective config volume mounted.
    * You can prebuild the configuration and store it as junos.conf.gz in the volume mounted.
    * Find the volume mount path for respective container using "docker volume ls" and inspect using "docker volume inspect <name>"
    * move the junos.conf.gz into the volume directory
    * start the container "docker exec -it <container> cli" and observe that config is pre-loaded.
 
3. Backup configuration 
    * You can backup the configuration from a container using action "backup" to backup config from all containers
    * Optionally backup from specific container using argument -c <name of container>
    * The backup would be stored as backup_<name of container>.txt and the config would be in set format. 
```
topology_builder % more config_rift_common.txt

set system scripts language python3
set system root-authentication encrypted-password $6$/ADg8$bBCD5cOVSV6BFZJMIYGBmNknxZeh5uZwold81fly2IfDsxawpJ.BJ2sM3x3NirvrjUlZfzQ30bDUU.EwkGfFb.
set groups rift-defaults protocols rift node-id auto
set groups rift-defaults protocols rift level auto
set groups rift-defaults protocols rift lie-receive-address family inet 224.0.0.120
set groups rift-defaults protocols rift lie-receive-address family inet6 ff02::a1f7
set groups rift-defaults protocols rift interface <*> lie-transmit-address family inet 224.0.0.120
set groups rift-defaults protocols rift interface <*> lie-transmit-address family inet6 ff02::a1f7
set groups rift-defaults protocols rift interface <*> bfd-liveness-detection minimum-interval 1000
set routing-options programmable-rpd rib-service dynamic-next-hop-interface enable
set protocols rift apply-groups rift-defaults
```

## Script usage details 

1. Ensure that a topology file is created 
2. Ensure a configuration file is created (Optional) 
3. Create virtual env using "virtualenv -p /usr/bin/python3 crpd-env"
4. Activate venv "source crpd-env/bin/active"
5. Install dependencies using "pip install -r requirements.txt"

### To create the topology 
```
python topo_builder.py -a create -t 3x3.yml 
```

### To delete the topology
```
python topo_builder.py -a delete -t 3x3.yml 
```

### To pass the same configuration to all containers in the topology
```
python topo_builder.py -a config -t 3x3.yml -cfg config_rift_common.txt
```

### To pass a configuration to a particular container 
```
python topo_builder.py -a config -c leaf1 -cfg backup_leaf1.txt

Here leaf1 is the container name and backup_leaf1.txt is the configuration file in set format
```
### To backup configuration from whole topology
```
python topo_builder.py -a backup -t 3x3.yml
```

### To backup configuration from a specific container
```
python topo_builder.py -a backup -c leaf1
```

### Logging
```
The script logs all the debug and info logs into topo_creator.log file which would be created in the same directory.
```
## Example Topology Bring up 
Below topology has been brought up using the script 

### Topology
```

                                                              +------------------------+                        +-------------------------+
                                                              |                        |                        |                         |
                                                              |      TOF1              |                        |        TOF2             |
                                                              |                        |                        |                         |
                                                              |                        |                        |                         |
                                                              +--+--------+-----+------+                        +-+---------+-------+-----+
                                                                 |        |     |                                 |         |       |
                                                                 |        |     +--------------------------------------------------------++
                                                                 |  +-------------------------------------------------------+       |    |
                                                                 |  |     |                                       |                 |    |
                                                                 |  |     +--------------------+                  |                 |    |
                                                                 |  |                          |                  |                 |    |
                                            +--------------------+--++                   +-----+------------------++             +--+----+------------------+
                                            |                        |                   |                         |             |                          |
                                            |          Spine1        |                   |      Spine 2            |             |         Spine 3          |
                                            |                        |                   |                         |             |                          |
              +-----------------------------+------+------+--+-------+            +------+------+------------------+             +--------------------------+    
              |                                    |      |  |                    |             |          |-----------------------------------------------------+
              |                                    |      |  +---------------------------------------------------------------------------------------+ |   |     |
              |                 +--------------------------------------------------------------------------------------------------------|     |     | |   |     |
              |                 |       +------------------------------------------------------------------------------------------------------+     | |   |     |
              |                 |       |          +---------------------------------------------------------+    |     +------------------------------+   |     |
              |                 |       |                 |                |      |                          |    |     |                            |     |     |
       +------+-----------------+-------+-+          +----+----------------+------+--+             +---------+----+-----+-----------+         +------+-----+-----+---------+
       |                                  |          |                               |             |                                |         |                            |
       |                                  |          |                               |             |                                |         |       Leaf 4               |
       |            Leaf 1                |          |          leaf 2               |             |       Leaf 3                   |         |                            |
       |                                  |          |                               |             |                                |         |                            |
       |                                  |          |                               |             |                                |         |                            |
       +----------------------------------+          +-------------------------------+             +--------------------------------+         |                            |
                                                                                                                                              +----------------------------+
```

### Topology tempalte
The file has been saved as 2x3x4.yml under the directory topologies
``` 
nodes:
  - name: tof1
    image: crpd-rift:latest
    link:
      - name: spine1
        prefix: 192.168.50.1/30
      - name: spine2
        prefix: 192.168.50.5/30
      - name: spine3
        prefix: 192.168.50.9/30
    volume:
        - name: config
          path: /config
        - name: varlog
          path: /var/log

  - name: tof2
    image: crpd-rift:latest
    link:
      - name: spine1
        prefix: 192.168.51.1/30
      - name: spine2
        prefix: 192.168.51.5/30
      - name: spine3
        prefix: 192.168.51.9/30
    volume:
        - name: config
          path: /config
        - name: varlog
          path: /var/log

  - name: spine1
    image: crpd-rift:latest
    link:
      - name: tof1
        prefix: 192.168.50.2/30
      - name: tof2
        prefix: 192.168.51.2/30
      - name: leaf1
        prefix: 192.168.60.1/30
      - name: leaf2
        prefix: 192.168.60.5/30
      - name: leaf3
        prefix: 192.168.60.9/30
      - name: leaf4
        prefix: 192.168.60.13/30
    volume:
        - name: config
          path: /config
        - name: varlog
          path: /var/log
...
...
...
...
```

### Usage 
```
python3 topo_builder.py -a create -t 2x3x4.yml
+-----------------------------------------------------------+
|           container topology builder                      |
+-----------------------------------------------------------+
|   Usage: ./topo_builder.py -a create/delete -t <yml file> |
|                                                           |
|  In case you want to pass common initial configuration    |
|  to all containers then. issue the below command to all   |
|                                                              |
|./topo_builder.py -a config -t <yml file> -cfg <config.txt>|
|                                                           |
|    For general help: ./topo_builder.py --help             |
|  Log file would be generated in cwd as topo_creator.log   |
+-----------------------------------------------------------+
********** Creating topology *************
entered container spine1
entered container leaf2
entered container leaf1
entered container spine2
entered container tof2
entered container spine3
entered container leaf3
entered container spine3
entered container leaf2
entered container spine2
entered container leaf3
entered container spine1
entered container leaf4
entered container spine2
entered container tof2
entered container spine2
entered container spine2
entered container leaf3
entered container leaf1
entered container spine1
entered container spine3
entered container tof1
entered container leaf1
entered container spine3
entered container spine1
entered container tof2
entered container spine3
entered container leaf4
entered container spine1
entered container tof1
entered container leaf4
entered container spine1
entered container spine2
entered container tof1
entered container leaf2
entered container spine3
 
 
 python3 topo_builder.py -a config -t 2x3x4.yml -cfg config_rift_common.txt
+-----------------------------------------------------------+
|           container topology builder                      |
+-----------------------------------------------------------+
|   Usage: ./topo_builder.py -a create/delete -t <yml file> |
|                                                           |
|  In case you want to pass common initial configuration    |
|  to all containers then. issue the below command to all   |
|                                                           |
|./topo_builder.py -a config -t <yml file> -cfg <config.txt>|
|                                                           |
|    For general help: ./topo_builder.py --help             |
|  Log file would be generated in cwd as topo_creator.log   |
+-----------------------------------------------------------+
*********** Sending initial config to cRPD ************
Configuring container leaf3 with provided config file
Configuring container tof1 with provided config file
Configuring container spine1 with provided config file
Configuring container spine2 with provided config file
Configuring container tof2 with provided config file
Configuring container leaf4 with provided config file
Configuring container spine3 with provided config file
Configuring container leaf1 with provided config file
Configuring container leaf2 with provided config file
 
 
 
python3 topo_builder.py -a delete -t 2x3x4.yml
+-----------------------------------------------------------+
|           container topology builder                      |
+-----------------------------------------------------------+
|   Usage: ./topo_builder.py -a create/delete -t <yml file> |
|                                                           |
|  In case you want to pass common initial configuration    |
|  to all containers then. issue the below command to all   |
|                                                              |
|./topo_builder.py -a config -t <yml file> -cfg <config.txt>|
|                                                           |
|    For general help: ./topo_builder.py --help             |
|  Log file would be generated in cwd as topo_creator.log   |
+-----------------------------------------------------------+
****** Deleting topology ********



root@vNTC-4:/home/csim/aravind# ./topo_builder.py -a config -c leaf1 -cfg backup_leaf1.txt
+-----------------------------------------------------------------------+
|           container topology builder                                  |
+-----------------------------------------------------------------------+
| Usage: ./topo_builder.py -a create/delete/config/backup -t <yml file> |
|                                                                       |
|  In case you want to pass common initial configuration                |
|  to all containers then. issue the below command to all               |
|			                                                           |
|./topo_builder.py -a config -t <yml file> -cfg <config.txt>            |
|                                                                       |
| In case you want to configure different containers with               |
| with different configuration files then issue the below.              |
|                                                                       |
| ./topo_builder.py -a config -c <container name> -cfg <file>           |
|                                                                       |
|    For general help: ./topo_builder.py --help                         |
|  Log file would be generated in cwd as topo_creator.log               |
+-----------------------------------------------------------------------+
 **** Configuring container leaf1
Configuring container leaf1 with provided config file


root@vNTC-4:/home/csim/aravind# ./topo_builder.py -a backup -c leaf1
<Container: 6bc0308414>
backup of container leaf1 completed

```

