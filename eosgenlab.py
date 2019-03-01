#!/usr/bin/env python
'''
The purpose of this script is to help quickly deploy a vEOS-lab
environment for testing. By leveraging the pyvmomi module, we can quickly
create vEOS VMs, create vSwitches and Port Groups all from parsing a yaml file
that spells out the switch hostname and the interfaces.
Normally we'd clone a template, but that requires vSphere. The idea here is do
this directly on an esxi host. The script would have to be written differently
to handle vSphere APIs to account for DC, resourcePools, etc.
Perhaps that could be a version 2 :-)

Sample yaml file structure:
---------------------------
DC1-Spine-1:
    description: DC1-Spine1
    Ma1: Lab-vEOS
    E1: vEOS-DC1-1
    E2: vEOS-DC1-2
    E3: vEOS-DC1-3
    E4: vEOS-DC1-4

DC1-Spine-2:
    description: DC1-Spine2
    Ma1: Lab-vEOS
    E1: vEOS-DC1-21
    E2: vEOS-DC1-22
    E3: vEOS-DC1-23
    E4: vEOS-DC1-24

----------------------

Each above is a type value, where the first level is the name of the VM and switch
Next indented level are the interfaces. They are not case sensitive, but must follow
the Ma1 and E<number> structure. The value for each interface is the vSwitch name created.
A Port Group with the same name but with a -PG suffix will also be created and bound
to each switch.
'''
####################################################################
# REVISION LOG
####################################################################
# Version 1.0 - 2/25/2019 - J. Georges - Initial Release
#
####################################################################
#
from __future__ import print_function  # This import is for python2.*
import atexit
import requests
import ssl
import getpass

from pyvim import connect
from pyVmomi import vim
from pyVmomi import vmodl
import argparse
import yaml
import re



def build_arg_parser():
    parser = argparse.ArgumentParser(
        description='Standard Arguments for talking to vCenter for vEOS')
    parser.add_argument('-d', '--datastore',
                        required=True,
                        action='store',
                        help='Datastore name')
    parser.add_argument('-s', '--host',
                        required=True,
                        action='store',
                        help='esxi host to connect to')
    parser.add_argument('-u', '--user',
                        required=True,
                        action='store',
                        help='User name to use when connecting to host')
    parser.add_argument('-o', '--port',
                        type=int,
                        default=443,
                        action='store',
                        help='Port to connect on')
    parser.add_argument('-S', '--disable_ssl_verification',
                        required=False,
                        action='store_true',
                        help='Disable ssl host certificate verification')
    parser.add_argument('-l', '--local_file',
                        required=True,
                        action='store',
                        help='Local vEOS vmdk disk path to file to upload')
    parser.add_argument('-y', '--yaml_file',
                        required=True,
                        action='store',
                        help='Yaml file to parse')
    parser.add_argument('-p', '--password',
                        required=False,
                        action='store',
                        help='Password to use when connecting to host')
    args = parser.parse_args()

    return parser

def get_args():
    """
    Supports the command-line arguments needed to form a connection to vSphere.
    """
    parser = build_arg_parser()
    args = parser.parse_args()

    return prompt_for_password(args)

def prompt_for_password(args):
    """
    if no password is specified on the command line, prompt for it
    """
    if not args.password:
        args.password = getpass.getpass(
            prompt='Enter password for host %s and user %s: ' %
                   (args.host, args.user))
    return args


def get_obj(content, vimtype, name):
    """
    Return an object by name, if name is None the
    first found object is returned
    """
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtype, True)
    for c in container.view:
        if name:
            if c.name == name:
                obj = c
                return obj
        else:
            obj = c
            return obj

def vswitch_exists(host, vswitchtocheck):
    '''
    Check to see if the vswitch already exists or not
    '''
    vswitchlistobj=host.config.network.portgroup
    for switch in vswitchlistobj:
        if switch.spec.vswitchName == vswitchtocheck:
            return True
        else:
            continue
    return False


