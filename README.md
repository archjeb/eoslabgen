# eoslabgen.py 
vEOS-lab Automated Topology Build ESXi Script 

The purpose of this script is to quickly build a vEOS-LAB topology for testing and simulating networks on an
ESXi host.


# Author
Jeremy Georges 

# Description
eoslabgen.py

The purpose of this script is to quickly build a vEOS-LAB topology from a yaml file and generate the entire vSwitch, PortGroup
and VM's effortlessly. All that is needed is the latest vEOS-lab.vmdk file from Arista, a locally generated yaml file with 
topology parameters and an ESXi host. 

This script has only been tested on ESXi6.5.



## Example

### Usage
```
$ ./eoslabgen.py --help
usage: eoslabgen.py [-h] -d DATASTORE -s HOST -u USER [-o PORT] [-S] -l
                    LOCAL_FILE -y YAML_FILE [-p PASSWORD]

Standard Arguments for talking to vCenter for vEOS

optional arguments:
  -h, --help            show this help message and exit
  -d DATASTORE, --datastore DATASTORE
                        Datastore name
  -s HOST, --host HOST  esxi host to connect to
  -u USER, --user USER  User name to use when connecting to host
  -o PORT, --port PORT  Port to connect on
  -S, --disable_ssl_verification
                        Disable ssl host certificate verification
  -l LOCAL_FILE, --local_file LOCAL_FILE
                        Local vEOS vmdk disk path to file to upload
  -y YAML_FILE, --yaml_file YAML_FILE
                        Yaml file to parse
  -p PASSWORD, --password PASSWORD
                        Password to use when connecting to host
```


### Example with sample yaml file: 
```
eosgenlab.py -d datastore1 -s 10.0.0.9 -u root -S -l vEOS-lab.vmdk -y example.yaml 
```

```
Enter password for host 10.0.0.9 and user root: 
Uploading vmdk for DC1-R1-Leaf-1...
Creating VM DC1-R1-Leaf-1...
Creating vSwitches and Portgroups for VM DC1-R1-Leaf-1
vEOS Ma1 binding to Lab-vEOS 
vEOS Et1 binding to vEOS-DC1-100 
vSwitch vEOS-DC1-100 does not exist. Creating...
vEOS Et2 binding to vEOS-DC1-101 
vSwitch vEOS-DC1-101 does not exist. Creating...
vEOS Et3 binding to vEOS-DC1-102 
vSwitch vEOS-DC1-102 does not exist. Creating...
vEOS Et4 binding to vEOS-DC1-103 
vSwitch vEOS-DC1-103 does not exist. Creating...
Uploading vmdk for DC1-R1-Leaf-2...
Creating VM DC1-R1-Leaf-2...
Creating vSwitches and Portgroups for VM DC1-R1-Leaf-2
vEOS Ma1 binding to Lab-vEOS 
vEOS Et1 binding to vEOS-DC1-100 
vSwitch vEOS-DC1-100 exists. Using existing...
vEOS Et2 binding to vEOS-DC1-101 
.
.
.truncated for brevity
.
.
Uploading vmdk for DC1-R3-Leaf-1...
Creating VM DC1-R3-Leaf-1...
Creating vSwitches and Portgroups for VM DC1-R3-Leaf-1
vEOS Ma1 binding to Lab-vEOS 
vEOS Et1 binding to vEOS-DC1-300 
vSwitch vEOS-DC1-300 exists. Using existing...
vEOS Et2 binding to vEOS-DC1-301 
vSwitch vEOS-DC1-301 exists. Using existing...
vEOS Et3 binding to vEOS-DC1-302 
vSwitch vEOS-DC1-302 does not exist. Creating...
vEOS Et4 binding to vEOS-DC1-303 
vSwitch vEOS-DC1-303 does not exist. Creating...
vEOS-lab generation complete!
```



# INSTALLATION:

eoslabgen requires pyVmomi. Easiest way is to install with pip.

1. pip install pyvmomi. Or see repo at https://github.com/vmware/pyvmomi 

2. clone eoslabgen from github repo.

3. Get the latest vEOS-lab.vmdk from Arista (create a support login)

4. Create your yaml file (example.yaml is provided in repo with 2 racks of leafs with MLAG links).

5. Execute and lab should generate



# LIMITATIONS:
This has only been tested on ESXi 6.5 but should work fine in previous releases. This uses the python SDK for the VMware vSphere API.
Also, it's really designed and tested around using a single ESXi target host; therefore it may or may not work in a multi ESXi server environment. 


License
=======
BSD-3, See LICENSE file
