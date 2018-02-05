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
import logging
from marshmallow import Schema, fields, post_load, ValidationError, validate


from helpers_n_wrappers import container3, utils3
import utils


#translate objects into dictionnary for AMQP
_jinja_con_args = {
    "name": ("connection", "name"),
    "node_id": ("connection", "node_id"),
    "dpd_action": ("connection", "dpd_action"),
    "dpd_interval": ("connection", "dpd_interval"),
    "dpd_timeout": ("connection", "dpd_timeout"),
    "initiator": ("connection", "initiator"),
    "self_ip": ("tunnel", "self_ip"),
    "peer_ip": ("tunnel", "peer_ip"),
    "peer_name": ("tunnel", "name"),
    "peer_public_ip": ("tunnel", "peer_public_ip"),
    "peer_id": ("tunnel", "peer_id"),
    "ike_version": ("ike", "ike_version"),
    "ike_encryption_algorithm": ("ike", "encryption_algorithm"),
    "ike_auth_algorithm": ("ike", "auth_algorithm"),
    "ike_pfs": ("ike", "pfs"),
    "ike_lifetime": ("ike", "lifetime_value"),
    "ike_name": ("ike", "name"),
    "ipsec_transform_protocol": ("ipsec", "transform_protocol"),
    "ipsec_encryption_algorithm": ("ipsec", "encryption_algorithm"),
    "ipsec_auth_algorithm": ("ipsec", "auth_algorithm"),
    "ipsec_pfs": ("ipsec", "pfs"),
    "ipsec_lifetime": ("ipsec", "lifetime_value"),
    "ipsec_encapsulation_mode": ("ipsec", "encapsulation_mode"),
    "ipsec_name": ("ipsec", "name"),
    "secret": ("connection", "secret"),
    "status": ("connection", "status"),
}

def convert_con_template(**kwargs):
    con_args = {}
    for key in _jinja_con_args:
        object = kwargs[_jinja_con_args[key][0]]
        try:
            value = getattr(object, _jinja_con_args[key][1])
            con_args[key]=value
        except AttributeError:
            pass
    if "self_id" in con_args:
        con_args["self_id"]=kwargs["self_id"]
    return con_args

class Vpn_connection(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Vpn_connection")
        utils3.set_attributes(self, override = False, status="Pending",
            deleting = False)
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_CONNECTION, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_CONNECTION, self.node_id), True))
        keys.append(((utils.KEY_IN_USE, self.tunnel_id), False))
        keys.append(((utils.KEY_IN_USE, utils.KEY_CONNECTION, self.tunnel_id), 
            False
            ))
        keys.append(((utils.KEY_IN_USE, self.ike_policy_id), False))
        keys.append(((utils.KEY_IN_USE, utils.KEY_CONNECTION, self.ike_policy_id), 
            False
            ))
        keys.append(((utils.KEY_IN_USE, self.ipsec_policy_id), False))
        keys.append(((utils.KEY_IN_USE, utils.KEY_CONNECTION, self.ipsec_policy_id), 
            False
            ))
        
        return keys
    

class Vpn_connection_schema(Schema):
    name = fields.Str()
    node_id = fields.Str(validate=utils.validate_uuid)
    tunnel_id = fields.Str(validate=utils.l2_validator)
    ike_policy_id = fields.Str(validate=utils.ike_validator)
    ipsec_policy_id = fields.Str(validate=utils.ipsec_validator)
    dpd_action = fields.Str(validate=validate.OneOf(["hold"]))
    dpd_interval = fields.Integer()
    dpd_timeout = fields.Integer()
    initiator = fields.Str(validate=validate.OneOf(["start"]))
    secret = fields.Str()
    status = fields.Str(validate=validate.OneOf(
        ["Pending", "Ok", "Deleting", "Failed"]
        ))
    deleting = fields.Boolean()
    
    
    @post_load
    def load_node(self, data):
        return Vpn_connection(**data)
        
        
async def get_vpn_connections(data_store, amqp, node_id=None):
    ret = utils.get_objects(data_store, amqp, Vpn_connection_schema, 
        utils.KEY_CONNECTION, node_id=None
        )
    raise web.HTTPOk(content_type="application/json", text = ret)
    
    
async def create_vpn_connection(data_store, amqp, **kwargs):
    ret, vpn_connection = utils.create_object(data_store, amqp, 
        Vpn_connection_schema, kwargs
        )
    await send_create_connection(data_store, amqp, vpn_connection)
    raise web.HTTPAccepted(content_type="application/json",
        text = ret
    )
    
    
async def delete_vpn_connection(data_store, amqp, node_id):
    vpn_connection = utils.delete_object(data_store, amqp, node_id, 
        utils.KEY_CONNECTION
        )
    vpn_connection.status = "Deleting"
    vpn_connection.deleting = True
    data_store.save(vpn_connection)
    await send_delete_connection(data_store, amqp, vpn_connection)
    raise web.HTTPAccepted()
    

async def send_create_connection(data_store, amqp, connection, no_wait = False):
    tunnel = data_store.get(connection.tunnel_id)
    if not data_store.has((utils.KEY_AGENT, utils.KEY_AGENT_IP, tunnel.self_ip)):
        return
    
    ike = data_store.get(connection.ike_policy_id)
    ipsec = data_store.get(connection.ipsec_policy_id)
    agent_amqp = data_store.get((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
        tunnel.self_ip
        ))
    
    data = convert_con_template(connection=connection, tunnel = tunnel,
        ike = ike, ipsec = ipsec, self_id = agent_amqp.node_uuid
        )
    
    await _send_action_connection(agent_amqp, amqp, utils.ACTION_ADD_CONNECTION, 
        data, no_wait
        )

async def send_delete_connection(data_store, amqp, connection, no_wait = False):
    data = {"node_id":connection.node_id}
    tunnel = data_store.get(connection.tunnel_id)
    if not data_store.has((utils.KEY_AGENT, utils.KEY_AGENT_IP, tunnel.self_ip)):
        return
    agent_amqp = data_store.get((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
        tunnel.self_ip
        ))
    
    await _send_action_connection(agent_amqp, amqp, utils.ACTION_DEL_CONNECTION, 
        data, no_wait
        ) 

    
async def _send_action_connection(agent_amqp, amqp, action, connection_args, 
        no_wait):
    payload = {"operation":action,
        "kwargs": connection_args
        }
    await amqp.publish_action(payload=payload, 
        node = agent_amqp, callback = utils.ack_callback, no_wait = no_wait
        )