def create_vm(vmname, service_instance, vm_folder, resource_pool,datastore, switchintf):

    #datastore_path = '[' + datastore + '] ' + vm_name
    datastore_path = '[' + datastore + '] '
    # Note that if we just leave the datastore as the path, then it will
    # create in directory that has the vm name. In this case we want that
    # behavior.
    # bare minimum VM shell, no disks. Feel free to edit
    vmx_file = vim.vm.FileInfo(logDirectory=None,
                               snapshotDirectory=None,
                               suspendDirectory=None,
                               vmPathName=datastore_path)



    config = vim.vm.ConfigSpec(
                                name=vmname,
                                memoryMB=2048,
                                numCPUs=1,
                                files=vmx_file,
                                guestId='rhel6_64Guest',
                                version='vmx-07',)
                                #deviceChange=devices)




    print ("Creating VM {}...".format(vmname))
    task = vm_folder.CreateVM_Task(config=config, pool=resource_pool)
    wait_for_tasks(service_instance, [task])



    #Get server object
    servcontent = service_instance.RetrieveContent()
    vmobj = (get_obj(servcontent, [vim.VirtualMachine], vmname))

    #Now  reconfig this by adding a controller and disk.
    #We could have probably did this above when defining the VM;
    #But this gives us some flexibility for testing new config specs.
    spec = vim.vm.ConfigSpec()


    #Setup our disk that we copied over.
    dev_changes=[]
    disk_ctlr = vim.vm.device.VirtualDeviceSpec()
    disk_ctlr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    disk_ctlr.device = vim.vm.device.VirtualIDEController()
    disk_ctlr.device.deviceInfo = vim.Description()
    disk_ctlr.device.slotInfo = vim.vm.device.VirtualDevice.PciBusSlotInfo()
    disk_ctlr.device.slotInfo.pciSlotNumber = 16
    disk_ctlr.device.unitNumber = 1
    disk_ctlr.device.controllerKey = 200
    disk_ctlr.device.busNumber = 0
    dev_changes.append(disk_ctlr)

    #Since we starting out here...unit number should be 0
    unit_number = 0
    controller = disk_ctlr.device
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    #disk_spec.fileOperation = "create"
    #If we don't set fileOperation, it should just use existing file which is
    #what we want
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    disk_spec.device = vim.vm.device.VirtualDisk()
    disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()

    disk_spec.device.backing.diskMode = 'persistent'
    disk_spec.device.controllerKey = controller.key
    disk_spec.device.unitNumber = unit_number
    disk_spec.device.backing.fileName = '[%s] %s/vEOS-lab.vmdk' % ( datastore, vmname)
    dev_changes.append(disk_spec)

    spec.deviceChange = dev_changes
    task = vmobj.ReconfigVM_Task( spec=spec )
    wait_for_tasks(service_instance, [task])

    #We could have done this in one shot above with our NICs below. But I want it
    #separate so I can re-use the code for other use cases. Its keeps it a little more modular

    #Now lets get our interfaces configured
    content=service_instance.RetrieveContent()
    host=get_obj(content,[vim.HostSystem], None)
    spec = vim.vm.ConfigSpec()
    dev_changes=[]

    print ("Creating vSwitches and Portgroups for VM %s" % vmname)
    for interface in sorted(switchintf.keys()):
        #First, lets find the management interface
        #We'll use findall because I have no idea of case in the yaml
        #file. Not efficient, but this will work.
        if re.findall('ma1', interface,re.IGNORECASE):
            print ("vEOS Ma1 binding to %s " % switchintf[interface])
            #Check if its already configured or not
            if not vswitch_exists(host, switchintf[interface]):
                print ("vSwitch %s does not exist. Creating..." % switchintf[interface])
                AddHostSwitch(host, switchintf[interface])

            #For our Port Groups, we just add the suffix -PG and use this as the Standard
            #naming convention
            PGNAME=switchintf[interface]+'-PG'
            #Lets bind our nic.
            nic_spec = vim.vm.ConfigSpec()
            nic_spec = vim.vm.device.VirtualDeviceSpec()
            nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            nic_type = vim.vm.device.VirtualE1000()
            nic_spec.device = nic_type
            nic_spec.device.addressType = "generated"
            nic_spec.device.deviceInfo = vim.Description()
            nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            #We need both the name and object passed here...so get it
            nic_obj= get_obj(content,[vim.Network], PGNAME)
            nic_spec.device.backing.network = nic_obj
            nic_spec.device.backing.deviceName = nic_obj.name
            # portgroup is an object called net_name and we need to pass both the object
            #and its name to the NIC device
            nic_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            nic_spec.device.connectable.startConnected = True
            nic_spec.device.connectable.allowGuestControl = True
            dev_changes.append(nic_spec)
            break
    else:
        print ("No Management interface was specified. This will be an issue with this VM.")

    int_index=1
    for interface in sorted(switchintf.keys()):
        #Ma1 is first interface, so front panel interfaces are max'd out at 9.
        if int_index > 9:
            print ("ESXi only supports 10 interfaces per VM. Ignoring additional interfaces in yaml file.")
            break
        if re.findall('e[0-9]', interface,re.IGNORECASE):
            print ("vEOS Et%s binding to %s " % (str(int_index),switchintf[interface]))
            #Check if its already configured or not
            if not vswitch_exists(host, switchintf[interface]):
                print ("vSwitch %s does not exist. Creating..." % switchintf[interface])
                AddHostSwitch(host, switchintf[interface])
            else:
                print ("vSwitch %s exists. Using existing..." % switchintf[interface] )

            #For our Port Groups, we just add the suffix -PG and use this as the Standard
            #naming convention
            PGNAME=switchintf[interface]+'-PG'
            #Lets bind our nic.
            nic_spec = vim.vm.ConfigSpec()
            nic_spec = vim.vm.device.VirtualDeviceSpec()
            nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            nic_type = vim.vm.device.VirtualE1000()
            nic_spec.device = nic_type
            nic_spec.device.addressType = "generated"
            nic_spec.device.deviceInfo = vim.Description()
            nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            #We need both the name and object passed here...so get it
            nic_obj= get_obj(content,[vim.Network], PGNAME)
            nic_spec.device.backing.network = nic_obj
            nic_spec.device.backing.deviceName = nic_obj.name
            # portgroup is an object called net_name and we need to pass both the object
            #and its name to the NIC device
            nic_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            nic_spec.device.connectable.startConnected = True
            nic_spec.device.connectable.allowGuestControl = True
            dev_changes.append(nic_spec)

            #Increment our index so we know if we have too many interfaces...
            int_index += 1

    #NOW Apply new NIC specs
    spec.deviceChange = dev_changes
    task = vmobj.ReconfigVM_Task( spec=spec )
    wait_for_tasks(service_instance, [task])



