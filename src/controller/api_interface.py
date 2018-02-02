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


import uuid
import logging
from aiohttp import web

import utils
import data_container
from ipsec import ike_policy, ipsec_policy, vpn_connection
from tunneling import l2_tunnel, network, expansion, mptcp_proxy
import gui

async def test_callback(**kwargs):
    for agent_amqp in kwargs["data_store"].lookup_list(data_container.KEY_AGENT,
            False, False ):
        payload = {"operation":utils.ACTION_NO_OP}
        await kwargs["amqp"].publish_action(payload=payload, 
            node = agent_amqp, callback = ack_callback,
            )
    raise web.HTTPOk()
    
async def ack_callback(payload, action):
    logging.debug("Received ACK for action {}".format(payload["action_uuid"]))
    
    
#define the API
api_mappings = [
    {"method":"GET", "endpoint":"/test", "callback":test_callback, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    
    {"method":"GET", "endpoint":"/ike", "callback":ike_policy.get_ike_policies, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/ike/{node_id}", 
        "callback":ike_policy.get_ike_policies, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"DELETE", "endpoint":"/ike/{node_id}", 
        "callback":ike_policy.delete_ike_policy, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/ike", 
        "callback":ike_policy.create_ike_policy, "url_args": [], 
        "required_args" : ["name", "ike_version", 
            "encryption_algorithm", "auth_algorithm", "pfs", "lifetime_value"
            ], "opt_args" : ["node_id"]
        },
    
    {"method":"GET", "endpoint":"/ipsec", "callback":ipsec_policy.get_ipsec_policies, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/ipsec/{node_id}", 
        "callback":ipsec_policy.get_ipsec_policies, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"DELETE", "endpoint":"/ipsec/{node_id}", 
        "callback":ipsec_policy.delete_ipsec_policy, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/ipsec", 
        "callback":ipsec_policy.create_ipsec_policy, "url_args": [], 
        "required_args" : ["name", "transform_protocol", "encapsulation_mode",
            "encryption_algorithm", "auth_algorithm", "pfs", "lifetime_value"
            ], "opt_args" : ["node_id"]
        },
    
    {"method":"GET", "endpoint":"/tunnel", "callback":l2_tunnel.get_l2_tunnels, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/tunnel/{node_id}", 
        "callback":l2_tunnel.get_l2_tunnels, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"DELETE", "endpoint":"/tunnel/{node_id}", 
        "callback":l2_tunnel.delete_l2_tunnel, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/tunnel", 
        "callback":l2_tunnel.create_l2_tunnel, "url_args": [], 
        "required_args" : ["name", "self_ip", "peer_id", "peer_ip", 
            "type", "peer_vni", "enabled"
        ], "opt_args" : ["peer_public_ip", "node_id"]
        },
    
    {"method":"GET", "endpoint":"/connection", 
        "callback":vpn_connection.get_vpn_connections, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/connection/{node_id}", 
        "callback":vpn_connection.get_vpn_connections, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"DELETE", "endpoint":"/connection/{node_id}", 
        "callback":vpn_connection.delete_vpn_connection, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/connection", 
        "callback":vpn_connection.create_vpn_connection, "url_args": [], 
        "required_args" : ["name", "tunnel_id", "ike_policy_id", 
            "ipsec_policy_id", "dpd_action", "dpd_interval", "dpd_timeout", 
            "initiator", "secret"
            ], "opt_args" : ["node_id"]
        },
    
    {"method":"GET", "endpoint":"/network", 
        "callback":network.get_networks, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/network/{node_id}", 
        "callback":network.get_networks, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"DELETE", "endpoint":"/network/{node_id}", 
        "callback":network.delete_network, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/network", 
        "callback":network.create_network, "url_args": [], 
        "required_args" : ["name", "cloud_network_id"], "opt_args" : ["node_id"]
        },
    
    {"method":"GET", "endpoint":"/expansion", 
        "callback":expansion.get_expansions, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/expansion/{node_id}", 
        "callback":expansion.get_expansions, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/expansion/network/{network_id}", 
        "callback":expansion.get_expansions, "url_args": ["network_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"DELETE", "endpoint":"/expansion/{node_id}", 
        "callback":expansion.delete_expansion, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/expansion", 
        "callback":expansion.create_expansion, "url_args": [], 
        "required_args" : ["network_id", "tunnel_id", "intercloud_id_out", 
            "intercloud_id_in"
            ], "opt_args" : ["node_id"]
        },
        
    {"method":"GET", "endpoint":"/mptcp", 
        "callback":mptcp_proxy.get_mptcp_proxies, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"GET", "endpoint":"/mptcp/{node_id}", 
        "callback":mptcp_proxy.get_mptcp_proxies, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"DELETE", "endpoint":"/mptcp/{node_id}", 
        "callback":mptcp_proxy.delete_mptcp_proxy, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/mptcp", 
        "callback":mptcp_proxy.create_mptcp_proxy, "url_args": [], 
        "required_args" : ["name", "peer_vni", "agent_id", "peer_id", "peer_ip", 
            "peer_port", "self_port_lan", "self_port_wan"
            ], "opt_args" : ["node_id"]
        },
    
    

    
    
    {"method":"GET", "endpoint":"/gui", "callback":gui.get_main, 
        "url_args": [], "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/create-ike", "callback":gui.create_ike, 
        "url_args": [], "required_args" : ["name", "ike_version", 
            "encryption_algorithm", "auth_algorithm", "pfs", "lifetime_value"
            ], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/delete-ike/{node_id}", 
        "callback":gui.delete_ike, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/create-ipsec", 
        "callback":gui.create_ipsec, "url_args": [], "required_args" : ["name", 
            "transform_protocol", "encapsulation_mode", "encryption_algorithm",
            "auth_algorithm", "pfs", "lifetime_value"
            ], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/delete-ipsec/{node_id}", 
        "callback":gui.delete_ipsec, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/create-tunnel", 
        "callback":gui.create_tunnel, "url_args": [], "required_args" : ["name", 
            "self_ip", "peer_id", "peer_ip", "type", "peer_vni", "enabled", 
            "peer_public_ip"
            ], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/delete-tunnel/{node_id}", 
        "callback":gui.delete_tunnel, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/create-connection", 
        "callback":gui.create_connection, "url_args": [], "required_args" : [
            "name", "tunnel_id", "ike_policy_id", "ipsec_policy_id", 
            "dpd_action", "dpd_interval", "dpd_timeout", "initiator", "secret"
            ], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/delete-connection/{node_id}", 
        "callback":gui.delete_connection, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/create-network", 
        "callback":gui.create_network, "url_args": [], "required_args" : [
            "name", "cloud_network_id"
            ], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/delete-network/{node_id}", 
        "callback":gui.delete_network, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/create-expansion", 
        "callback":gui.create_expansion, "url_args": [], "required_args" : [
            "network_id", "tunnel_id", "intercloud_id_out", "intercloud_id_in"
            ], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/delete-expansion/{node_id}", 
        "callback":gui.delete_expansion, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/create-mptcp", 
        "callback":gui.create_mptcp, "url_args": [], "required_args" : [
            "name", "peer_vni", "agent_id", "peer_id", "peer_ip", 
            "peer_port", "self_port_lan", "self_port_wan"
            ], "opt_args" : []
        },
    {"method":"POST", "endpoint":"/gui/delete-mptcp/{node_id}", 
        "callback":gui.delete_mptcp, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
        },
]

