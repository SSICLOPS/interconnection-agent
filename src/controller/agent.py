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


import asyncio
import logging
from marshmallow import Schema, fields, post_load, ValidationError, validate

import utils
from tunneling import l2_tunnel, network, expansion, mptcp_proxy
from ipsec import vpn_connection

from helpers_n_wrappers import container3, utils3

class Agent_schema(Schema):
    node_uuid       = fields.Str(validate=utils.validate_uuid)
    vni             = fields.Integer(validate=lambda n: 2<= n <= 4095)
    standalone      = fields.Boolean()
    runtime_id      = fields.Integer()
    mptcp_capable   = fields.Boolean()
    
    
    @post_load
    def load_node(self, data):
        return Agent(**data)


class Agent(container3.ContainerNode):
    def __init__(self, **kwargs):
        super().__init__(name="Agent")
        self.addresses = []
        utils3.set_attributes(self, override = True, **kwargs)
        self.loading = asyncio.Event()
        self.loading.set()
        self.restarting = False

    def lookupkeys(self):
        keys = []
        keys.append((utils.KEY_AGENT, False))
        keys.append(((utils.KEY_AGENT, self.node_uuid), True))
        keys.append((self.node_uuid, True))
        for address in self.addresses:
            keys.append(((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
                address
                ), True))
        return keys

    def update(self, **kwargs):
        utils3.set_attributes(self, override = True, **kwargs)
        
    async def reload(self, data_store, amqp):
        tunnels = []
        connections = []
        expansions = []
        mptcp_proxies = []
        
        #find all tunnels on this node
        for address in self.addresses:
            for tunnel_obj in data_store.lookup_list((utils.KEY_L2_TUNNEL, 
                    utils.KEY_L2_TUNNEL_IP, address
                    ), False, False
                    ):
                if tunnel_obj.deleting:
                    data_store.remove(tunnel_obj)
                else:
                    tunnels.append(tunnel_obj)
        logging.debug("Applying tunnels configuration: {}".format(
            [tunnel_obj.node_id for tunnel_obj in tunnels]
            ))
        
        #For each, create them and find associated connections and expansions
        for tunnel in tunnels:
            for connection_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                    utils.KEY_CONNECTION, tunnel.node_id
                    ), False, False
                    ):
                if connection_obj.deleting:
                    data_store.remove(connection_obj)
                else:
                    connections.append(connection_obj)
            for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                    utils.KEY_EXPANSION, tunnel.node_id
                    ), False, False
                    ):
                if expansion_obj.deleting:
                    data_store.remove(expansion_obj)
                else:
                    expansions.append(expansion_obj)
        
        if self.mptcp_capable:
            mptcp_proxies = data_store.lookup_list((utils.KEY_MPTCP_PROXY, 
                    utils.KEY_AGENT, self.node_uuid), False, False)
            for mptcp_proxy_obj in mptcp_proxies:
                if mptcp_proxy_obj.deleting:
                    data_store.remove(mptcp_proxy_obj)
            mptcp_proxies = data_store.lookup_list((utils.KEY_MPTCP_PROXY, 
                    utils.KEY_AGENT, self.node_uuid), False, False)
                
        self.restarting = False
        
        for tunnel in tunnels:
            await l2_tunnel.send_create_tunnel(data_store, amqp, tunnel,
                no_wait = True)
        
        logging.debug("Applying connections configuration: {}".format(
            [con.node_id for con in connections]
            ))

        #For each connection, create it
        for connection in connections:
            await vpn_connection.send_create_connection(data_store, amqp, 
                connection, no_wait = True
                )
        
        
        #Assume namespaces deleted, host reboot = deletion
        for network_obj in data_store.lookup_list(utils.KEY_NETWORK, 
                False, False):
            if self.node_uuid in network_obj.agents_deployed:
                network_obj.agents_deployed.discard(self.node_uuid)
        
        #Create all the expansions
        for expansion_obj in expansions:
            await expansion.send_create_expansion(data_store, amqp, 
                expansion_obj, no_wait = True
                )
        
        for mptcp_proxy_obj in mptcp_proxies:  
            await mptcp_proxy.send_create_proxy(data_store, amqp, 
                mptcp_proxy_obj, no_wait = True
                )
            
    async def update_tunnels(self, data_store, amqp, old_addresses, new_addresses):
        #Remove the expansions using the tunnels and the tunnels
        for address in old_addresses - new_addresses:
            if not data_store.has((utils.KEY_L2_TUNNEL, utils.KEY_L2_TUNNEL_IP, 
                    address)):
                continue
            for tunnel in data_store.get(utils.KEY_L2_TUNNEL, 
                    utils.KEY_L2_TUNNEL_IP, address):
                for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                        utils.KEY_EXPANSION, tunnel.node_id ), False, False):
                    await expansion.send_delete_expansion(data_store, amqp, 
                        expansion_obj
                        ) 
                await l2_tunnel.send_delete_tunnel(data_store, amqp, tunnel)
        
        self.addresses = payload["addresses"]
        data_store.updatekeys(self)
        
        #add the new tunnels and create the associated expansions
        for address in new_addresses - old_addresses:
            if not data_store.has((utils.KEY_L2_TUNNEL, utils.KEY_L2_TUNNEL_IP, 
                    address)):
                continue
            for tunnel in data_store.get(utils.KEY_L2_TUNNEL, 
                    utils.KEY_L2_TUNNEL_IP, address):
                await l2_tunnel.send_create_tunnel(data_store, amqp, tunnel)
                for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                        utils.KEY_EXPANSION, tunnel.node_id ), False, False):
                    await expansion.send_create_expansion(data_store, amqp,
                        expansion_obj)
                
    async def update_networks(self, data_store, amqp, old_networks, new_networks):
        logging.debug("Updating the networks")
        #Remove expansions for old networks and old networks
        for network_cloud_id in old_networks - new_networks:
            if not data_store.has((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                network_cloud_id )):
                continue
            network_obj = data_store.get((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                network_cloud_id 
                ))
            for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                    utils.KEY_EXPANSION, network_obj.node_id ), False, False):
                await expansion.send_delete_expansion(data_store, amqp,
                    expansion_obj) 
            await network.remove_all_propagated_network(data_store, amqp, network_obj)
        
        self.networks = new_networks
        data_store.updatekeys(self)
        
        #Create the expansions for the new networks
        for network_cloud_id in new_networks - old_networks:
            if not data_store.has((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                network_cloud_id )):
                continue
            network_obj = data_store.get((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                network_cloud_id 
                ))
            for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                    utils.KEY_EXPANSION, network_obj.node_id ), False, False):
                await expansion.send_create_expansion(data_store, amqp,
                    expansion_obj)