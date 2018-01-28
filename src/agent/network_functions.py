import pyroute_utils
import utils
import logging
import traceback
from netns import netns
import iptables

"""
Create the namespace, the linux bridge and add all the links to the namespace and bridge
"""

def addNetns(ipr, network_id, vlan, mtu):
    pyroute_utils.createNetNS("net-{}".format(network_id))
    ns = pyroute_utils.getNetNS("net-{}".format(network_id))
    pyroute_utils.createLink(ns, 'lxb', 'bridge')
    pyroute_utils.createVlan(ns, 'lxb.{}'.format(vlan), 'lxb', vlan)
    idx_in = pyroute_utils.setNetNS(
        ipr, "net-{}".format(network_id), 
        interfaceName=pyroute_utils.IN_PORT_ROOT.format(network_id)
    )
    idx_out = pyroute_utils.setNetNS(
        ipr, "net-{}".format(network_id), 
        interfaceName=pyroute_utils.OUT_PORT_ROOT.format(network_id)
    )
    pyroute_utils.addIfBr(ns, ifIdx=idx_in, brName='lxb')[1]
    idx_lxb = pyroute_utils.addIfBr(ns, ifIdx=idx_out, brName='lxb')[1]
    pyroute_utils.setMtu(ns, pyroute_utils.IN_PORT_ROOT.format(network_id), 
        mtu
    )
    pyroute_utils.setMtu(ns, pyroute_utils.OUT_PORT_ROOT.format(network_id), 
        mtu
    )
    pyroute_utils.setMtu(ns, 'lxb', mtu)
    pyroute_utils.setMtu(ns, 'lxb.{}'.format(network_id), mtu)
    pyroute_utils.setUp(ns, idx=idx_in)
    pyroute_utils.setUp(ns, idx=idx_out)
    pyroute_utils.setUp(ns, idx=idx_lxb)
    ns.close()

    #TODO make sure netns use of libc does not create issue with aiohttp or aioamqp
    with netns.NetNS("net-{}".format(network_id)):
        iptables.addRules(iptables.defInputOutputDrop())
        iptables.addRules(iptables.defNoTrack())
        utils.execute("sysctl -w net.ipv6.conf.lxb.disable_ipv6=1")
        utils.execute("sysctl -w net.ipv6.conf.lxb/{}.disable_ipv6=1".format(vlan))

    return



"""
Set up ebtables and iptables for the namespace. start the queues processes
"""

def setIptables(network_id, mtu):

    with netns.NetNS("net-{}".format(network_id)):
        iptables.addRules(iptables.defTCPClamping(
            [(pyroute_utils.IN_PORT_ROOT.format(network_id), mtu), 
                (pyroute_utils.OUT_PORT_ROOT.format(network_id), mtu)
            ]
        ))

    logging.debug("Network {} iptables rules added".format(network_id))        
        
        
        
def removeNetns(network_id):
    pyroute_utils.delNetNS("net-{}".format(network_id))
    logging.debug("Network {} namespace removed".format(network_id))   