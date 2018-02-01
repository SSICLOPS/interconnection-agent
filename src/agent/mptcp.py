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

import ipaddress
import uuid
import json
import traceback

import pyroute_utils
import iptables
import utils

from helpers_n_wrappers import utils3
from netns.netns import NetNS

def no_op(*args, **kwargs):
    return
    
    
"""
#Notes on the flows :
    for br-cloud-tun :
    
    for a network with mptcp, we need to get the broadcast ARP messages to learn
    the IP to mac correspondance. So when the broadcast reaches the MPTCP_SPLIT
    table, the TCP and the ARP of the network are resubmitted to MPTCP_APPLY,
    the rest goes normally to the ROUTING table. 
    for TCP:
        - if peer_vni, move the vlan to packet mark, move the peer vni to the vlan, move the 
        self vni to the packet mark (up), send to patch port
    for ARP:
        - if peer_vni, resumbit to ROUTING table, then do as for TCP
    
    Incoming packets :
        the packet mark will have the in vlan tag and the peer VNI
        matching on both of those, the vlan tag needs to be put to actual
        vlan tag, and output to patch port.
        
    for br-cloud-mptcp:
        from br-cloud-tun:
            higher priority : if ARP, learn load mac_dst with mac_src if dst ip = 
            query source ip, load vlan, match packet mark output patch, drop after
            rest : normal
        not from br-cloud-tun:
            go to learnt table by default
        
"""

