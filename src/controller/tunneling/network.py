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

from aiohttp import web
import uuid
from marshmallow import Schema, fields, post_load, ValidationError
import traceback
import logging


import utils

from helpers_n_wrappers import container3, utils3


class Network_schema(Schema):
    name             = fields.Str()
    node_id          = fields.Str(validate=utils.validate_uuid)
    cloud_network_id = fields.Int() #segmentation ID from OpenStack or 
    # vlan ID if standalone
    
    @post_load
    def load_node(self, data):
        return Network(**data)
        

class Network(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        self.agents_deployed = set()
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Network")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_NETWORK, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_NETWORK, self.node_id), True))
        keys.append(((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                self.cloud_network_id
                ), True
            ))
        return keys
        

        
        
async def get_networks(data_store, amqp, node_id=None):
    ret = utils.get_objects(data_store, amqp, Network_schema, utils.KEY_NETWORK, 
        node_id=None
        )
    raise web.HTTPOk(content_type="application/json", text = ret)
    
    
async def create_network(data_store, amqp, **kwargs):
    ret = utils.create_object(data_store, amqp, Network_schema, kwargs)
    raise web.HTTPAccepted(content_type="application/json", text = ret)
    
    
async def delete_network(data_store, amqp, node_id):
    utils.delete_object(data_store, amqp, node_id, utils.KEY_NETWORK)
    remove_all_propagated_network(data_store, amqp, network)
    raise web.HTTPAccepted()
    
   
    
async def send_create_network(data_store, amqp, agent, network):
    await send_action_network(data_store, amqp, utils.ACTION_ADD_NETWORK, 
        network, agent
        )
    network.agents_deployed.add(agent.node_uuid)

async def send_delete_network(data_store, amqp, agent, network):
    await send_action_network(data_store, amqp, utils.ACTION_DEL_NETWORK, 
        network, agent
        ) 
    network.agents_deployed.discard(agent.node_uuid)
    
async def remove_all_propagated_network(data_store, amqp, network):
    agents_list = list(network.agents_deployed)
    for agent_uuid in agents_list:
        agent = data_store.get(agent_uuid)
        await send_delete_network(data_store, amqp, agent, network)
    
async def send_action_network(data_store, amqp, action, network, agent_amqp):
    payload = {"operation":action,
        "kwargs": Network_schema().dump(network).data
    }
    await amqp.publish_action(payload=payload, 
        node = agent_amqp, callback = utils.ack_callback,
    )