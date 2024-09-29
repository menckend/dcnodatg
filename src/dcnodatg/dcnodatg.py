import sys
import tarfile
from getpass import getpass
from io import BytesIO, StringIO

import docker
import pyeapi
import requests

"""dcnodatg module/script

This script gathers and parses run-state details from a list of Arista
network switches.  It then creates a GNS3 virtual-lab project in which the
interrogated devices are emulated."""


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
    for i in range(len(list_to_search)):
        if list_to_search[i] == item_to_find:
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
    eos_output_lldpName = eos_output[2]["result"]["systemName"]
    # Create this_switch_data list to return
    this_sw_vals = ([switch, eos_output_model, eos_output_ver, eos_output_mac,
                    eos_output_serial, eos_output_lldpName])
    # Create this_sw_lldpnbrs list to return
    this_sw_lldpnbrs = []
    for count, value in enumerate(eos_output[1]["result"]["lldpNeighbors"]):
        this_sw_lldpnbrs.append([str(eos_output_lldpName), str(value["port"]),
                                 str(value["neighborDevice"]),
                                 str(value["neighborPort"])])
    # Create this_sw_cfg list to return
    this_sw_cfg = []
    this_sw_cfg = (node.startup_config.splitlines())
    # Return our results
    return (this_sw_vals, this_sw_lldpnbrs, this_sw_cfg)


