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
