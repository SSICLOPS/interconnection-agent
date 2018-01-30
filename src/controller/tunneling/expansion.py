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
from marshmallow import Schema, fields, post_load, ValidationError, validate
import logging


import utils
from tunneling import network


from helpers_n_wrappers import container3, utils3

#Mapping from objects to dictionnary for AMQP
_expansion_args = {
    "node_id": ("expansion", "node_id"),
    "network_id": ("network", "node_id"),
    "cloud_network_id": ("network", "cloud_network_id"),
    "peer_vni": ("tunnel", "peer_vni"),
    "peer_name": ("tunnel", "name"),
    "tunnel_id": ("tunnel", "node_id"),
    "inter_id_in": ("expansion", "intercloud_id_in"),
    "inter_id_out": ("expansion", "intercloud_id_out")
}


def convert_expansion(**kwargs):
    con_args = {}
    for key in _expansion_args:
        object = kwargs[_expansion_args[key][0]]
        try:
            value = getattr(object, _expansion_args[key][1])
            con_args[key]=value
        except AttributeError:
            pass
    return con_args



class Expansion_schema(Schema):
    node_id           = fields.Str(validate=utils.validate_uuid)
    network_id        = fields.Str(validate=utils.network_validator)
    tunnel_id         = fields.Str(validate=utils.l2_validator)
    intercloud_id_out = fields.Int(validate=validate.Range(2,4095))
    intercloud_id_in  = fields.Int(validate=validate.Range(2,4095))

    
    @post_load
    def load_node(self, data):
        return Expansion(**data)
        

class Expansion(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        self.applied = False
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Expansion")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_EXPANSION, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_EXPANSION, self.node_id), True))
        keys.append(((utils.KEY_EXPANSION, self.network_id, self.tunnel_id), 
            True
            ))
        keys.append(((utils.KEY_IN_USE, self.network_id), False))
        keys.append(((utils.KEY_IN_USE, utils.KEY_EXPANSION, self.network_id), 
            False
            ))
        
        keys.append(((utils.KEY_IN_USE, self.tunnel_id), 
            False
            ))
        keys.append(((utils.KEY_IN_USE, utils.KEY_EXPANSION, self.tunnel_id), 
            False
            ))
        return keys
        
        
async def get_expansions(data_store, amqp, node_id=None, network_id=None):
    if network_id:
        if not data_store.has((utils.KEY_NETWORK, network_id)):
            raise web.HTTPNotFound(text = "Network Not Found")
        expansions = data_store.lookup_list((utils.KEY_IN_USE, network_id))
        ret = Expansion_schema().dumps(expansions, many=True).data
    else:
        ret = utils.get_objects(data_store, amqp, Expansion_schema, 
            utils.KEY_EXPANSION, node_id=None
            )
    raise web.HTTPOk(content_type="application/json", text = ret)
    
    
async def create_expansion(data_store, amqp, **kwargs):
    ret, expansion = utils.create_object(data_store, amqp, Expansion_schema, kwargs)
    await send_create_expansion(data_store, amqp, expansion)
    raise web.HTTPAccepted(content_type="application/json", text = ret)
    
    
async def delete_expansion(data_store, amqp, node_id):
    expansion = utils.delete_object(data_store, amqp, node_id, utils.KEY_EXPANSION)
    await send_delete_expansion(data_store, amqp, expansion)
    raise web.HTTPAccepted()
    
 
    
    
    
async def send_create_expansion(data_store, amqp, expansion):
    await send_action_expansion(data_store, amqp, utils.ACTION_ADD_EXPANSION, 
        expansion
        )

async def send_delete_expansion(data_store, amqp, expansion):
    await send_action_expansion(data_store, amqp, utils.ACTION_DEL_EXPANSION, 
        expansion
        ) 
    
async def send_action_expansion(data_store, amqp, action, expansion):
    #Get the elements to send the action
    tunnel = data_store.get(expansion.tunnel_id)
    network_obj = data_store.get(expansion.network_id)
    
    if not data_store.has((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
            tunnel.self_ip )):
        return
        
    
    agent_amqp = data_store.get((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
        tunnel.self_ip
        ))
    
    #If we delete an expansion that was not applied, this is a No op.
    if action == utils.ACTION_DEL_EXPANSION and not expansion.applied:
        return
    
    #If we want to add an expansion in a node where the network is not, No op.
    if ( action == utils.ACTION_ADD_EXPANSION and 
            network_obj.cloud_network_id not in agent_amqp.networks and
            not agent_amqp.standalone
            ):
        logging.debug("Expansion {} not applicable, network not extended".format(
            expansion.node_id
            ))
        return
        
    #Pre-process the data
    data = convert_expansion(expansion = expansion, tunnel = tunnel,
        network = network_obj
        )
    
    #If we add the expansion, but the network had not been yet propagated on 
    #that agent, propagate it now. If removing, flip the flag
    if action == utils.ACTION_ADD_EXPANSION:
        if agent_amqp.node_uuid not in network_obj.agents_deployed:
            await network.send_create_network(data_store, amqp, agent_amqp, 
                network_obj
                )
        expansion.applied = True
    else:
        expansion.applied = False
    
    #Send the actual action
    payload = {"operation":action,
        "kwargs": data
        }
    await amqp.publish_action(payload=payload, 
        node = agent_amqp, callback = utils.ack_callback,
        )
 