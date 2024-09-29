# Preamble

I wrote this specifically to assist in *fast* modeling of a production EVPN Layer-3 Leaf & Spine physical network of Arista switches in a pre-existing GNS3 server, using Arista cEOS docker images.

Documentation at: [https://menckend.github.io/dcnodatg/](https://menckend.github.io/dcnodatg/)

Repository at: [https://github.com/menckend/dcnodatg](https://github.com/menckend/dcnodatg)

## What it does

- Grabs startup configuration, version info, and lldp neighbor information from a list of Arista switches
- Uses Arista eAPI (credentials must be provided as arguments when running dcnodatg) to retrieve all data
- Sanitizes the switch configs for use in a cEOS environment
  - Removes all AAA and username configuration
  - Reformats interface names to match the cEOS interface naming convention  Ethernet_n , not Ethernt_n/1
  - Comments out incompatible commands ("queue..." not supported on cEOS)
  - Configures a matching system mac-address to
    - Increase verisimilitude with prod device that is being modeled
    - Avoid mLAG incompatibility with cEOS
      - Docker container default mac address has U/L bit set to L instead of U
- Builds a table of interconnections between the switches
  - From the lldp neighbor and startup config data
- Creates a GNS3 project
  - Creates models of all of the switches from it processed
  - Modeled devices matches cEOS versioning, interface count, and system-mac-address
- Creates the interconnects between all of the cEOS switches in the previous step
- Pushes the startup-config of the production switch into /mnt/flash/startup-config of the virtual-switch
  - Uses the docker client API's put_archive method to put the startup-config file in the container's root directory
    - It's only possible to send to the "/" path for some reason.
  - Uses the GNS API to start the node/container (which ensures that the /mnt/flash volume is mounted)
  - Uses the docker client API's exec_create method to run the command:  "mv /startup-config /mnt/flash/startup-config"

## Requirements

### Python

- The dcnodatg module was written using Python 3.12.  I haven't tested it with any other versions.
- The host running the dcnodat module will need the pyeapi and docker python packages installed
  - 'pip install pyeapi'
  - 'pip install docker'

If you want to invoke dcnodatg programmatically as a python module, install it with pip:

- 'pip install dcnodatg'

And import it into your python project:

- 'import dcnodatg'

### GNS3 server

- The dcnodatg module was written against version 2.2.18 of GNS3 server.
- The GNS3 server must be pre-configured with cEOS docker templates
  - dcnodatg will compare the EOS version string on the switches you tell it to process to the tags of the docker-images on the GNS3 server
    - The docker images need to be named as "ceos:*n.n...*" for the matching to work
- The containerd service must be listening on TCP port 2375 of the GNS3 server

### Arista Switches

All switches that you will be modeling will need to have:

- EAPI services accessible from the host running the dcnodatg module
  - And you will need to provide auth. credentials with sufficient privileges to invoke the following methods:
    - node.enable(("show version", "show lldp neighbors", "show lldp local-info"), format="json")
    - node.startup_config.splitlines()

### Instructions

### Prep

- Put a copy of  dcnodatg.py where your Python interpreter can get at it
- Have your login credentials for your production switches handy
- Make sure that your production switches can receive eAPI connections from your GNS3 server
- Optionally, create a file named "input-switch-list" in the same directory that you installed the .py files
  - Populate 'input-switch-list' with the names of the switches that you want to model in gns3

### Parameter/argument list

dcnodatg uses the following arguments (passed as keyword pairs):

- filename *or* switchlist
  - No default value
  - If *both* arguments are provided, dcnodatg will exit.
  - If *no* argument is provided, dcnodatg will try use the input function to prompt for switch names
  - "filename" is (path and) name of the file containing the list of switches to process
    - One switch-name (FQDN or resolvable short-name) per line in the file
    - E.G.:  ./switch-list.txt
  - "switchlist" is a python list of switch-names
    - E.g.:  ["name1", "name2", "nameN"]
- servername
  - No default value
  - The name (FQDN or resolvable short-name) of the GNS3 server
  - If not provided, dcnodatg will try to use the input function to prompt for a value
  - E.g.:  gns3server.whathwere.there
- username
  - No default value
  - The username dcnodatg will provide to the switches when authenticating the eapi connections
  - If not provided, dcnodatg will try to use the input function to prompt for a value
- passwd
  - No default value
  - The password dcnodatg will provide to the switches when authenticating the eapi connections
  - If not provided, dcnodatg will try to use the input function to prompt for a value
- prjname
  - No default value
  - The name to assign to the new project that dcnodatg will create on the GNS3 server

### Execution

#### As a Python script

##### To run interactively

Enter:

```bash
python [path-to]/dcnodatg.py
```

As dcnodatg executes, you will be prompted to respond with values for all of the parameters/arguments. No quotes or delimiters should be required as you enter the values.

- The FQDNs of the switches you want to process
  - Type a switch-name and press Enter
  - Repeat until you've entered all the switches you want to model
  - Then press Enter again
- The name of the GNS3 project to create
  - Type a project name (adhere to whatever GNS3's project-naming semantics) and press enter
- The EOS username to use when querying the switches
  - Type the name and press enter
- The EOS password to use when querying the switches
  - The getpass function is used, obscuring the password on-screen as you type it
  - The password itself isn't written to any file
  - Type the password and press Enter
- The FQDN of the GNS3 server you'll be using

##### To run non-interactively

Enter:  

```python
python [path-to]/dcnodatg.py [arguments]
```

The arguments are keyword/value pairs, in the form of:

```python
keyword='value'
```

The arguments can be entered in any order, separate by a space.  Examples of each argument follow:

```text
username= 'mynameismud'
passwd= 'mypasswordisalsomud'
servername= 'gns3server.menckend.com'
switchlist= 'sw1.menckend.com sw2.menckend.com sw3.menckend.com'
filename= './switchlist.txt'
prjname= 'dcnodatg-project-dujour'
```

Remember that the switchlist and filename arguments are mutually exclusive, if you include both, dcnodatg will exit.

An example of a fully-argumented invocation would be:

```bash
python ./dcnodatg.py username='fakeid' passwd='b@dp@ssw0rd' servername='gn3server.com' prjname='giveitanme' switchlist='switch1 switch2 switch3'
```

##### As a Python module

Install dcnodatg with pip  ('pip install dcnodatg') and include an import statement ('import dcnodatg') in your python module. E.g.

```python
import dcnodatg

sn='gns3server.bibbity.bobbity.boo'
un='myuserid'
pw='weakpassword'
prjn='new-gns3-project-today'
sl=['switch1.internal', 'switch15.internal', 'switch1.menckend.com']

dcnodatg.main(username=sn, passwd=pw, servername=sn, switchlist=sl, prjname=prjn)
```