class Mptcp_manager(object):
    def __init__(self, mptcp_conf_path, ovs_manager, of_manager, dp_mptcp, 
            enabled, internal_address_network ):
        self.enabled = enabled
        if not self.enabled :
            self.add_proxy = no_op
            self.del_proxy = no_op
            return
        self.ipr = pyroute_utils.createIpr()
        self.ovs_manager = ovs_manager
        self.of_manager = of_manager
        self.networks = {}
        self.proxies = {}
        self.internal_net = internal_address_network
        self.available_internal_ips = set(internal_address_network.hosts())
        self.internal_netmask = internal_address_network.prefixlen
        self.internal_gateway = self.get_next_addr_int()
        with open(mptcp_conf_path, "r") as file:
            network_configs = json.load(file)
        self.routing_table_id = 100
        for network_config in network_configs:
            if network_config["name"] in self.networks:
                raise ValueError("Duplicated MPTCP network name")
            mptcp_net = Mptcp_network(ipr = self.ipr, 
                routing_table_id = self.routing_table_id, **network_config
                )
            self.routing_table_id += 1
            self.networks[mptcp_net.name] = mptcp_net
        self.ovs_manager.set_infra_mptcp(dp_mptcp)

    def init_flows(self):
        self.of_manager.init_mptcp(dp_mptcp = self.ovs_manager.dp_mptcp, 
            dpid_mptcp = self.ovs_manager.dpid_mptcp, 
            patch_mptcp_port = self.ovs_manager.patchMptcpPort, 
            patch_tun_port_mptcp = self.ovs_manager.patchTunPortMptcp
            )

        #self.add_proxy(peer_vni=156, self_port_wan=1080, self_port_lan=1082)
        #self.del_proxy(peer_vni=256, self_port_wan=1080, self_port_lan=1082)
        
            
    def add_proxy(self, **kwargs):
        if kwargs["peer_vni"] in self.proxies:
            raise ValueError("Duplicated MPTCP proxy")
        
        #Create the proxy and register it
        proxy = Mptcp_proxy(ipr = self.ipr, **kwargs)
        self.proxies[proxy.peer_vni] = proxy
        
        #create the namespace (this removes any previous namespace with same name
        pyroute_utils.createNetNS("mptcp-{}".format(proxy.peer_vni), 
            recreate=True
            )
        
        proxy.routing_table_id = 100
        
        self.add_proxy_wan(proxy)
        self.add_proxy_lan(proxy)
        self.of_manager.add_proxy(proxy.ovs_port_id, proxy.peer_vni, 
            proxy.int_mac_address
            )
        
    def del_proxy(self, **kwargs):
        if kwargs["peer_vni"] not in self.proxies:
            raise ValueError("MPTCP proxy not found")
        
        
        proxy = self.proxies[kwargs["peer_vni"]]
        
        
        self.del_proxy_wan(proxy)
        self.del_proxy_lan(proxy)
        
        netns_name = "mptcp-{}".format(proxy.peer_vni)
        
        netns = pyroute_utils.getNetNS(netns_name)
        netns.close()
        netns.remove()
        
        del self.proxies[kwargs["peer_vni"]]
        
        
        
    def add_proxy_wan(self, proxy):
        
        default = False
        
        
        #For each public interface of the host, create a pair of veth and 
        # configure the routing properly
        for net_name in self.networks:
            mptcp_net = self.networks[net_name]
            veth_name = "mptcp{}s{}".format(
                    proxy.peer_vni, mptcp_net.external_interface
                    )
            veth_ns_name = "mptcp{}n{}".format(
                    proxy.peer_vni, mptcp_net.external_interface
                    )
            netns_name = "mptcp-{}".format(proxy.peer_vni)
            netns = pyroute_utils.getNetNS(netns_name)
            
            
            #Try to delete existing link to remove unknown configs
            try:
                idx = pyroute_utils.getLink(self.ipr, veth_name)
                pyroute_utils.delLink(self.ipr, idx = idx)
            except:
                pass
            #Create the veth pair
            if_idx = pyroute_utils.createLink(self.ipr, veth_name, "veth", 
                peerName = veth_ns_name
                )
            #put it in the namespace
            ns_if_idx = pyroute_utils.setNetNS(self.ipr, netns_name, 
                interfaceName = veth_ns_name
                )
            pyroute_utils.setUp(netns, idx = ns_if_idx)
            pyroute_utils.setUp(self.ipr, idx = if_idx)
            
            #Get the IP address and configure it
            proxy.ext_addresses[mptcp_net.name] = mptcp_net.get_next_addr()
            address = proxy.ext_addresses[mptcp_net.name].exploded
            pyroute_utils.add_address(netns, ns_if_idx, address,
                mptcp_net.net_mask
                ) 
            
            #If that was the first address, use it as default route
            if not default:
                pyroute_utils.add_route(netns, gateway = mptcp_net.gateway.exploded)
                default = True
            
            #Set a rule so that traffic from that IP goes to a separate table
            pyroute_utils.add_rule(netns, table = proxy.routing_table_id, src = address)
            
            #Add the link route and the default route
            pyroute_utils.add_route(netns, dst = mptcp_net.network.with_prefixlen,
                proto = "static", scope = "link",
                prefsrc = address,
                table = proxy.routing_table_id,
                oif = ns_if_idx,
                )
            pyroute_utils.add_route(netns, gateway = mptcp_net.gateway.exploded, 
                table = proxy.routing_table_id
                )
            proxy.routing_table_id += 1
            
            
            pyroute_utils.setUp(self.ipr, idx = mptcp_net.bridge_idx)
            pyroute_utils.addIfBr(self.ipr, ifIdx=if_idx, 
                brIdx = mptcp_net.bridge_idx
                )
            
            
            if mptcp_net.nated:
                # add the iptables DNAT rule on ext interface
                iptables.addRules(iptables.def_DNAT(mptcp_net.external_interface,
                    proxy.self_port_wan, address, proxy.self_port_wan
                    ))
            
                #Create a dummy with the address to trick the mptcp stack
                dum_idx = pyroute_utils.createLink(netns, 
                    "dummy{}".format(mptcp_net.external_interface), type = "dummy")
                pyroute_utils.flush_addresses(netns, dum_idx)
                pyroute_utils.add_address(netns, dum_idx, 
                    mptcp_net.external_ip.exploded, mptcp_net.net_mask
                    )
                
                
                
            netns.close()
            
            
    def del_proxy_wan(self, proxy):
        
        #For each public interface of the host, create a pair of veth and 
        # configure the routing properly
        for net_name in self.networks:
            
            mptcp_net = self.networks[net_name]
            address = proxy.ext_addresses[mptcp_net.name].exploded
            
            if mptcp_net.nated:
                # add the iptables DNAT rule on ext interface
                iptables.delRules(iptables.def_DNAT(mptcp_net.external_interface,
                    proxy.self_port_wan, address, proxy.self_port_wan
                    ))
           
            veth_name = "mptcp{}s{}".format(
                    proxy.peer_vni, mptcp_net.external_interface
                    )
            

            mptcp_net.release_addr(proxy.ext_addresses[mptcp_net.name])

            #Try to delete existing link to remove unknown configs
            try:
                idx = pyroute_utils.getLink(self.ipr, veth_name)
                pyroute_utils.delLink(self.ipr, idx = idx)
            except:
                pass
            
            
    

    def add_proxy_lan(self, proxy):
        if_name = "mptcp{}".format(proxy.peer_vni)
        self.ovs_manager.add_internal_port(self.ovs_manager.dp_mptcp, if_name, 
            vlan=proxy.peer_vni, recreate=True
            )
        proxy.ovs_port_id = self.ovs_manager.find_port(if_name)
        
        netns_name = "mptcp-{}".format(proxy.peer_vni)
        netns = pyroute_utils.getNetNS(netns_name)
        
        #put it in the namespace
        ns_if_idx = pyroute_utils.setNetNS(self.ipr, netns_name, 
            interfaceName = if_name
            )
        pyroute_utils.setUp(netns, idx = ns_if_idx)
        
        proxy.int_address = self.get_next_addr_int()
        address = proxy.int_address.exploded
        
        pyroute_utils.add_address(netns, ns_if_idx, address,
                self.internal_netmask
                )
                
        proxy.int_mac_address = pyroute_utils.getInterfaceMac(netns, ns_if_idx)

        if not proxy.int_mac_address:
            raise ValueError("Unable to find the mac address")
        
        #Set a rule so that traffic from that IP goes to a separate table
        pyroute_utils.add_rule(netns, table = proxy.routing_table_id, 
            src = address
            )
        
        #Add the link route and the default route
        pyroute_utils.add_route(netns, dst = self.internal_net.with_prefixlen,
            proto = "static", scope = "link",
            prefsrc = address,
            table = proxy.routing_table_id,
            oif = ns_if_idx,
            )
        pyroute_utils.add_route(netns, gateway = self.internal_gateway.exploded, 
            table = proxy.routing_table_id
            )
            
        utils.execute(
            "ip netns exec {} arp -s {} E1:8E:36:8C:F6:0D".format(
                netns_name, self.internal_gateway.exploded
                )
            )
        proxy.routing_table_id += 1
        

        with NetNS(netns_name):
            iptables.addRules(iptables.def_REDIRECT(if_name, proxy.self_port_lan))
        netns.close()
        
    def del_proxy_lan(self, proxy):
        if_name = "mptcp{}".format(proxy.peer_vni)
        self.ovs_manager.del_port(if_name)
        self.release_addr_int(proxy.int_address)
           
        
        
        
    def get_next_addr_int(self):
        return self.available_internal_ips.pop()
        
    def release_addr_int(self, address):
        self.available_internal_ips.add(address)
        
        
            
            