def AddHostSwitch(host, vswitchName):
    vswitch_spec = vim.host.VirtualSwitch.Specification()
    vswitch_spec.numPorts = 32
    vswitch_spec.mtu = 9000

    #Set security policies. We need to be pretty open here for vEOS
    #Note remark out network_policy below because this is not working.
    #For the time being, we'll set it under the port group
    #https://github.com/vmware/pyvmomi-community-samples/issues/403
    #network_policy = vim.host.NetworkPolicy()
    #network_policy.security = vim.host.NetworkPolicy.SecurityPolicy()
    #network_policy.security.allowPromiscuous = True
    #network_policy.security.macChanges = True
    #network_policy.security.forgedTransmits = True

    #vswitch_spec.policy = network_policy

    host.configManager.networkSystem.AddVirtualSwitch(vswitchName,vswitch_spec)

    #Now create port group and add that to the vswitch we just created.

    portgroup_spec = vim.host.PortGroup.Specification()
    portgroup_spec.vswitchName = vswitchName
    portgroup_spec.name = vswitchName+'-PG'
    portgroup_spec.vlanId = int(4095)
    network_policy = vim.host.NetworkPolicy()
    network_policy.security = vim.host.NetworkPolicy.SecurityPolicy()
    network_policy.security.allowPromiscuous = True
    network_policy.security.macChanges = True
    network_policy.security.forgedTransmits = True
    portgroup_spec.policy = network_policy

    host.configManager.networkSystem.AddPortGroup(portgroup_spec)



#Function borrowed from pyvmomi-community-samples samples.tools
def wait_for_tasks(service_instance, tasks):
    """Given the service instance and tasks, it returns after all the
   tasks are complete.
   """
    property_collector = service_instance.content.propertyCollector
    task_list = [str(task) for task in tasks]
    # Create filter
    obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                 for task in tasks]
    property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                               pathSet=[],
                                                               all=True)
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = obj_specs
    filter_spec.propSet = [property_spec]
    pcfilter = property_collector.CreateFilter(filter_spec, True)
    try:
        version, state = None, None
        # Loop looking for updates till the state moves to a completed state.
        while len(task_list):
            update = property_collector.WaitForUpdates(version)
            for filter_set in update.filterSet:
                for obj_set in filter_set.objectSet:
                    task = obj_set.obj
                    for change in obj_set.changeSet:
                        if change.name == 'info':
                            state = change.val.state
                        elif change.name == 'info.state':
                            state = change.val
                        else:
                            continue

                        if not str(task) in task_list:
                            continue

                        if state == vim.TaskInfo.State.success:
                            # Remove task from taskList
                            task_list.remove(str(task))
                        elif state == vim.TaskInfo.State.error:
                            raise task.info.error
            # Move to next version
            version = update.version
    finally:
        if pcfilter:
            pcfilter.Destroy()

