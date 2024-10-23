"""dcnodatg module/script

Gathers and parses run-state details from a list of Arista
network switches.  Then creates a GNS3 virtual-lab project in which the
interrogated devices are emulated."""


import sys
from getpass import getpass
import pyeapi
import requests
from dcnodatg import gns3_worker, eos_poller

def read_file(file_to_read: str) -> list:
    """Open a file and return its contents as a list of strings

    Parameters
    ----------
    file_to_read : str
        The path of the file to be read
    """
    # Open the file in read mode
    opened_file = open(file_to_read, "r")
    # Each line of the file into an entry in a list called list_of_lines
    list_of_lines = opened_file.read().splitlines()
    # Close the file that was being read
    opened_file.close()
    return list_of_lines


def list_search(list_to_search: list, item_to_find: str) -> bool:
    """Search a list for a specified string

    Parameters
    ----------
    list_to_search : list
        The list to be searched
    item_to_find : str
        The item to search for
    """
    for val in list_to_search:
        if val == item_to_find:
            return True
    return False


def get_switch_data(switch: str, uname: str, passw: str) -> tuple[list, list, list]:
    """Connect to a switch and gets the data that we want from it

    Parameters
    ---------
    switch : str
        The network switch to be interrogated
    uname : str
        The username credential for authenticating to the switch
    passw : str
        The password credential for authenticating to the switch

    Returns
    -------
    this_sw_vals : list
        Values of the switch that we're interested in
    this_sw_lldp_nbrs : list
        The switch's LLDP neighbors table
    this_sw_cfg : list
        The switch's startup configuration
        """

    # Clear any existing pyeapi.client.config
    pyeapi.client.config.clear()
    # Build the pyeapi.client.config object required for connecting to the switch
    pyeapi.client.config.add_connection(switch, host=switch, transport='https',
                                        username=uname, password=passw)
    # Connect to the switch
    node = pyeapi.connect_to(switch)
    # Get JSON-formatted results of several 'show...' commands
    eos_output = node.enable(("show version", "show lldp neighbors",
                              "show lldp local-info"), format="json")
    # Pluck the specific bits out data we want from the "show" cmds' output
    eos_output_model = eos_output[0]["result"]["modelName"]
    eos_output_ver = eos_output[0]["result"]["version"]
    eos_output_mac = eos_output[0]["result"]["systemMacAddress"]
    eos_output_serial = eos_output[0]["result"]["serialNumber"]
    eos_output_lldpname = eos_output[2]["result"]["systemName"]
    # Create this_switch_data list to return (include empty indecesfor later)
    this_sw_vals = ([switch, eos_output_model, eos_output_ver, eos_output_mac,
                    eos_output_serial, eos_output_lldpname, '', '', '', '', '', ''])
    # Create this_sw_lldpnbrs list to return
    this_sw_lldpnbrs = []
    for value in eos_output[1]["result"]["lldpNeighbors"]:
        this_sw_lldpnbrs.append([str(eos_output_lldpname), str(value["port"]),
                                 str(value["neighborDevice"]),
                                 str(value["neighborPort"])])
    # Create this_sw_cfg list to return
    this_sw_cfg = []
    this_sw_cfg = node.startup_config.splitlines()
    # Return our results
    return (this_sw_vals, this_sw_lldpnbrs, this_sw_cfg)


def count_ether_interfaces(tmp_switch_config: list) -> int:
    """Accept a list of lines representing a switch config and return the number of
    Ethernet interfaces the corresponding cEOS container will need

    Parameters
    ---------
    tmp_switch_config : list
        List of lines of a switch's configuration

    Returns
    -------
    this_sw_intf_count : int
        The number of Ethernet interfaces the cEOS container version of the switch will\
         need
    """
    my_ethercount = 0
    for line in tmp_switch_config:
        # We're only counting single interfaces (not the breakout interfaces)
        if (line.startswith('interface Ethernet') and (not (line.endswith('/2') or
                                                            line.endswith('/3') or
                                                            line.endswith('/4')))):
            my_ethercount += 1
    return my_ethercount