class Mptcp_network(object):
    def __init__(self, **kwargs):
        utils3.set_attributes(self, override=True, **kwargs)
        self.nated = True
        #Attributes of interest:
        # - gateway : the gateway IP address for the mptcp namespace
        # - network : the network from which the pool of IP comes from
        # - net_mask : the network mask
        # - external_ip : the IP of the host in the external network
        # - external_interface : the host interface (from config)
        
        #Create a bridge for that network
        self.bridge_idx = pyroute_utils.createLink(self.ipr,
            "br-{}".format(self.external_interface), "bridge"
            )
        pyroute_utils.setUp(self.ipr, idx = self.bridge_idx)
        
        #Get the usable range of IP addresses
        network = ipaddress.ip_network(
            self.address_range
            )
        self.available_addresses = set(network.hosts())
        
        
        external_ip_masked = pyroute_utils.get_ip_with_mask(self.ipr, 
            self.external_interface
            ).pop()
        self.external_ip = ipaddress.ip_address(external_ip_masked.split("/")[0])
        net_if_idx = pyroute_utils.getLink(self.ipr, self.external_interface)
        
        if self.nated:
            self.gateway = self.get_next_addr()
            self.net_mask = network.prefixlen
            self.network = ipaddress.ip_network(
                "{}/{}".format(self.gateway, self.net_mask), strict=False
                )
            gw_network = ipaddress.ip_network(external_ip_masked, strict=False)
            # add the masquerade rule on ext interface
            iptables.addRules(iptables.def_masquerade([self.external_interface]))
            
            #Add an ip rule for traffic from network to use specific routing table
            try:
                pyroute_utils.del_rule(self.ipr, table = self.routing_table_id, src = self.network.with_prefixlen)
            except:
                pass
            pyroute_utils.add_rule(self.ipr, table = self.routing_table_id, src = self.network.with_prefixlen)
            
            #populate the routing table
            pyroute_utils.flush_routes(self.ipr, table = self.routing_table_id)
            pyroute_utils.add_route(self.ipr, dst = gw_network.with_prefixlen,
                proto = "static", scope = "link",
                prefsrc = self.external_ip.exploded,
                table = self.routing_table_id,
                oif = net_if_idx,
                )
            pyroute_utils.add_route(self.ipr, gateway = self.gateway_address, 
                table = self.routing_table_id
                )           
            
            pyroute_utils.flush_addresses(self.ipr, self.bridge_idx)
            pyroute_utils.add_address(self.ipr, self.bridge_idx, self.gateway.exploded,
                self.net_mask
                )
        else:
            
            self.network = ipaddress.ip_network(external_ip_masked)
            self.gateway = ipaddress.ip_address(self.gateway_address)
            
            self.net_mask = self.network.prefixlen
            pyroute_utils.del_address(self.ipr, net_if_idx, self.external_ip.exploded,
                self.net_mask)
            pyroute_utils.addIfBr(self.ipr, ifIdx=net_if_idx, 
                brIdx=self.bridge_idx
                )
               
               
            pyroute_utils.flush_addresses(self.ipr, self.bridge_idx)
            pyroute_utils.add_address(self.ipr, self.bridge_idx, self.external_ip.exploded,
                self.net_mask
                )
            

            
            
    def get_next_addr(self):
        return self.available_addresses.pop()
        
    def release_addr(self, address):
        self.available_addresses.add(address)
        
class Mptcp_proxy(object):
    def __init__(self, **kwargs):
        utils3.set_attributes(self, override=True, **kwargs)
        self.ext_addresses = {}
        
        #requires :
        #peer_vni
        #self_port_wan
        #self_port_lan
            