def GetVMHosts(content):
    host_view = content.viewManager.CreateContainerView(content.rootFolder,
                                                        [vim.HostSystem],
                                                        True)
    obj = [host for host in host_view.view]
    host_view.Destroy()
    return obj

def pushvmdk(si,datastorename,hostname,localfilename,verify_cert, vmname):
    print ("Uploading vmdk for %s..." % vmname)
    content = si.RetrieveContent()
    # Get the list of all datacenters we have available to us
    datacenters_object_view = content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.Datacenter],
        True)

    # Find the datastore and datacenter we are using
    datacenter = None
    datastore = None
    for dc in datacenters_object_view.view:
        datastores_object_view = content.viewManager.CreateContainerView(
            dc,
            [vim.Datastore],
            True)
        for ds in datastores_object_view.view:
            if ds.info.name == datastorename:
                datacenter = dc
                datastore = ds
    if not datacenter or not datastore:
        print("Could not find the datastore specified")
        raise SystemExit(-1)
    # Clean up the views now that we have what we need
    datastores_object_view.Destroy()
    datacenters_object_view.Destroy()
    # Build the url to put the file - https://hostname:port/resource?params

    #To keep things simple, we'll use the vmname as the folder and then
    #we'll force the vmdk file to vEOS-lab.vmdk
    resource = "/folder/" + vmname + "/vEOS-lab.vmdk"
    params = {"dsName": datastore.info.name,
              "dcPath": datacenter.name}
    http_url = "https://" + hostname + ":443" + resource

    # Get the cookie built from the current session
    client_cookie = si._stub.cookie
    # Break apart the cookie into it's component parts - This is more than
    # is needed, but a good example of how to break apart the cookie
    # anyways. The verbosity makes it clear what is happening.
    cookie_name = client_cookie.split("=", 1)[0]
    cookie_value = client_cookie.split("=", 1)[1].split(";", 1)[0]
    cookie_path = client_cookie.split("=", 1)[1].split(";", 1)[1].split(
        ";", 1)[0].lstrip()
    cookie_text = " " + cookie_value + "; $" + cookie_path
    # Make a cookie
    cookie = dict()
    cookie[cookie_name] = cookie_text

    # Get the request headers set up
    headers = {'Content-Type': 'application/octet-stream'}

    # Get the file to upload ready, extra protection by using with against
    # leaving open threads
    with open(localfilename, "rb") as f:
        # Connect and upload the file
        request = requests.put(http_url,
                               params=params,
                               data=f,
                               headers=headers,
                               cookies=cookie,
                               verify=verify_cert)




def main():
    args = get_args()

    try:
        service_instance = None
        sslContext = None
        verify_cert = None

        if args.disable_ssl_verification:
            sslContext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            sslContext.verify_mode = ssl.CERT_NONE
            verify_cert = False
            # disable urllib3 warnings
            if hasattr(requests.packages.urllib3, 'disable_warnings'):
                requests.packages.urllib3.disable_warnings()

        try:
            service_instance = connect.SmartConnect(host=args.host,
                                                    user=args.user,
                                                    pwd=args.password,
                                                    port=int(args.port),
                                                    sslContext=sslContext)
        except IOError as e:
            pass
        if not service_instance:
            print("Could not connect to the specified host using specified "
                  "username and password")
            raise SystemExit(-1)

        # Ensure that we cleanly disconnect in case our code dies
        atexit.register(connect.Disconnect, service_instance)

        content = service_instance.RetrieveContent()
        vmfolder = (get_obj(content, [vim.Folder], None))
        resource_pool = (get_obj(content, [vim.ResourcePool], None))

        with open(args.yaml_file, 'r') as fh:
            doc = yaml.load(fh)
        for switch in doc.keys():
            #Push VM, create VM and build/bind Port Groups to VM
            pushvmdk(service_instance, args.datastore,args.host,args.local_file,verify_cert,switch)

            #Pass doc[switch] which is a dictionary of interfaces for the vm
            create_vm(switch, service_instance, vmfolder, resource_pool, args.datastore, doc[switch])

        print ("vEOS-lab generation complete!")

    except vmodl.MethodFault as e:
        print("Caught vmodl fault : " + e.msg)
        raise SystemExit(-1)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
