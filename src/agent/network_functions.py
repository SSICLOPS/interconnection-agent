"""
BSD 3-Clause License

Copyright (c) 2018, Maël Kimmerlin, Aalto University, Finland
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import logging


import pyroute_utils
import utils
from netns import netns
import iptables


"""
Create the namespace, the linux bridge and add all the links to the namespace and bridge
"""

def addNetns(ipr, network_id, vlan, mtu):
    #Create the namespace
    pyroute_utils.createNetNS("net-{}".format(network_id))
    ns = pyroute_utils.getNetNS("net-{}".format(network_id))
    
    #Create the LXB
    pyroute_utils.createLink(ns, 'lxb', 'bridge')
    pyroute_utils.createLink(ns, 'lxb.{}'.format(vlan), "vlan", link = 'lxb', 
        vlan_id = vlan
        )
    
    #Set the OVS port in the namespace
    idx_in = pyroute_utils.setNetNS(
        ipr, "net-{}".format(network_id), 
        interfaceName=pyroute_utils.IN_PORT_ROOT.format(network_id)
        )
    idx_out = pyroute_utils.setNetNS(
        ipr, "net-{}".format(network_id), 
        interfaceName=pyroute_utils.OUT_PORT_ROOT.format(network_id)
        )
    
    #Add them to the bridge
    pyroute_utils.addIfBr(ns, ifIdx=idx_in, brName='lxb')[1]
    idx_lxb = pyroute_utils.addIfBr(ns, ifIdx=idx_out, brName='lxb')[1]
    
    #Set the MTU
    pyroute_utils.setMtu(ns, pyroute_utils.IN_PORT_ROOT.format(network_id), 
        mtu
        )
    pyroute_utils.setMtu(ns, pyroute_utils.OUT_PORT_ROOT.format(network_id), 
        mtu
        )
    pyroute_utils.setMtu(ns, 'lxb', mtu)
    pyroute_utils.setMtu(ns, 'lxb.{}'.format(network_id), mtu)
    
    #Set everything up
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
Set up iptables for the namespace. start the queues processes
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