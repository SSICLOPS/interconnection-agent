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

from helpers_n_wrappers import container3, utils3


class L2_tunnel_schema(Schema):
    name            = fields.Str()
    node_id         = fields.Str(validate=utils.validate_uuid)
    self_ip         = fields.Str(validate=utils.validate_ip_address)
    peer_id         = fields.Str(validate=utils.validate_uuid)
    peer_ip         = fields.Str(validate=utils.validate_ip_address)
    peer_public_ip  = fields.Str(validate=utils.validate_ip_address)
    type            = fields.Str(validate=validate.OneOf(["gre","vxlan"]))
    enabled         = fields.Boolean()
    peer_vni        = fields.Integer(validate=lambda n: 2<= n <= 4095)
    
    @post_load
    def load_node(self, data):
        return L2_tunnel(**data)
        

class L2_tunnel(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="L2_tunnel")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_L2_TUNNEL, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_L2_TUNNEL, self.node_id), True))
        keys.append(((utils.KEY_L2_TUNNEL, utils.KEY_L2_TUNNEL_IP, self.self_ip),
            False
            ))
        return keys
        

        
        
async def get_l2_tunnels(data_store, amqp, node_id=None):
    ret = utils.get_objects(data_store, amqp, L2_tunnel_schema, 
        utils.KEY_L2_TUNNEL, node_id=None
        )
    raise web.HTTPOk(content_type="application/json", text = ret)
    
    
async def create_l2_tunnel(data_store, amqp, **kwargs):
    ret, l2_tunnel = utils.create_object(data_store, amqp, L2_tunnel_schema, kwargs)
    await send_create_tunnel(data_store, amqp, l2_tunnel)
    raise web.HTTPAccepted(content_type="application/json",
        text = ret
    )
    
    
async def delete_l2_tunnel(data_store, amqp, node_id):
    l2_tunnel = utils.delete_object(data_store, amqp, node_id, utils.KEY_L2_TUNNEL)
    await send_delete_tunnel(data_store, amqp, l2_tunnel)
    raise web.HTTPAccepted()
    
async def send_create_tunnel(data_store, amqp, tunnel):
    await send_action_tunnel(data_store, amqp, utils.ACTION_ADD_TUNNEL, tunnel)

async def send_delete_tunnel(data_store, amqp, tunnel):
    await send_action_tunnel(data_store, amqp, utils.ACTION_DEL_TUNNEL, tunnel) 

    
async def send_action_tunnel(data_store, amqp, action, tunnel):
    if not data_store.has((utils.KEY_AGENT, utils.KEY_AGENT_IP, tunnel.self_ip)):
        return
    agent_amqp = data_store.get((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
        tunnel.self_ip
        ))
    payload = {"operation":action,
        "kwargs": L2_tunnel_schema().dump(tunnel).data
        }
    await amqp.publish_action(payload=payload, 
        node = agent_amqp, callback = utils.ack_callback,
        )
    
 


