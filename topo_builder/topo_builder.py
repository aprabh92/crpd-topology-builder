#!/usr/bin/env python
__author__ = "Aravind"
__email__ = "aprabh@juniper.net"

import sys
import os 
import docker 
import argparse
import yaml
import logging

'''
Note: Ensure the directory /var/run/netns exists. if not do the below
      mkdir -p /var/run/netns
      
      This works only on linux systems and not on mac and windows. Uses veth to create
      interfaces between containers. If using this standard ubuntu/alpine containers 
      ensure that the distro can use "ip addr" commands.

To Do:
1. Ability to delete link connectivity and rebinding of interfaces without deleting containers
2. Exception handling
'''

# Argument parser
parser = argparse.ArgumentParser()
parser.add_argument("-t", action='store', dest='topology', help='topology yaml file')
parser.add_argument("-a", action='store', dest='action', help='create/delete/config/backup topology')
parser.add_argument("-cfg", action='store', dest='config', help='config file to configure containers')
parser.add_argument("-c", action='store', dest='container', help='container to which config has to be passed.')
parser.add_argument("-f", action='store_true', dest='force', default=False, help='remove volumes when deleting the topology.')
args = parser.parse_args()

# Initiate logger
logging.basicConfig(filename='topo_creator.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

#Usage Banner 
def banner():
    print('+-----------------------------------------------------------------------+')
    print('|           container topology builder                                  |')
    print('+-----------------------------------------------------------------------+')
    print('| Usage: ./topo_builder.py -a create/delete/config/backup -t <yml file> |')
    print('|  In case you want to pass common initial configuration                |')
    print('|  to all containers then. issue the below command to all               |')
    print('|                                                                       |')
    print('|  In case you want to delete the created volumes pass -f flag.         |')
    print('|  Only applicable when issuing the delete action.                      |')
    print('|                                                                       |')
    print('|./topo_builder.py -a config -t <yml file> -cfg <config.txt>            |')
    print('|                                                                       |')
    print('| In case you want to configure different containers with               |')
    print('| with different configuration files then issue the below.              |')
    print('|                                                                       |')
    print('| ./topo_builder.py -a config -c <container name> -cfg <file>           |')
    print('|                                                                       |')
    print('| ./topo_builder.py -a backup -c <container name>   to backup single    |')
    print('| ./topo_builder.py -a backup -t <yml file> to backup all               |')
    print('|    For general help: ./topo_builder.py --help                         |')
    print('|  Log file would be generated in cwd as topo_creator.log               |')
    print('+-----------------------------------------------------------------------+')
    

# Parse yaml and start/stop containers
"""
Input: json input  
Output:
 links --> {'leaf2_spine2': '192.168.60.5/30',
            'leaf2_spine1': '192.168.60.1/30',
            'leaf1_spine1': '192.168.50.1/30',
            'leaf1_spine2': '192.168.50.5/30',
            'spine2_leaf1': '192.168.50.6/30',
            'spine2_leaf2': '192.168.60.2/30',
            'spine1_leaf1': '192.168.50.2/30',
            'spine1_leaf2': '192.168.60.2/30'}

image: --> {'spine1': 'crpd-rift:latest',
            'spine2': 'crpd-rift:latest',
            'leaf1': 'crpd-rift:latest',
            'leaf2': 'crpd-rift:latest'}
""" 
#ifdef VERSION1
#TO-DO: review if it can be optimized with comprehensions
#endif /* VERSION1 */
def parse(mapp):
    links = {}
    images = {}
    volumes = {}
    dup_intf = []
    for node in mapp["nodes"]:
        nodeName = node["name"]
        images[nodeName] = node["image"]
        volumes[nodeName] = {}
        for intf in node["link"]:
            if intf["name"] in dup_intf:
                links[nodeName+"_"+intf["name"]+"_"+str(dup_intf.count(intf["name"]))] = intf["prefix"]
                dup_intf.append(intf["name"])
            else:
                links[nodeName+"_"+intf["name"]] = intf["prefix"]
                dup_intf.append(intf["name"])
        dup_intf=[]
        for vol in node["volume"]:
            volumes[nodeName][nodeName+"_"+vol["name"]] = { "bind": vol["path"], "mode": "rw" }
    return links, images, volumes

# Create/delete volumes for containers
def handleVolume(client, name, action):
    if action == 'create':
        try:
            if (client.volumes.get(name)):
                logging.debug("volume exists. Will be reutilised")
                return name
        except docker.errors.NotFound as err:
            logging.info("Volume {} does not exist. Will be created".format(name))
            client.volumes.create(name=name)
            return name
        except docker.errors.APIError as err:
            print("API server error",err)

    if action == 'delete':
        try:
            client.volumes.get(name).remove()
            logging.info("Volume {} deleted".format(name))
        except docker.errors.APIError as err:
            print("API server error",err)

def handleContainer(client, name, image, volumes, action):
        if action =='create':
            if (client.images.get(image)):  
                logging.debug("image present, starting container")
                logging.debug("attaching volumes: %s", volumes)
                client.containers.run(image=image, name=name, hostname=name, network_mode='bridge',
                                        volumes=volumes, privileged=True, detach=True,
                                        ports={'830/tcp':None,'40051/tcp':None,'22/tcp':None}
                                        )
            else:
                logging.error("Faled: Image not present. Please load the image first using docker load -i <image>")
        if action == 'delete':
            _id = client.containers.get(name)
            logging.info("stopping container {}".format(_id))
            if (_id):
                _id.stop(timeout=5)
                _id.remove()
            else:
                logging.info("container {} doesn't exist".format(_id))


# Create Veth pair to connect to containers 
def createVeth(name, peername):
    try:
        os.popen('ip link add {} type veth peer name {}'.format(name, peername))
        os.popen('ip link set {} up'.format(name))
        os.popen('ip link set {} up'.format(peername))
        return 1
    except:
        return "Error creating Veth pair"

# Delete veth. Currently not used [WIP]
'''
Need this for rebinding veth interfaces to create 
new topology without restart containers 
'''
def deleteveth(client, name):
    # peer end will be automatically deleted
    try:
        os.popen('ip link del {}'.format(name))
        return 1
    except:
        return "Error deleting veth pair"


# Connect interface to container 
def connect(client, interface, container, _id, ip):
    try:
        os.popen('ip link set {} netns {}'.format(interface, container))
        _id = client.containers.get(container)
        _id.exec_run(cmd='ip link set {} up'.format(interface))
        _id.exec_run(cmd='ip addr add {} dev {}'.format(ip, interface))
        return 1
    except docker.errors.APIError as err:
        print("API server error",err)
    except docker.errors.InvalidArgument as err:
        print ("argument not a valid descriptor",err)
    except docker.errors.ContainerError as err:
        print ("Container error",err)


# Find PID of the container to create named network namespace
def findPid(client, container):
    try:
        print("entered container {}".format(container))
        _id = client.containers.get(container).id
        pid = client_lowlevel.inspect_container(_id)['State']['Pid']
        os.popen('ln -sfT /proc/{}/ns/net /var/run/netns/{}'.format(pid, container))
        return _id

    except docker.errors.APIError as err:
        print("API server error",err)
    except docker.errors.InvalidArgument as err:
        print ("argument not a valid descriptor",err)
    except docker.errors.ContainerError as err:
        print ("Container error",err)


# Configures Basic initial commands. Configuration is passed as a file
'''
exec_run seems to have been depricated. use exec_create and exec_start
'''
def configureJunos(client, container, config):
    print("Configuring container {} with provided config file".format(container))
    logging.info("Configuring container {}  with provided config file".format(container))
    _id = client.containers.get(container)
    if(_id):
        with open(config, 'r') as cfg:
            con = cfg.readlines()
            for i in con:
                j = '"'+i+'"'
                _id.exec_run(cmd='cli -c configure;{}'.format(j))
            try:
                commit_out = _id.exec_run(cmd='cli -c "configure;commit"').output
                logging.debug(commit_out)
            except:
                logging.error("Commit failed: check the commands in config file")
                
# Backup configuration
def backupConfig(client, container):
    logging.info("Backing up container {} ".format(container))
    _id = client.containers.get(container)
    if(_id):
        print(_id)
        text = _id.exec_run(cmd='cli -c "show configuration | display set"').output
        with open('backup_{}.txt'.format(container),'w') as fout:
            fout.writelines(text)
            fout.close()
        print("backup of container {} completed ".format(container))
        logging.info("backup of container {} completed ".format(container))
    
def main():
    banner()
    # Initialize docker
    global client_lowlevel
    client = docker.from_env()
    client_lowlevel = docker.APIClient(base_url='unix://var/run/docker.sock')
    if args.action:
        # Load yaml file
        with open(args.topology, "r") as f:
            mapp = yaml.safe_load(f)
        # Parse the yaml
        links,images,volumes = parse(mapp)
        # action create topology
        if args.action == 'create':
            print(" ********** Creating topology ************* ")
            for container in images:
                for volume in volumes[container]:
                    handleVolume(client, volume, args.action)
                handleContainer(client, container, images[container], volumes[container], args.action)
                logging.info("{} container {}".format(args.action, container))

            logging.debug(50*"*")
            logging.debug("Images: \n")
            logging.debug(images)
            logging.debug(50*"*")
            logging.debug("links: \n")
            logging.debug(links)
            logging.debug(50*"*")
            logging.debug("Volumes: \n")
            logging.debug(volumes)
            logging.debug(50*"*")
                
            # create links
            del_list = [] 
            for link in links:
                if link not in del_list:
                    name = link
                    ip = links[link]
                    temp = name.split("_")
                    container = temp[0]
                    peer_container = temp[1]
                    if len(temp) == 3:
                        # swap only first 2 elements in list and retain the index # for intf
                        temp_peer_name = temp[:2]
                        temp_peer_name = temp_peer_name[::-1]
                        temp_peer_name.append(temp[2])
                        peer_name = '_'.join(temp_peer_name)
                    else:
                        temp = temp[::-1]
                        peer_name = '_'.join(temp)
                    if peer_name in links:
                        peer_ip = links[peer_name]
                        createVeth(name, peer_name)
                        cid = findPid(client, container)
                        connect(client, name, container, cid, ip)
                        pcid = findPid(client, peer_container)
                        connect(client, peer_name, peer_container, pcid, peer_ip)
                        del_list.append(peer_name)
                        del_list.append(name)

        # action delete topology
        if args.action == 'delete':
            print(" ****** Deleting topology ******** ")
            for container in images:
                handleContainer(client, container, images[container], None, args.action)
                logging.info("{} container {}".format(args.action, container))
                if args.force == True:
                    for volume in volumes[container]:
                        handleVolume(client, volume, args.action)
                        logging.info("{} volume {}".format(args.action, volume))

        # Initial configuration.Only applicable to cRPD
        if args.action == 'config':
            if args.container:
                print(" **** Configuring container {} ".format(args.container))
                configureJunos(client, args.container, args.config)
            else:
                print (" *********** Sending initial config to cRPD ************ ") 
                yaml_open = open(args.topology)
                mapp = yaml.load(yaml_open, Loader=yaml.FullLoader)
                links,images,volumes = parse(mapp)
                for container in images:
                    configureJunos(client, container, args.config)      

        if args.action == 'backup':
            if args.container:
                backupConfig(client, args.container)
            else:
                with open(args.topology, "r") as f:
                    mapp = yaml.safe_load(f)
                links,images,volumes = parse(mapp)
                for container in images:
                    backupConfig(client, container)
#endif /* VERSION1 */

# Main function
if __name__=="__main__":
    main()
