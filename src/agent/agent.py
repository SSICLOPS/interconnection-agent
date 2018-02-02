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

import sys, getopt, os
import configparser
import asyncio
import logging.config
import logging
import random
import json
import uuid
import ipaddress

from common import amqp_client
import queue_manager
import pyroute_utils
import amqp_agent
from ovs import ovs_manager, ofctl_manager
from ipsec import strongswan_driver, vpn_manager
import network_functions
from common import file
import mptcp

from helpers_n_wrappers import utils3

        
class Agent(object):
    def __init__(self, **kwargs):
        utils3.set_attributes(self, override = True, **kwargs)
        self.tunnels_port_ids = {}
        self.tunnels = {}
        self.networks_mapping = {}
        self.networks = {}
        self.expansions = {}
        self.update_runtime_id()
        #ovs_manager
        #vpn_manager
        #of_manager

        
    def update_heartbeat_payload(self):
        heartbeat_payload = { "node_uuid": self.self_id,
            "addresses":list(self.addresses),
            "runtime_id":self.runtime_id,
            "standalone": self.standalone,
            "networks": list(self.networks_mapping.keys()),
            "vni": self.self_vni
            }
        return json.dumps(heartbeat_payload)
        
    def update_runtime_id(self):
        self.runtime_id = random.randint(1,amqp_client.MAX_KEY)
        return self.update_heartbeat_payload()
        
    def update_addresses(self, addresses):
        self.addresses = addresses
        return self.update_heartbeat_payload()
    
    def update_networks_mapping(self, mappings):
        self.networks_mapping = mappings
        return self.update_heartbeat_payload()
    
    def add_tunnel(self, **kwargs):
        #Create a default port name if it does not exist
        port_name = "cl-{}".format(str(uuid.uuid4())[:8])
        
        #Create or find the existing tunnel
        port_name, port_id = self.ovs_manager.add_tun_port(port_name, 
            kwargs["self_ip"], kwargs["peer_ip"], kwargs["type"]
            )
        
        #Store this tunnel as a way to reach the peer
        if kwargs["peer_vni"] in self.tunnels_port_ids :
            self.tunnels_port_ids[kwargs["peer_vni"]].append(port_id)
        else:
            self.tunnels_port_ids[kwargs["peer_vni"]] = [port_id]
        
        kwargs["port_name"] = port_name
        kwargs["port_id"] = port_id
        self.tunnels[kwargs["node_id"]] = kwargs
        
        #Add the flows for the tunnel
        self.of_manager.add_tunnel(port_id)
        
        #Add a direct route, This will change with a route manager
        self.of_manager.add_route(kwargs["peer_vni"], port_id)
            
    def del_tunnel(self, **kwargs):
        port_name = self.tunnels[kwargs["node_id"]]["port_name"]
        port_id = self.tunnels[kwargs["node_id"]]["port_id"]
        
        #Delete the tunnel
        self.ovs_manager.del_tun_port(port_name, kwargs["self_ip"], 
            kwargs["peer_ip"], kwargs["type"]
            )
        self.tunnels_port_ids[kwargs["peer_vni"]].discard(port_id)
        
        #Delete the tunnel flows
        self.of_manager.del_tunnel(port_id)
        
        #Delete the route, This will change
        self.of_manager.del_route(kwargs["peer_vni"])
        
        del self.tunnels[kwargs["node_id"]]
        
    def add_network(self, **kwargs):
        network_id = kwargs["node_id"]
        self.networks[network_id] = kwargs
        seg_id = kwargs["cloud_network_id"]
        if self.standalone:
            vlan = seg_id
        else:
            vlan = self.networks_mapping[seg_id]
        self.networks[network_id]["vlan"] = vlan
        
        #Add the namespace ports on the switches
        self.ovs_manager.add_internal_port(self.ovs_manager.dp_in, 
            pyroute_utils.IN_PORT_ROOT.format(seg_id), vlan
            )
        self.ovs_manager.add_internal_port(self.ovs_manager.dp_out, 
            pyroute_utils.OUT_PORT_ROOT.format(seg_id), vlan
            )
            
        #Create the namespace
        network_functions.addNetns(self.iproute, seg_id, vlan, self.mtu_lan)
        
        #Create the clamping rules
        network_functions.setIptables(seg_id, self.mtu_wan)
        
    def del_network(self, **kwargs):
        network_id = kwargs["node_id"]
        network_dict = self.networks[network_id]
        seg_id = network_dict["cloud_network_id"]
        vlan = network_dict["vlan"]
        
        #Delete the namespace
        network_functions.removeNetns(seg_id)
        
        #Remove the ports from the switches
        self.ovs_manager.del_port(pyroute_utils.IN_PORT_ROOT.format(seg_id))
        self.ovs_manager.del_port(pyroute_utils.OUT_PORT_ROOT.format(seg_id))
        
        del self.networks[network_id]
        
    
    def add_expansion(self, **kwargs):
        expansion_id = kwargs["node_id"]
        self.expansions[expansion_id] = kwargs
        network = self.networks[kwargs["network_id"]]
        vlan = network["vlan"]
        expansions_list = []
        
        #Create a list of all expansions for a network for the flood
        for expansion_mult in self.expansions.values():
            if expansion_mult["cloud_network_id"] == kwargs["cloud_network_id"]:
                expansions_list.append(expansion_mult)
        
        #Add the flows for the expansion
        self.of_manager.add_expansion(kwargs, expansions_list, vlan)
        
    def del_expansion(self, **kwargs):
        expansion_id = kwargs["node_id"]
        expansion = self.expansions[expansion_id]
        network = self.networks[expansion["network_id"]]
        vlan = network["vlan"]
        del self.expansions[expansion_id]
        
        #Create a list of all expansions but the deleted 
        expansions_list = []
        for expansion_mult in self.expansions.values():
            if expansion_mult["cloud_network_id"] == expansion["cloud_network_id"]:
                expansions_list.append(expansion_mult)
        
        #Delete the flow and update the flood
        self.of_manager.del_expansion(expansion, expansions_list, vlan)
        
            