def count_ether_interfaces(tmp_switch_config: list) -> int:
    """Accept a list of lines representing a switch config and return the number of Ethernet interfaces the corresponding cEOS container will need

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
    return (my_ethercount)


def main(**kwargs):
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
    switch_vals = []

    # List of LLDP neighbor details we'll use to build a list of connections for GNS3
    connections_to_make = []
    # Nested list for holding the configs of ALL the switches
    allconfigs = []

    # A list of patterns for the beginning of configuration lines that we'll comment \
    # out for cEOS compatibility)
    badstarts = []

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
        print(switchlist)
        for switch in switchlist:
            print(switch)
        exit
    if 'servername' in kwargs:
        servername = kwargs['servername']
    if 'prjname' in kwargs:
        prj_name = kwargs['prjname']
    if (filename == '' and switchlist == []):
        print("You didn't specify a filename or pass a list of switches.  So...")
        print("Enter a switch name and press enter.")
        print("(Press Enter without entering a name when done.")
        while True:
            line = input()
            if not line:
                break
            switchlist.append(line)
    if (not filename == '') and (not switchlist == ''):
        print("Don't pass both filename_arg AND switchlist_arg; choose one or the \
other.")
        exit(1)
    if prj_name == '':
        prj_name = input('Enter a value to use for the GNS project name when modeling \
the production switches: ')
    if servername == '':
        servername = input('Enter the name of the GNS3 server: ')
    # Read the input switch-list file, if a filename was provided
    if not filename == '':
        switchlist = read_file(filename)

    # Remove any blank entries from switchlist
    switchlist = list(filter(None, switchlist))

    # Prompt for switch/EOS credentials if none were provided
    if username == '':
        username = input('Enter username for Arista EOS login: ')
    if passwd == '':
        passwd = getpass('Enter password for Arista EOS login: ')

    # Loop through all of the switches we've been asked to process and GET their data
    switchcount = str(len(switchlist))
    print("Connecting to switches to grab config, EOS version, and lldp details:")
    c = 1
    for s in switchlist:
        # Print progress/status message
        print("   Switch  ",  c,  " of ", switchcount, "(", s, ")", end="\n")
        c += 1
        # Get the switch's data
        that_sw_vals, that_sw_lldpnbrs, that_sw_cfg = get_switch_data(s, username,
                                                                      passwd)
        # Push switch's data into the list of all switches' data
        switch_vals.append(that_sw_vals)
        allconfigs.append(that_sw_cfg)
        for that_lldp_nbr in that_sw_lldpnbrs:
            connections_to_make.append(that_lldp_nbr)

    # Get the number of ethernet interfaces from each switch's config and store for l8r
    for switchct in range(len(switchlist)):
        ether_count = count_ether_interfaces(allconfigs[switchct])
        switch_vals[switchct].append(ether_count)

    # Loop through all those configs and clean them up

    # List of global-config commands that we should comment out for cEOS compatibility
    # and lab environments in general
    badstarts = ['radius', 'username', 'aaa', 'ip radius', 'hardware speed', 'queue',
                 'server 10.207.200.82', 'ip radius', 'ntp server',
                 'daemon TerminAttr', '   exec /usr/bin/TerminAttr']

    # get rid of commands we don't want in the EOS configs for the cEOS lab
    for switchct in range(len(switchlist)):
        for linect in range(len(allconfigs[switchct])):
            for oopsie in badstarts:
                if allconfigs[switchct][linect].startswith(oopsie):
                    # Can't just delete the un-wanted lines, that would screw up
                    # the iteration through the list. Better to just prepend with a '!'
                    allconfigs[switchct][linect] = "!removed_for_cEOS-lab| " + \
                        allconfigs[switchct][linect]

    # Get rid of '...netN/2|3|4' interface config sections altogether
    # (can't have them getting converted to ../netN and their vestigial config
    # overwriting the actual interface config
    spurious_interface = False
    # Loop through all of the switches
    for switchct in range(len(switchlist)):
        # Loop through the lines in each switch's configuration
        for linect in range(len(allconfigs[switchct])):
            # Check to see if the current config line is a 'spurious' interface
            spurious_interface = (allconfigs[switchct][linect].startswith(
                'interface Ethernet') and ('/2' in allconfigs[switchct][linect] or '/3'
                                           in allconfigs[switchct][linect] or '/4' in
                                           allconfigs[switchct][linect]))
            if spurious_interface:
                # Loop through the lines in the spurious interface's config section
                # and comment them out by prepending with '!'
                next_sec = False
                shortcount = linect
                # Stop commenting out lines when we get to the end of the config
                # section (marked by a line consisting of '!')
                next_sec = False
                while not next_sec:
                    if allconfigs[switchct][shortcount] == '!':
                        next_sec = True
                    allconfigs[switchct][shortcount] = '!' + allconfigs[switchct][shortcount]
                    shortcount += 1

    # Convert interface names from  '...netn/m' to '...netn'
    for switchct in range(len(switchlist)):
        for linect in range(len(allconfigs[switchct])):
            if allconfigs[switchct][linect].startswith('interface Ethernet'):
                allconfigs[switchct][linect] = allconfigs[switchct][linect].split('/')[0]

    # Replace all references to 'Management1' in the config with 'Ethernet__' (where
    #  __ is the switch's interface-count + 1)
    # Loop through all of the switches
    mgt_port = int(0)
    mgt_port_str = '0'

    for switchct in range(len(switchlist)):
        # Look up the port-count for this switch
        port_count = int(switch_vals[switchct][6])
        mgt_port = port_count + 1
        mgt_port_str = str(mgt_port)
        # Loop through the lines in each switch's configuration
        for linect in range(len(allconfigs[switchct])):
            # Do string substition with the assigned mgmt port number for this device
            allconfigs[switchct][linect] = allconfigs[switchct][linect].replace(
                'Management1', 'Ethernet' + mgt_port_str)

    # Add a new section to the end of each switch's configuration to
    # emulate the system mac address of the production device  (required for MLAG
    # functionality due to docker container default mac address have U/L bit set to L.)

    # Creating list for system mac config snippet
    system_mac_config_snippet = ['', '', '', '', '', '', '']
    system_mac_config_snippet[0] = 'event-handler onStartup'
    system_mac_config_snippet[1] = ' trigger on-boot'
    system_mac_config_snippet[2] = ' action bash'
    system_mac_config_snippet[4] = '  echo $var_sysmac > /mnt/flash/system_mac_address'
    system_mac_config_snippet[5] = '  truncate -s -1 /mnt/flash/system_mac_address'
    system_mac_config_snippet[6] = '  EOF'

    # Loop through each switch's config in allconfigs
    # Removing the last line ('end') and appending the system_mac_config snippet
    # (with the REAL switch's MAC address) before adding the final 'end' back
    # This will help our lab switches look more like the prod switches, but will
    # also work around the system-mac MLAG bug on cEOS
    for config in range(len(allconfigs)):
        poppedline = allconfigs[config].pop(len(allconfigs[config])-1)
        system_mac_config_snippet[3] = '      var_sysmac=\'' + \
            switch_vals[config][3] + '\''
        for sysmacline in range(len(system_mac_config_snippet)):
            allconfigs[config].append(system_mac_config_snippet[sysmacline])
            allconfigs[config].append(poppedline)

    # Create a list of the LLDP local-IDs used by our switches
    our_lldp_ids = []
    for sw_cnt in range(len(switch_vals)):
        our_lldp_ids.append(switch_vals[sw_cnt][5])

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
    for cn_cnt in range(len(connections_to_make)):
        connections_to_make[cn_cnt][1] = connections_to_make[cn_cnt][1].lower()
        connections_to_make[cn_cnt][3] = connections_to_make[cn_cnt][3].lower()
        if connections_to_make[cn_cnt][1] == 'management1':
            for sw_cnt in range(len(switch_vals)):
                if connections_to_make[cn_cnt][0] == switch_vals[sw_cnt][5]:
                    connections_to_make[cn_cnt][1] = 'ethernet' + str(
                        int(switch_vals[sw_cnt][6]) + 1)
        if connections_to_make[cn_cnt][3] == 'management1':
            for switch in range(len(switch_vals)):
                if connections_to_make[cn_cnt][2] == switch_vals[sw_cnt][5]:
                    connections_to_make[cn_cnt][3] = 'ethernet' + str(
                        int(switch_vals[sw_cnt][6]) + 1)

    # Set GNS3 URL
    gns3_url = 'http://'+servername+':3080/v2/'

    # Get all of the docker image templates from the GNS3 server so we can figure out
    # which template_id value maps to a specific EOS version when we start building
    # our instances
    r = requests.get(gns3_url + 'templates')
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
                switch_vals[i].append(image_map[j][0])

    # create a new project with provided name
    gnsprj_response = requests.post(gns3_url + 'projects', json={'name': prj_name})
    # Grab the templates object from the GNS server so we can crawl through it
    templ_qry_response = requests.get(gns3_url + 'templates')

    # Set x/y coordinates for the first node on the project
    nodex = -900
    nodey = -420

    # Loop through switch_vals and create cEOS nodes in the GNS3 project for each
    c = 1
    print('')
    print("Instantiating cEOS switches in your new GNS project:")
    for linecount in range(len(switch_vals)):
        tmpl_idx = 0
        for tpls in range(len(templ_qry_response.json())):
            if templ_qry_response.json()[tpls]['template_id'] == \
             switch_vals[linecount][7]:
                tmpl_idx = tpls
        tmpl_ifcount = int(switch_vals[linecount][6]) + 2
        templ_chgifcnt_response = requests.put(gns3_url + 'templates/' + switch_vals[1]
                                               [7], json={'adapters': tmpl_ifcount})
        newnodeoutput = requests.post(gns3_url + 'projects' + '/' + gnsprj_response
                                      .json()['project_id'] + '/templates/' +
                                      templ_qry_response.json()[tmpl_idx]
                                      ['template_id'], json={'x': nodex, 'y': nodey})
        switch_vals[linecount].append(newnodeoutput.json()['node_id'])
        switch_vals[linecount].append(newnodeoutput.json()['properties']
                                      ['container_id'])
        node_chg_name_response = requests.put(gns3_url + 'projects' + '/' +
                                              gnsprj_response.json()['project_id'] +
                                              '/nodes/' + newnodeoutput.json()
                                              ['node_id'], json={'name': switch_vals
                                                                 [linecount][0].split
                                                                 ('.')[0]})
        nodex += 120
        if nodex > 500:
            nodex = -900
            nodey = nodey + 120
        print("   Switch  ",  c,  " of ", switchcount, "(", switch_vals[linecount]
              [0], ")", end="\r")
        c += 1
    print('')

    # Loop through connections_to_make and make the connections between switches
    print("Instantiating the connections between switches in the GNS3 project (might \
           take a minute):")
    c = 1
    for cn_cnt in range(len(connections_to_make)):
        a_node_id = []
        b_node_id = []

        for switch_nbr in range(len(switch_vals)):
            if connections_to_make[cn_cnt][0] == switch_vals[switch_nbr][5]:
                a_node_id = switch_vals[switch_nbr][8]
            if connections_to_make[cn_cnt][2] == switch_vals[switch_nbr][5]:
                b_node_id = switch_vals[switch_nbr][8]
        a_node_adapter_nbr = int(connections_to_make[cn_cnt][1].split('/')[0].split
                                 ('ethernet')[1])
        b_node_adapter_nbr = int(connections_to_make[cn_cnt][3].split('/')[0].split
                                 ('ethernet')[1])
        cnx_crt_rspns = requests.post(gns3_url + 'projects/' + gnsprj_response.json()
                                      ['project_id'] + '/links', json={"nodes":
                                      [{"adapter_number": a_node_adapter_nbr, "node_id":
                                       a_node_id, "port_number":
                                       0}, {"adapter_number": b_node_adapter_nbr,
                                       "node_id": b_node_id, "port_number": 0}]})
        print("   Connection  ",  c,  " of ", len(connections_to_make), end="\r")
        c += 1

    # print('Refreshing  the docker container-UIDs of each virtual switch in our project.\
    # They were re-spawned with new IDs when we changed interface counts, etc..')
    for sw_c in range(len(switch_vals)):
        qnodersp = requests.get(gns3_url + 'projects/' + gnsprj_response.json()
                                ['project_id'] + '/nodes/' + switch_vals[sw_c][8])
        crntdockerid = qnodersp.json()['properties']['container_id']
        switch_vals[sw_c][9] = crntdockerid
    print('')

    print('Now we will push the config files directly into the respective docker \
    containers via API calls directly to the docker engine.')
    print('')

    # Create docker client (RESTful API, not low-level API)
    d_clnt = docker.DockerClient(base_url='tcp://'+servername+':2375')

    # Do the work for every switch we processed
    my_string_to_go = ''
    for sw_c in range(len(switch_vals)):

        print("   Switch  ",  sw_c + 1,  " of ", switchcount, "(", s, ")", end="\r")

        # Tell GNS3 to start the node that represents the current switch
        # using GNS3 API so the persistent volumes get mounted when the container is run
        gnsrsp = requests.post(gns3_url + 'projects/' + gnsprj_response.json()
                               ['project_id']+'/nodes/' + switch_vals[sw_c][8] +
                               '/start')

        # Rebuild the switch-config (allconfigs[sw_c]) from its current state as a
        # list of individual lines to a single string with newline characters.
        my_string_to_go = ''
        for i in allconfigs[sw_c]:
            my_string_to_go = my_string_to_go + i + "\n"
        ascii_to_go = my_string_to_go.encode('ascii')
        bytes_to_go = BytesIO(ascii_to_go)
        file_like_to_go = StringIO(my_string_to_go)

        # Turn the switch-config string into a tar archive for later
        fh = BytesIO()
        with tarfile.open(fileobj=fh, mode='w') as tarch:
            info = tarfile.TarInfo('startup-config')
            info.size = len(my_string_to_go)
            tarch.addfile(info, bytes_to_go)

        # Grab the container that corresponds to the current switch
        qnodersp = requests.get(gns3_url + 'projects/' + gnsprj_response.json()
                                ['project_id'] + '/nodes/' + switch_vals[sw_c][8])
        crntdockerid = qnodersp.json()['properties']['container_id']
        cont1 = d_clnt.containers.get(crntdockerid)

        # Retrieve our tar archive from the file-like object ('fh') that we staored it in
        uggo = fh.getbuffer()
        # Put the startup-config onto / on the virtual-switch
        copied2 = cont1.put_archive('/', data=uggo)

        # Move the startup-config from / to /mnt/flash on the virtual switch
        moved = cont1.exec_run('mv /startup-config /mnt/flash/')

        # Tell GNS3 to stop the node/container
        gnsrsp = requests.post(gns3_url+'projects/' + gnsprj_response.json()
                               ['project_id']+'/nodes/' + switch_vals[sw_c][8] + '/stop')

    # Tell GNS3 to close the project that we created.
    gnodest = requests.post(gns3_url + 'projects/' + gnsprj_response.json()
                            ['project_id'] + '/close')
    # Done!
    return ()


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
    main(**kwdict)
