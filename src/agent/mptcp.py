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
from jinja2 import Environment, FileSystemLoader
import os
import traceback
from subprocess import Popen

import pyroute_utils
import iptables
import utils

from helpers_n_wrappers import utils3
from netns.netns import NetNS

def no_op(*args, **kwargs):
    return
    


class Mptcp_manager(object):
    def __init__(self, **kwargs ):
        utils3.set_attributes(self, override=True, **kwargs)
        
        #If MPTCP is disabled, do nothing when called
        if not self.enabled :
            self.add_proxy = no_op
            self.del_proxy = no_op
            return
        
        self.ipr = pyroute_utils.createIpr()
        self.networks = {}
        self.proxies = {}
        
        #Get the available internal IP addresses to use on the Lan side
        self.available_internal_ips = set(self.internal_net.hosts())
        self.internal_netmask = self.internal_net.prefixlen
        #Internal gateway is a fake gateway used to send all traffic to
        #using a static arp entry. the mac addresses are then rewritten by the
        #switch
        self.internal_gateway = self.get_next_addr_int()
        
        #Parse the network configuration file
        with open(self.mptcp_conf_path, "r") as file:
            network_configs = json.load(file)
        self.routing_table_id = 100
        #For each network in the config
        for network_config in network_configs:
            #Detect duplicates based on external interface
            if network_config["external_interface"] in self.networks:
                raise ValueError("Duplicated MPTCP network name")
            #Initialize the MPTCP network
            mptcp_net = Mptcp_network(ipr = self.ipr, 
                routing_table_id = self.routing_table_id, **network_config
                )
            self.routing_table_id += 1
            self.networks[mptcp_net.external_interface] = mptcp_net
        
        #Create the switch infrastructure on lan side
        self.ovs_manager.set_infra_mptcp(self.dp_mptcp)
        
        #Create the Jinja2 environments for the shadowsocks configuration files,
        #for ss-redir
        self.redir_template_folder, self.redir_template_file = os.path.split(
            self.template_redir)
        self.redir_env = Environment(
            autoescape=False,
            loader=FileSystemLoader(self.redir_template_folder),
            trim_blocks=False)
        
        #for ss-server
        self.server_template_folder, self.server_template_file = os.path.split(
            self.template_server)
        self.server_env = Environment(
            autoescape=False,
            loader=FileSystemLoader(self.server_template_folder),
            trim_blocks=False)

    #Initialize the flows
    def init_flows(self):
        if not self.enabled :
            return
        self.of_manager.init_mptcp(dp_mptcp = self.dp_mptcp, 
            dpid_mptcp = self.ovs_manager.dpid_mptcp, 
            patch_mptcp_port = self.ovs_manager.patchMptcpPort, 
            patch_tun_port_mptcp = self.ovs_manager.patchTunPortMptcp
            )
        
            
    def add_proxy(self, **kwargs):
        if kwargs["peer_vni"] in self.proxies:
            raise ValueError("Duplicated MPTCP proxy")
        
        #Create the proxy and register it
        proxy = Mptcp_proxy(ipr = self.ipr, **kwargs)
        self.proxies[proxy.peer_vni] = proxy
        
        #create the namespace (this removes any previous namespace)
        ns_name = "mptcp-{}".format(proxy.peer_vni)
        pyroute_utils.createNetNS(ns_name, recreate=True)
        
        
        proxy.routing_table_id = 100
        
        #perform the network setup on both sides
        self.add_proxy_wan(proxy)
        self.add_proxy_lan(proxy)
        
        #add the flows for this proxy
        self.of_manager.add_proxy(proxy.ovs_port_id, proxy.peer_vni, 
            proxy.int_mac_address
            )
   
        #Create the ss-redir configuration file
        with open("{}/{}.redir".format(self.tmp_folder, 
                proxy.peer_vni),"w") as redir_file:
            args = {"server_ip": proxy.peer_ip,
                "server_port": proxy.peer_port,
                "local_ip": proxy.int_address.exploded,
                "local_port": proxy.self_port_lan
                }
            conf = self.redir_env.get_template(self.redir_template_file).render(
                args
                )
            redir_file.write(conf)
        
        
        #For the server, if one address, as string, if several, as list
        if len(proxy.ext_addresses) == 1:
            for address in proxy.ext_addresses.values():
                addresses_list = "\"{}\"".format(address)
        elif len(proxy.ext_addresses) > 1:
            addresses_list = "[\"{}\"]".format(
                "\",\"".join(proxy.ext_addresses.values())
                )
            
        #Create the ss-server configuration file
        with open("{}/{}.server".format(self.tmp_folder, 
                proxy.peer_vni),"w") as server_file:
            server_file.write(self.server_env.get_template(
                self.server_template_file).render(
                    {"local_port": proxy.self_port_wan,
                        "bind_ip": proxy.int_address.exploded,
                        "server_address": addresses_list
                        }
                    )
                )
        
        #Start the instances of shadowsocks
        proxy.nsp_redir = Popen(["ip", "netns", "exec", ns_name, 
            self.exec_redir, "-c", 
            "{}/{}.redir".format(self.tmp_folder, 
            proxy.peer_vni)
            ])
        proxy.nsp_server = Popen(["ip", "netns", "exec", ns_name, 
            self.exec_server, "-c", 
            "{}/{}.server".format(self.tmp_folder, 
                proxy.peer_vni
                ),
            ])
        


        
    def del_proxy(self, **kwargs):
        if kwargs["peer_vni"] not in self.proxies:
            raise ValueError("MPTCP proxy not found")
        proxy = self.proxies[kwargs["peer_vni"]]
        
        #Delete the network infrastructure
        self.del_proxy_wan(proxy)
        self.del_proxy_lan(proxy)
        
        #del the flows for this proxy
        self.of_manager.del_proxy(proxy.ovs_port_id, proxy.peer_vni)
        
        #Delete the namespace
        netns_name = "mptcp-{}".format(proxy.peer_vni)
        netns = pyroute_utils.getNetNS(netns_name)
        netns.close()
        netns.remove()
        
        del self.proxies[kwargs["peer_vni"]]
        
        proxy.nsp_redir.terminate()
        proxy.nsp_redir.kill()
        proxy.nsp_server.terminate()
        proxy.nsp_server.kill()
        
    def add_proxy_wan(self, proxy):
        default = False
        
        #For each public interface of the host, create a pair of veth and 
        # configure the routing properly
        for external_interface in self.networks:
            mptcp_net = self.networks[external_interface]
            
            veth_name = "mptcp{}s{}".format(
                    proxy.peer_vni, external_interface
                    )
            veth_ns_name = "mptcp{}n{}".format(
                    proxy.peer_vni, external_interface
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
                pyroute_utils.add_route(netns, 
                    gateway = mptcp_net.gateway.exploded
                    )
                default = True
            
            #Set a rule so that traffic from that IP goes to a separate table
            pyroute_utils.add_rule(netns, table = proxy.routing_table_id, 
                src = address
                )

            
            #Add the link route and the default route
            pyroute_utils.add_route(netns, 
                dst = mptcp_net.network.with_prefixlen,
                proto = "static", scope = "link",
                prefsrc = address,
                table = proxy.routing_table_id,
                oif = ns_if_idx,
                )
            pyroute_utils.add_route(netns, gateway = mptcp_net.gateway.exploded, 
                table = proxy.routing_table_id
                )
            proxy.routing_table_id += 1
            
            
            #Connect the other side of the veth
            pyroute_utils.setUp(self.ipr, idx = mptcp_net.bridge_idx)
            pyroute_utils.addIfBr(self.ipr, ifIdx=if_idx, 
                brIdx = mptcp_net.bridge_idx
                )
            
            
            
            if mptcp_net.nated:
                # add the iptables DNAT rule on ext interface
                iptables.addRules(iptables.def_DNAT(external_interface,
                    proxy.self_port_wan, address, proxy.self_port_wan
                    ))
            
                #Create a dummy with the address to trick the mptcp stack
                dum_name = "dum{}".format(external_interface)
                dum_idx = pyroute_utils.createLink(netns, 
                        dum_name, type = "dummy",
                        )

                #Set the address
                pyroute_utils.setUp(netns, idx = dum_idx)
                pyroute_utils.flush_addresses(netns, dum_idx)
                pyroute_utils.add_address(netns, dum_idx, 
                    mptcp_net.external_ip.exploded, 32
                    )
                
                
                
            netns.close()
            
            
    def del_proxy_wan(self, proxy):
        
        #For each public interface of the host, delete a pair of veth and 
        # deconfigure the routing properly
        for external_interface in self.networks:
            
            mptcp_net = self.networks[external_interface]
            address = proxy.ext_addresses[mptcp_net.name].exploded
            
            if mptcp_net.nated:
                # del the iptables DNAT rule on ext interface
                iptables.delRules(iptables.def_DNAT(external_interface,
                    proxy.self_port_wan, address, proxy.self_port_wan
                    ))
           
            veth_name = "mptcp{}s{}".format(
                    proxy.peer_vni, external_interface
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
        netns_name = "mptcp-{}".format(proxy.peer_vni)
        netns = pyroute_utils.getNetNS(netns_name)
        
        #Create the ovs internal port
        #Need to always recreate it because if the port was in a namespace,
        # and the namespace was deleted, the port will exist in OVS, not in 
        # the root namespace.
        self.ovs_manager.add_internal_port(self.ovs_manager.dp_mptcp, if_name, 
            vlan=proxy.peer_vni, recreate=True
            )
        proxy.ovs_port_id = self.ovs_manager.find_port(if_name)
        
        
        #put it in the namespace
        ns_if_idx = pyroute_utils.setNetNS(self.ipr, netns_name, 
            interfaceName = if_name
            )
        pyroute_utils.setUp(netns, idx = ns_if_idx)
        
        #Set the address on the lan side
        proxy.int_address = self.get_next_addr_int()
        address = proxy.int_address.exploded
        pyroute_utils.add_address(netns, ns_if_idx, address,
                self.internal_netmask
                )
                
        #Find the mac address
        proxy.int_mac_address = pyroute_utils.getInterfaceMac(netns, ns_if_idx)
        if not proxy.int_mac_address:
            raise ValueError("Unable to find the mac address")
        
        #Set a rule so that traffic from the IP goes to a separate table
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
            
        #Set the static arp entry for the fake gateway on lan
        utils.execute(
            "ip netns exec {} arp -s {} E1:8E:36:8C:F6:0D".format(
                netns_name, self.internal_gateway.exploded
                )
            )
        proxy.routing_table_id += 1
        
        #add the TCP redirect
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
        # - gateway_address : the external gateway address from config file
        
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
        
        #get the external IP and the mask
        external_ip_masked = pyroute_utils.get_ip_with_mask(self.ipr, 
            self.external_interface
            ).pop()
        self.external_ip = ipaddress.ip_address(external_ip_masked.split("/")[0])
        net_if_idx = pyroute_utils.getLink(self.ipr, self.external_interface)
        
        #If the MPTCP network is nated
        if self.nated:
            #Define the nated network characteristics
            self.gateway = self.get_next_addr()
            self.net_mask = network.prefixlen
            self.network = ipaddress.ip_network(
                "{}/{}".format(self.gateway, self.net_mask), strict=False
                )
            
            #get the external network (for routing purpose)
            gw_network = ipaddress.ip_network(external_ip_masked, strict=False)
            
            # add the masquerade rule on ext interface
            iptables.addRules(iptables.def_masquerade([self.external_interface]))
            
            #Add an ip rule for traffic from network to use source routing
            try:
                pyroute_utils.del_rule(self.ipr, table = self.routing_table_id, 
                    src = self.network.with_prefixlen
                    )
            except:
                pass
            pyroute_utils.add_rule(self.ipr, table = self.routing_table_id, 
                src = self.network.with_prefixlen
                )
            
            #Set the address on the bridge
            pyroute_utils.flush_addresses(self.ipr, self.bridge_idx)
            pyroute_utils.add_address(self.ipr, self.bridge_idx, self.gateway.exploded,
                self.net_mask
                )
            
            #populate the routing table, the routes for both links and the default
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
            
            pyroute_utils.add_route(self.ipr, dst = self.network.with_prefixlen,
                proto = "static", scope = "link",
                prefsrc = self.gateway.exploded,
                table = self.routing_table_id,
                oif = self.bridge_idx,
                )
        
        #If not nated
        else:
            
            #Get the network characteristics
            self.network = ipaddress.ip_network(external_ip_masked, stric=False)
            self.gateway = ipaddress.ip_address(self.gateway_address)
            self.net_mask = self.network.prefixlen
            
            #Remove the ip from the interface to add it on the bridge
            pyroute_utils.del_address(self.ipr, net_if_idx, self.external_ip.exploded,
                self.net_mask)
            pyroute_utils.flush_addresses(self.ipr, self.bridge_idx)
            pyroute_utils.add_address(self.ipr, self.bridge_idx, self.external_ip.exploded,
                self.net_mask
                )
            
            #Bridge the interface
            pyroute_utils.addIfBr(self.ipr, ifIdx=net_if_idx, 
                brIdx=self.bridge_idx
                )
               
            
    def get_next_addr(self):
        return self.available_addresses.pop()
        
    def release_addr(self, address):
        self.available_addresses.add(address)
        
class Mptcp_proxy(object):
    def __init__(self, **kwargs):
        utils3.set_attributes(self, override=True, **kwargs)
        self.ext_addresses = {}

            