def init_agent(argv):
    cli_error_str = "agent.py -c <configuration file>"
    configuration_file = None
    asyncio_loop = asyncio.get_event_loop()
    
    #parse the command line arguments
    # h - help : help
    # c - conf : configuration file
    try:
        cli_opts, _ = getopt.getopt(argv, "hc:",["help","conf="])
    
    except getopt.GetoptError:
        print(cli_error_str)
        sys.exit()
    
    for cli_opt, cli_arg in cli_opts:
        
        if cli_opt in ("-c", "--conf"):
            configuration_file = cli_arg
        
        else:
            print(cli_error_str)
            sys.exit()
    
    #Exit if the configuration file is not set
    if not configuration_file:
        print(cli_error_str)
        sys.exit()
    
    #Parse the configuration file
    config = configparser.ConfigParser()
    config.read(configuration_file)

    log_config_file = file.get_filename(config, "DEFAULT", "log_config_file")
    logging.config.fileConfig(log_config_file)
    
    #Get the IP addresses
    iproute = pyroute_utils.createIpr()
    addresses = set()
    interfaces = config.get('DEFAULT', 'public_interface')
    if interfaces.find(",") >= 0:
        interfaces_list = interfaces.split(",")
    else:
        interfaces_list = [interfaces]
    for interface in interfaces_list:
        addresses.update(pyroute_utils.getInterfaceIP(iproute, interface))
    
    self_id = config.get('DEFAULT', "agent_id")
    standalone = config.getboolean("DEFAULT", "standalone")
    mtu_lan = config.getint("DEFAULT", "mtu_lan")
    mtu_wan = config.getint("DEFAULT", "mtu_wan")
    
    
    #Get the VPN configuration
    vpn_backend = config.get('DEFAULT', 'vpn_backend')
    
    if vpn_backend not in ["strongswan"]:
        raise Input_error("The given vpn backend is not supported.")

    vpn_conf = {}
    vpn_conf["conf_template"] = file.get_filename(config, vpn_backend, "template_file")
    vpn_conf["secrets_template"] = file.get_filename(
        config, vpn_backend, "template_secrets_file")
    vpn_conf["conf_filename"] = file.get_filename(config, vpn_backend, "conf_file")
    vpn_conf["secrets_filename"] = file.get_filename( config, vpn_backend, "secrets_file")
    vpn_conf["binary"] = file.get_filename(config, vpn_backend, "executable")
        
    if vpn_backend == "strongswan":
        vpn_driver = strongswan_driver.Strongswan_driver(**vpn_conf)
        vpn_manager_obj = vpn_manager.Vpn_manager(vpn_driver, addresses)


    
    
    #Get the ovs configuration and init the manager
    ovs_arch = {}
    ovs_arch["dp_in"] = config.get('ovs', 'lan_bridge')
    ovs_arch["dp_out"] = config.get('ovs', 'wan_bridge')
    ovs_arch["dp_tun"] = config.get('ovs', 'tun_bridge')
    ovs_arch["internal_bridge"] = config.get('ovs', 'internal_bridge')
    ovs_arch["standalone"] = standalone
            
    ovs_manager_obj = ovs_manager.Ovs_manager(**ovs_arch)
    ovs_manager_obj.set_infra()
    
    
    #Add the runtime info and init the flow manager
    ovs_arch["patch_in_id"] = ovs_manager_obj.internalPort
    ovs_arch["patch_out_id"] = ovs_manager_obj.patchOutPort
    ovs_arch["patch_tun_id"] = ovs_manager_obj.patchTunPort
    ovs_arch["dpid_in"] = ovs_manager_obj.dpid_in
    ovs_arch["dpid_out"] = ovs_manager_obj.dpid_out
    ovs_arch["dpid_tun"] = ovs_manager_obj.dpid_tun
    ovs_arch["self_vni"] = config.getint('DEFAULT', 'self_vni')
    self_vni = ovs_arch["self_vni"]
    
    flow_ctl = config.get('DEFAULT', 'flow_control')
    if flow_ctl == "ovs-ofctl":
        of_manager_obj = ofctl_manager.Ofctl_manager(**ovs_arch)
    else:
        raise Input_error("The given flow control method is not supported.")

    mptcp_enabled = config.getboolean('DEFAULT', 'mptcp_enabled')
    mptcp_conf_file = config.get('mptcp', 'mptcp_config_file')
    dp_mptcp = config.get('mptcp', 'mptcp_bridge')
    address_pool = ipaddress.ip_network(config.get('mptcp', 
        'internal_address_pool'
        ))
    
    mptcp_manager = mptcp.Mptcp_manager( mptcp_conf_file, ovs_manager_obj, 
        of_manager_obj, dp_mptcp, mptcp_enabled, address_pool
        )
        
    of_manager_obj.init_flows()
    mptcp_manager.init_flows()
    
    #Init the agent
    agent = Agent(self_id = self_id, addresses = addresses, iproute = iproute, 
        standalone = standalone, ovs_manager = ovs_manager_obj,
        vpn_manager = vpn_manager_obj, of_manager = of_manager_obj,
        mtu_lan = mtu_lan, mtu_wan = mtu_wan, mptcp_manager = mptcp_manager,
        self_vni = self_vni
        )
    
    #Init the queue manager
    queue_manager_obj = queue_manager.Queue_manager(agent)
    
    #Get the AMQP configuration
    amqp_auth = {}
    amqp_auth["host"] = config.get('amqp', 'host')
    amqp_auth["login"] = config.get('amqp', 'login')
    amqp_auth["password"] = config.get('amqp', 'password')
    amqp_auth["virtualhost"] = config.get('amqp', 'virtualhost')
    amqp_auth["port"] = config.get('amqp', 'port')
    amqp_auth["loop"] = asyncio_loop
    amqp_auth["bind_action_queue"] = True
    amqp_auth["heartbeat_receive_key"] = amqp_client.AMQP_KEY_HEARTBEATS_CTRL
    amqp_auth["action_callback"] = queue_manager_obj.add_msg_to_queue
    
    amqp_client_obj = amqp_agent.Amqp_agent(agent = agent, node_uuid = self_id,
        **amqp_auth
        )
    queue_manager_obj.set_amqp(amqp_client_obj)
    
    
    
    # Start running
    asyncio_loop.run_until_complete(amqp_client_obj.connect())
    asyncio.ensure_future(ovs_manager_obj.get_network_vlans(amqp_client_obj))
    asyncio.ensure_future(amqp_client_obj.send_heartbeat("{}{}".format(
        amqp_client.AMQP_KEY_HEARTBEATS_AGENTS, self_id)))
    asyncio.ensure_future(queue_manager_obj.process_queue())

    logging.info("Agent started")
    
    try:
        asyncio_loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Stopping")
        asyncio.get_event_loop().close()

if __name__ == "__main__":
   init_agent(sys.argv[1:])
