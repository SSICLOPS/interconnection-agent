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


class Mptcp_proxy_schema(Schema):
    name            = fields.Str()
    node_id         = fields.Str(validate=utils.validate_uuid)
    peer_vni        = fields.Integer(validate=lambda n: 2<= n <= 4095)
    agent_id        = fields.Str(validate=utils.agent_validator)
    peer_id         = fields.Str(validate=utils.validate_uuid)
    peer_ip         = fields.Str(validate=utils.validate_ip_address)
    peer_port       = fields.Integer(validate=lambda n: 1<= n <= 65535)
    self_port_lan   = fields.Integer(validate=lambda n: 1<= n <= 65535)
    self_port_wan   = fields.Integer(validate=lambda n: 1<= n <= 65535)
    
    
    @post_load
    def load_node(self, data):
        return Mptcp_proxy(**data)
        

class Mptcp_proxy(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Mptcp_proxy")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_MPTCP_PROXY, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_MPTCP_PROXY, self.node_id), True))
        keys.append(((utils.KEY_MPTCP_PROXY, utils.KEY_AGENT, self.agent_id), 
            False
            ))
        keys.append(((utils.KEY_MPTCP_PROXY, utils.KEY_MPTCP_PEER_VNI, 
                self.peer_vni
                ), True
            ))
        return keys
        

        
        
async def get_mptcp_proxies(data_store, amqp, node_id=None):
    ret = utils.get_objects(data_store, amqp, Mptcp_proxy_schema, 
        utils.KEY_MPTCP_PROXY, node_id=None
        )
    raise web.HTTPOk(content_type="application/json", text = ret)
    
    
async def create_mptcp_proxy(data_store, amqp, **kwargs):
    ret, mptcp_proxy = utils.create_object(data_store, amqp, Mptcp_proxy_schema, kwargs)
    await send_create_proxy(data_store, amqp, mptcp_proxy)
    raise web.HTTPAccepted(content_type="application/json",
        text = ret
    )
    
    
async def delete_mptcp_proxy(data_store, amqp, node_id):
    mptcp_proxy = utils.delete_object(data_store, amqp, node_id, utils.KEY_MPTCP_PROXY)
    await send_delete_proxy(data_store, amqp, mptcp_proxy)
    raise web.HTTPAccepted()
    
async def send_create_proxy(data_store, amqp, mptcp_proxy):
    await send_action_proxy(data_store, amqp, utils.ACTION_ADD_PROXY, 
        mptcp_proxy
        )

async def send_delete_proxy(data_store, amqp, mptcp_proxy):
    await send_action_proxy(data_store, amqp, utils.ACTION_DEL_PROXY, 
        mptcp_proxy
        ) 

    
async def send_action_proxy(data_store, amqp, action, mptcp_proxy):
    if not data_store.has((utils.KEY_AGENT, mptcp_proxy.agent_id)):
        return
    agent_amqp = data_store.get((utils.KEY_AGENT, mptcp_proxy.agent_id
        ))
    payload = {"operation":action,
        "kwargs": Mptcp_proxy_schema().dump(mptcp_proxy).data
        }
    await amqp.publish_action(payload=payload, 
        node = agent_amqp, callback = utils.ack_callback,
        )
    
 


