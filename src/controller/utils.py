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

from marshmallow import ValidationError
import uuid
import ipaddress
import functools
from aiohttp import web
import logging

KEY_IN_USE = "KEY_IN_USE"
KEY_AGENT = "KEY_AGENT"
KEY_AGENT_IP = "KEY_AGENT_IP"
KEY_POLICY_IKE = "KEY_POLICY_IKE"
KEY_POLICY_IPSEC = "KEY_POLICY_IPSEC"
KEY_L2_TUNNEL = "KEY_L2_TUNNEL"
KEY_L2_TUNNEL_IP = "KEY_L2_TUNNEL_IP"
KEY_CONNECTION = "KEY_CONNECTION"
KEY_NETWORK = "KEY_NETWORK"
KEY_CLOUD_NET_ID = "KEY_CLOUD_NET_ID"
KEY_EXPANSION = "KEY_EXPANSION"
KEY_MPTCP_PROXY = "KEY_MPTCP_PROXY"
KEY_MPTCP_PEER_VNI = "KEY_MPTCP_PEER_VNI"


ACTION_ACK = "Ack"
ACTION_NACK = "Nack"
ACTION_NO_OP = "No-op"
ACTION_DIE = "Die"
ACTION_ADD_TUNNEL = "Add-tunnel"
ACTION_DEL_TUNNEL = "Del-tunnel"
ACTION_ADD_CONNECTION = "Add-connection"
ACTION_DEL_CONNECTION = "Del-connection"
ACTION_ADD_EXPANSION = "Add-expansion"
ACTION_DEL_EXPANSION = "Del-expansion"
ACTION_ADD_NETWORK = "Add-network"
ACTION_DEL_NETWORK = "Del-network"
ACTION_ADD_PROXY = "Add-proxy"
ACTION_DEL_PROXY = "Del-proxy"



def validate_uuid(uuid_str):
    try:
        uuid.UUID(uuid_str, version=4)
    except ValueError:
        raise ValidationError("{} is not a correct UUID".format(uuid_str))
    return True

def validate_ip_address(address):
    try:
        ipaddress.ip_address(address)
    except ValueError:
        raise ValidationError("Incorrect IP : {}".format(address))
    return True
    
class Data_store_validator(object):
    
    def __init__(self):
        self.data_store = None
        
    def add_data_store(self, data_store):
        self.data_store = data_store
        
    def check_in_data(self, key, node_id):
        validate_uuid(node_id)
        if not self.data_store:
            raise ValidationError("No data structure initialized")
        if not self.data_store.has((key, node_id)):
            raise ValidationError("{} not found".format(node_id))
        return True
        
data_store_validator = Data_store_validator()
l2_validator = functools.partial(data_store_validator.check_in_data,
    KEY_L2_TUNNEL
    )
ike_validator = functools.partial(data_store_validator.check_in_data,
    KEY_POLICY_IKE
    )
ipsec_validator = functools.partial(data_store_validator.check_in_data,
    KEY_POLICY_IPSEC
    )
network_validator = functools.partial(data_store_validator.check_in_data,
    KEY_NETWORK
    )
agent_validator = functools.partial(data_store_validator.check_in_data,
    KEY_AGENT
    )


def get_objects(data_store, amqp, obj_schema, key, node_id=None): 
    schema = obj_schema()
    if node_id:
        if not data_store.has((key, node_id)):
            raise web.HTTPNotFound(text = "Ike Policy Not Found")
        objs = data_store.get(node_id)
        objs_str = schema.dumps(objs).data
    else:
        objs = data_store.lookup_list(key)
        objs_str = schema.dumps(objs, many=True).data
    return objs_str
    
    
def create_object(data_store, amqp, obj_schema, kwargs):
    schema = obj_schema()
    obj, errors = schema.load(kwargs)
    if errors:
        raise web.HTTPBadRequest( content_type="application/json",
            text = "{}".format(errors)
            )
    try:
        data_store.add(obj)
    except KeyError as e:
        raise web.HTTPConflict(text = "{}".format(e.args))
    obj_str = schema.dumps(obj).data
    data_store.save(obj)
    return obj_str, obj
    
def delete_object(data_store, amqp, node_id, key):
    if not data_store.has((key, node_id)):
        raise web.HTTPNotFound(text = "Object Not Found")
    if data_store.has((KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "Object in use")
    obj = data_store.get(node_id)
    data_store.delete(node_id)
    return obj
    
async def ack_callback(data_store, payload, action):
    obj = data_store.lookup(action["kwargs"]["node_id"], False, False)
    if obj:
        if payload["operation"] == ACTION_NACK:
            obj.status = "Failed"
        elif action["operation"].startswith("Add"):
            if payload["operation"] == ACTION_ACK:
                obj.status = "Ok"
        elif action["operation"].startswith("Del"):
            data_store.remove(obj)
    success = "un" if payload["operation"] == ACTION_NACK else ""
    logging.debug("{} completed {}successfully for {}".format(
        action["operation"], success, action["kwargs"]["node_id"]
        ))