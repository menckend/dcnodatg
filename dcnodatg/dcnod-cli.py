'''This is a wrapper script for dcnodatg to allow it be be invoked from outside of the 
Python interpreter.  To use it, copy the contents of the dcnodatg folder to the host you
will run it from.  Then move the dcnod-cli.py file *up* one level, so that is is in the 
same directory as the dcnodatg folder.  Refer to the docs for additional details.'''


import dcnodatg
from dcnodatg import dcnodatg
import sys

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
    dcnodatg.p_to_v(**kwdict)