def arista_ceos_sanitizer(sw_config_in: list, ether_count_in: int, system_mac_in:
                          str) -> list:
    """Accept a list of lines representing a switch config and return the number of
    Ethernet interfaces the corresponding cEOS container will need

    Parameters
    ---------
    sw_config_in : list
        List of lines of a switch's configuration
    invalid_starts : list
        List of strings the cEOS configs should NOT start with, and we will scrub
    ether_count_in : int
        The number of "Ethernet" interfaces in the original switch config
    system_mac_in : str
        The system MAC address of the original switch

    Returns
    -------
    sw_config_out : list
        Switch configuration (as a list of lines) that has been sanitized for cEOS
    """
    # List of global-config commands that we should comment out for cEOS compatibility
    # and lab environments in general
    badstarts = ['radius',
                 'username',
                 'aaa',
                 'ip radius',
                 'hardware speed',
                 'queue',
                 'server ',
                 'ip radius',
                 'ntp server',
                 'daemon TerminAttr',
                 '   exec /usr/bin/TerminAttr']

    # Replace all references to 'Management1' in the config with 'Ethernet__' (where
    #  __ is the switch's interface-count + 1)
    mgt_port_int = int(ether_count_in) + 1
    mgt_port_str = str(mgt_port_int)

    # Loop through the lines in each switch's configuration
    for linect, line in enumerate(sw_config_in):
        # Replace the Management1 interface name with an extra Ethernet interface
        sw_config_in[linect] = line.replace('Management1', 'Ethernet' + mgt_port_str)
        # Eiminate config lines the begin with any of the "invalid_starts"
        for oopsie in badstarts:
            if sw_config_in[linect].startswith(oopsie):
                # Can't just delete the un-wanted lines, that would screw up
                # the iteration through the list. Better to just prepend with a '!'
                sw_config_in[linect] = "!removed_for_cEOS-lab| " + sw_config_in[linect]
        # Get rid of '...netN/2|3|4' interface config sections altogether
        # (can't have them getting converted to ../netN and their vestigial config
        # overwriting the actual interface config
        spurious_interface = False
        # Loop through all of the switches
        # Check to see if the current config line is a 'spurious' interface
        spurious_interface = sw_config_in[linect].startswith(
            'interface Ethernet') and ('/2' in sw_config_in[linect] or '/3'
                                       in sw_config_in[linect] or '/4' in
                                       sw_config_in[linect])
        if spurious_interface:
            # Loop through the lines in the spurious interface's config section
            # and comment them out by prepending with '!'
            next_sec = False
            shortcount = linect
            # Stop commenting out lines when we get to the end of the config
            # section (marked by a line consisting of '!')
            next_sec = False
            while not next_sec:
                if sw_config_in[shortcount] == '!':
                    next_sec = True
                sw_config_in[shortcount] = '!' + sw_config_in[shortcount]
                shortcount += 1
        # Convert interface names from  '...netn/m' to '...netn'
        if sw_config_in[linect].startswith('interface Ethernet'):
            sw_config_in[linect] = sw_config_in[linect].split('/')[0]

    # Create an event-handler section to append to the configuration to
    # use the original switch's MAC address
    system_mac_config_snippet = ['', '', '', '', '', '', '']
    system_mac_config_snippet[0] = 'event-handler onStartup'
    system_mac_config_snippet[1] = ' trigger on-boot'
    system_mac_config_snippet[2] = ' action bash'
    system_mac_config_snippet[4] = '  echo $var_sysmac > /mnt/flash/system_mac_address'
    system_mac_config_snippet[5] = '  truncate -s -1 /mnt/flash/system_mac_address'
    system_mac_config_snippet[6] = '  EOF'
    # Remove the last line ('end') of the config  and append the system_mac_config
    # snippet(with the REAL switch's MAC address) before adding the final 'end' back
    # This will help our lab switches look more like the prod switches, but will
    # also work around the system-mac MLAG bug on cEOS
    poppedline = sw_config_in.pop(len(sw_config_in[linect])-1)
    system_mac_config_snippet[3] = '      var_sysmac=\'' + \
        system_mac_in + '\''
    for sysmacline in range(len(system_mac_config_snippet)):
        sw_config_in.append(system_mac_config_snippet[sysmacline])
        sw_config_in.append(poppedline)
    return sw_config_in


