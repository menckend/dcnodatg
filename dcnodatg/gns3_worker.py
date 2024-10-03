"""gns3_worker.py

Creates project and nodes on GNS3 server and then populates their configuration."""
import asyncio
#from asyncio import tasks
from io import BytesIO
import tarfile
import requests
import aiohttp
import docker


async def stop_a_node(session: str, url: str) -> str:
    """Add nodes to the new GNS3 project and push a copy of the configuration files
    to their substrate docker containers.

    Parameters
    ----------
    session : str
        The name of the aiohttp.ClientSession object used for the connections
    url : str
        The URL to be posted to the GNS3 server
    """
    async with session.post(url) as response:
        # await on asyncio.sleep function because it takes about 6 seconds to receive
        # the session.post response and we want to free up some time for the main
        # loop to keep executing
        await asyncio.sleep(.2)
        return response


async def gns3_node_create_async(servername_in: str, gns3_url_in: str, sw_vals_in: list,
                          allconf_in: list, prj_id_in: str):
    async with aiohttp.ClientSession() as session:
        # Set x/y coordinates for the first node on the project
        nodex = -900
        nodey = -420
        # Create docker client for RESTful API
        d_clnt = docker.DockerClient(base_url='tcp://'+servername_in+':2375')
        # Initialize single string version of switch config from allconf_in
        my_string_to_go = ''
        tasks=[]
        # Loop through the switches
        for sw_val_ctr, sw_val in enumerate(sw_vals_in):
            looped_template_id = requests.post(gns3_url_in + 'templates/' + sw_val[7]
                                            + '/duplicate',
                                            timeout=5).json()['template_id']
            # Put request to change the # of interfaces of the temporary template.
            requests.put(gns3_url_in + 'templates/' + looped_template_id, json={'adapters':
                        int(sw_val[6]) + 2}, timeout=5)
            # Request to instantiate a new node using the temporary template
            newnodeoutput = requests.post(gns3_url_in + 'projects/' + prj_id_in +
                                        '/templates/' + sw_val[7], timeout=5,
                                        json={'x': nodex, 'y': nodey})
            # Capture the GNS3 node_id of the virtual-switch we just created
            sw_val[8] = newnodeoutput.json()['node_id']
            # Request to delete the temporary template
            requests.delete(gns3_url_in + 'templates/' + looped_template_id, timeout=5)

            # Change the name of the GNS3 node that we just created
            requests.put(gns3_url_in + 'projects/' + prj_id_in + '/nodes/' + sw_val[8],
                        timeout=5, json={'name': sw_val[0]})
            # Capture the docker_id of the virtual-switch we just created  (container
            # re-spawned when we changed its name)
            sw_val[9] = requests.get(gns3_url_in + 'projects/' + prj_id_in + '/nodes/' +
                                    sw_val[8], timeout=5).json()['properties']['container_id']
            # Copy the modified sw_val objects contents back into sw_vals_in[sw_val_ctr]
            sw_vals_in[sw_val_ctr] = sw_val
            # Increment x/y coordinates for the *next* switch to be instantiated
            nodex += 120
            if nodex > 500:
                nodex = -900
                nodey = nodey + 120
            # Tell GNS3 to start the node that represents the current switch
            requests.post(gns3_url_in + 'projects/' + prj_id_in + '/nodes/' + sw_val[8] +
                        '/start', timeout=5)
            # Rebuild the switch-config from its current state as a list of individual
            # lines to a single string with newline characters.
            my_string_to_go = ''
            for i in allconf_in[sw_val_ctr]:
                my_string_to_go = my_string_to_go + i + "\n"
            # Apply ASCII encoding to the config string
            ascii_to_go = my_string_to_go.encode('ascii')
            # Turn the ASCII-encoded string into a bytes-like object
            bytes_to_go = BytesIO(ascii_to_go)
            # file_like_to_go = StringIO(my_string_to_go)
            # Turn the switch-config string into a tar archive for later
            fh = BytesIO()
            with tarfile.open(fileobj=fh, mode='w') as tarch:
                info = tarfile.TarInfo('startup-config')
                info.size = len(my_string_to_go)
                tarch.addfile(info, bytes_to_go)
            # Get a docker API connection for the current switch's container
            cont1 = d_clnt.containers.get(sw_val[9])
            # Retrieve our tar archive from the file-like object ('fh') that we stored it in
            uggo = fh.getbuffer()
            # Put the startup-config onto / on the virtual-switch
            cont1.put_archive('/', data=uggo)
            # Move the startup-config from / to /mnt/flash on the virtual switch
            cont1.exec_run('mv /startup-config /mnt/flash/')
            # Set URL for request to GNS3 to stop the node
            url = gns3_url_in+"projects/" + prj_id_in+"/nodes/" + sw_val[8] + "/stop"
            # Assign the HTTP post request for async execution
            tasks.append(asyncio.ensure_future(stop_a_node(session, url)))
            await asyncio.sleep(0.1)
        responses = await asyncio.gather(*tasks)
        return responses


def invoker(servername_in: str, gns3_url_in: str, sw_vals_in: list, allconf_in: list, prj_id_in: str):
    asyncio.run(gns3_node_create_async(servername_in, gns3_url_in, sw_vals_in, allconf_in, prj_id_in))
    return 'done'
