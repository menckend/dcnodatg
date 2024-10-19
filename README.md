# Preamble

I wrote this package (dcnodatg) specifically to assist in *fast/low-effort* modeling of a production EVPN Layer-3 Leaf & Spine physical network of Arista switches in a pre-existing GNS3 server, using Arista cEOS docker images.  (Also, to teach myself how to write/publish Python packages, but *really* for modeling Arista switches.)

- Documentation at: [https://menckend.github.io/dcnodatg/](https://menckend.github.io/dcnodatg/)
- Repository at: [https://github.com/menckend/dcnodatg](https://github.com/menckend/dcnodatg)
- (Latest) Package at: [https://pypi.org/project/dcnodatg/](https://pypi.org/project/dcnodatg/)
- (testing) Package at: [https://test.pypi.org/project/dcnodatg/](https://test.pypi.org/project/dcnodatg/)

## What it does

- Grabs startup configuration, version info, and lldp neighbor information from a list of Arista switches
- Uses Arista eAPI (credentials must be provided as arguments) to retrieve all data
- Sanitizes the switch configs for use in a cEOS environment
  - Removes all AAA and username configuration
  - Reformats interface names to match the cEOS interface naming convention  Ethernet_n , not Ethernt_n/1
  - Comments out incompatible commands ("queue..." not supported on cEOS)
  - Configures the system mac-address of the production switch
    - Increase verisimilitude with prod device that is being modeled
    - Avoids mLAG incompatibility with cEOS
      - Docker container default mac address has U/L bit set to L instead of U, which prevents MLAG from working
- Builds a table of interconnections between the switches
  - Inferred from the "show lldp neighbor" and "show lldp local" output
- Creates a GNS3 project
  - Instantiates a cEOS container node in the project for each switch in the input list
  - Modeled devices mirror the following properties of the switches they are modeling:
    -  cEOS version (a pre-existing GNS3 docker template using the matching cEOS version must be present) 
    -  Ethernet interface count
    -  system-mac-address
    -  Startup configuration
       -  "startup-config" is pushed from the dcnodatg package directly to the containerd service on the GNS3 server
          -  Avoiding the need for dcnodatg to run *on* the gns3 server
  - Creates the connections between the GNS3/cEOS nodes, mirroring all inter-switch connections discovered in LLDP tables

## What you'll need

### Python

- The dcnodatg project was written using Python 3.12.
  - I haven't tested it with any other versions.
- The host running the dcnodatg packages will need to have Python and the packages listed in the dependencies section of pyproject.toml installed
- Once Python is installed, use pip to install either the test or "stable" version of dcnodatg (which will install its dependencies as well):
  - For the test version:
    - 'pip install -i https://test.pypi.org/simple/ --no-cache --user --extra-index-url https://pypi.org/simple dcnodatg'
  - For the "real" version:
    -  'pip install --user dcnodatg'

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

- Have Python and the dcnodatg package installed on the host that will run dcnodatg
- Have your login credentials for your production switches handy
- Make sure that your production switches can receive eAPI connections from your GNS3 server
- Optionally, create a file named "input-switch-list"
  -   - Populate 'input-switch-list' with the names of the switches that you want to model in gns3
      -   One switch name per line (no quotes or commas)

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

Installing dcnodatg via pip will save you the effor of installing the additional dependencies list in pyproject.toml, but you can also just grab the contents of the dcnodatg folder [directly from the git repository](https://github.com/menckend/dcnodatg/tree/main/dcnodatg) and store them on the host you'll run them from.

You'll also need to move the "dcnod-cli.py" file *up* one level in the directory structure from the dcnodatg folder after copying the entire folder to your host.  This is to work around "goofiness" with regards to how Python treats namespaces when accessing Python code as a "script" vs accessing it "as a module."

To actually run the utility, you'll enter the following command:

```
python [path-to]dcnod-cli.py'
```

##### To run interactively

Enter:

```bash
python [path-to]dcnod-cli.py'
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
python [path-to]dcnod-cli.py [arguments]
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
switchlist= 'sw1.menckend.com sw2 sw3 sw4.menckend.com'
filename= './switchlist.txt'
prjname= 'dcnodatg-project-dujour'
```

Remember that the switchlist and filename arguments are mutually exclusive, if you pass *both*, dcnodatg will exit.

An example of a fully-argumented invocation would be:

```bash
python ./dcnodatg.py username='fakeid' passwd='b@dp@ssw0rd' servername='gn3server.com' prjname='giveitanme' switchlist='switch1 switch2 switch3'
```

##### As a Python module

Install dcnodatg with pip as described above and include an import statement ('import dcnodatg') in your python module. E.g.

```python
from dcnodatg import dcnodatg

sn='gns3server.bibbity.bobbity.boo'
un='myuserid'
pw='weakpassword'
prjn='new-gns3-project-today'
sl=['switch1.internal', 'switch15.internal', 'switch1.menckend.com']

dcnodatg.p_to_v(username=sn, passwd=pw, servername=sn, switchlist=sl, prjname=prjn)
```

> [!IMPORTANT]  
> The 'switchlist' parameter, when dcnodatg is being accessed as a module is a dict structure, and the formatting in the example above is mandatory when specifying the switchlist data as a kwarg.
