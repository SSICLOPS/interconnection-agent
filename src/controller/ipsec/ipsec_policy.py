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

import utils

from helpers_n_wrappers import container3, utils3



class Ipsec_policy(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Ipsec_policy")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_POLICY_IPSEC, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_POLICY_IPSEC, self.node_id), True))
        return keys
        

class Ipsec_policy_schema(Schema):
    name = fields.Str()
    node_id = fields.Str(validate=utils.validate_uuid)
    transform_protocol = fields.Str(validate=validate.OneOf(
        ["esp","ah"]
        ))
    encapsulation_mode = fields.Str(validate=validate.OneOf(
        ["tunnel","transport"]
        ))
    encryption_algorithm = fields.Str(validate=validate.OneOf(
        ["aes128","aes192","aes256"]
        ))
    auth_algorithm = fields.Str(validate=validate.OneOf(
        ["sha","sha1","sha256"]
        ))
    pfs = fields.Str(validate=validate.OneOf(
        ["modp1024","modp1536","modp2048","modp3072"]
        ))
    lifetime_value = fields.Integer()
    
    @post_load
    def load_node(self, data):
        return Ipsec_policy(**data)
        


        
        
async def get_ipsec_policies(data_store, amqp, node_id=None):
    ret = utils.get_objects(data_store, amqp, Ipsec_policy_schema, 
        utils.KEY_POLICY_IPSEC, node_id=None
        )
    raise web.HTTPOk(content_type="application/json", text = ret)    
    
async def create_ipsec_policy(data_store, amqp, **kwargs):
    ret, _ = utils.create_object(data_store, amqp, Ipsec_policy_schema, kwargs)
    raise web.HTTPCreated(content_type="application/json", text = ret)
    
    
async def delete_ipsec_policy(data_store, amqp, node_id):
    obj = utils.delete_object(data_store, amqp, node_id, utils.KEY_POLICY_IPSEC)
    data_store.remove(obj)
    raise web.HTTPOk()