def p_to_v(**kwargs):
    """Pull switch run-state data, massage it, and turn it into a GNS3 lab

    Parameters
    ---------
    username : str
        The username to be used in authenticating eapi calls to the switches
    passwd : str
        The password to be used in authenticating eapi calls to the switches
    filename : str
        Name of the file containing the list of switches to be interrogated
    switchlist : list
        List object of names of switches to be interrogated.
    servername : str
        The name of the remote GNS3/Docker server
    prjname : str
        The name of the project to create on the GNS3 server

    Returns
    -------
    result : str
    """
    # Lists we'll use later
    # List that we'll use to store the switch's vital statistics for modeling later
    # switch_vals[n][0]= switch name received as input argument
    # switch_vals[n][1]= switch model
    # switch_vals[n][2]= EOS version
    # switch_vals[n][3]= system MAC
    # switch_vals[n][4]= serial number
    # switch_vals[n][5]= LLDP system-name
    # switch_vals[n][6]= Number of Ethernet interfaces
    # switch_vals[n][7]= GNS3 image-template ID
    # switch_vals[n][8]= GNS3 node-ID
    # switch_vals[n][9]= Docker container ID
    # List of LLDP neighbor details we'll use to build a list of connections for GNS3
    connections_to_make = []
    # Nested list for holding the configs of ALL the switches
    allconfigs = []
    # A list for holding a list of gns3 template_id values and corresponding EOS \
    # version values
    image_map = []
    # Set default values for all anticipated arguments
    filename = ''
    username = ''
    passwd = ''
    switchlist = []
    servername = ''
    prj_name = ''
    run_type = 'module'
    # Pull any expected (and received) arguments from kwargs into their recipient
    # objects
    if 'filename' in kwargs:
        filename = kwargs['filename']
    if 'username' in kwargs:
        username = kwargs['username']
    if 'passwd' in kwargs:
        passwd = kwargs['passwd']
    if 'switchlist' in kwargs:
        switchlist = kwargs['switchlist']
    if 'servername' in kwargs:
        servername = kwargs['servername']
    if 'prjname' in kwargs:
        prj_name = kwargs['prjname']
    if 'runtype' in kwargs:
        run_type = kwargs['runtype']
    if (filename == '' and switchlist == []):
        print("Enter a switch name and press enter.")
        print("(Press Enter without entering a name when done.")
        while True:
            line = input()
            if not line:
                break
            switchlist.append(line)
    if (filename != '') and (switchlist != []):
        print("Don't pass both filename_arg AND switchlist_arg; choose one or the \
other.")
        exit(1)
    if prj_name == '':
        prj_name = input('Enter a value to use for the GNS project name when modeling \
the production switches: ')
    if servername == '':
        servername = input('Enter the name of the GNS3 server: ')
    # Read the input switch-list file, if a filename was provided
    if filename != '':
        switchlist = read_file(filename)

    # Remove any blank entries from switchlist
    switchlist = list(filter(None, switchlist))
    # Prompt for switch/EOS credentials if none were provided
    if username == '':
        username = input('Enter username for Arista EOS login: ')
    if passwd == '':
        passwd = getpass('Enter password for Arista EOS login: ')

    # Call eos_poller.invoker to poll the Arista switches
    switch_vals, connections_to_make, allconfigs = eos_poller.invoker(switchlist,
                                                                      username,
                                                                      passwd, run_type)
    # Get the number of ethernet interfaces from each switch's config and store for l8r
    for i, val in enumerate(switchlist):
        ether_count = count_ether_interfaces(allconfigs[i])
        switch_vals[i][6] = ether_count

    # Loop through all those configs and clean them up for life as a cEOS container
    for i, val in enumerate(allconfigs):
        allconfigs[i] = arista_ceos_sanitizer(val, switch_vals[i][6], switch_vals[i][3])
    # Create a list of the LLDP local-IDs used by our switches
    our_lldp_ids = []
    for val in switch_vals:
        our_lldp_ids.append(val[5])

    # Sanitize connections_to_make list; removing any entries in which either end
    # is NOT one of our switches  (we can't tell GNS3 to create a connection to a
    # node that doesn't exist in the project.)
    connections_to_make[:] = [connx for connx in connections_to_make if
                              list_search(our_lldp_ids, connx[0]) and
                              list_search(our_lldp_ids, connx[2])]

    # Remove A|B-inverted entries in connections_to_make
    # (connections are directionless; so A<>B is the same as B<>A)
    for i in connections_to_make:
        for j in connections_to_make:
            if i[2]+i[3] == j[0]+j[1]:
                connections_to_make.remove(j)

    # Clean up "management1" in the connections_to_make list (using the highest
    # available ethernet interface instead (we added an extra interface to each
    # node when we created it and later in the allconfigs table)

    for i, val in enumerate(connections_to_make):
        # connections_to_make[i][0] = val[0].lower()
        connections_to_make[i][1] = val[1].lower()
        # connections_to_make[i][2] = val[2].lower()
        connections_to_make[i][3] = val[3].lower()
        if val[1] == 'management1':
            for j, val2 in enumerate(switch_vals):
                if val[0] == val2[5]:
                    connections_to_make[i][1] = 'ethernet' + str(int(val2[6]) + 1)
        if val[3] == 'management1':
            for j, val2 in enumerate(switch_vals):
                if val[2] == val2[5]:
                    connections_to_make[i][3] = 'ethernet' + str(int(val2[6]) + 1)

    # Set GNS3 URL
    gns3_url = 'http://'+servername+':3080/v2/'
    gns3_url_noapi = 'http://'+servername+':3080/static/web-ui/server/1/project/'

    # Get all of the docker image templates from the GNS3 server so we can figure out
    # which template_id value maps to a specific EOS version when we start building
    # our instances
    r = requests.get(gns3_url + 'templates', timeout=10)
    for x in r.json():
        if x['template_type'] == 'docker':
            image_map.append([x['template_id'], x['image']])

    # Loop through image_map while looping through switch_vals, looking for imag_map
    # names that are good matches for the EOS version data captured in switch_vals,
    #  and appending each entry in switch_status with the GNS3 template_id from the
    #  matching entry in image_map
    for i in range(len(switch_vals)):
        for j in range(len(image_map)):
            fudgedupeosverion = 'ceos:' + switch_vals[i][2].lower()
            if fudgedupeosverion == image_map[j][1].lower():
                switch_vals[i][7] = image_map[j][0]
    # create a new project with provided name and grab the project_id
    gnsprj_id = requests.post(gns3_url + 'projects', json={'name': prj_name},
                              timeout=10).json()['project_id']
    # Grab the templates object from the GNS server so we can crawl through it
    # templ_qry_resp = requests.get(gns3_url + 'templates')

    # Invoke function that handles node creation/configuration in GNS3 project
    gns3_worker.invoker(servername, gns3_url, switch_vals,
                        allconfigs, gnsprj_id, connections_to_make)
    # Done!

    # Close the GNS3 project
    gnsprj_close = requests.post(gns3_url + 'projects' + 'project_id' + 'close')
    
    return gns3_url_noapi + gnsprj_id


if __name__ == '__main__':
    kwdict = {}
    for arg in sys.argv[1:]:
        splarg = arg.split('=')
        if splarg[0] == 'switchlist':
            splargalt = []
            for swname in splarg[1].split():
                splargalt.append(swname)
            kwdict[splarg[0]] = splargalt
        else:
            kwdict[splarg[0]] = splarg[1]
    kwdict['runtype'] = 'script'
    import dcnodatg.gns3_worker
    import dcnodatg.eos_poller
    p_to_v(**kwdict)
