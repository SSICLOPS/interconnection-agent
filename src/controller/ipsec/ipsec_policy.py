from helpers_n_wrappers import container3, utils3
from aiohttp import web
import uuid
import models
import utils
import traceback
import logging

from marshmallow import Schema, fields, post_load, ValidationError

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
    transform_protocol = fields.Str(validate=utils.create_validation_str([
        "esp","ah"
    ]))
    encapsulation_mode = fields.Str(validate=utils.create_validation_str([
        "tunnel","transport"
    ]))
    encryption_algorithm = fields.Str(validate=utils.create_validation_str([
        "aes128","aes192","aes256",
    ]))
    auth_algorithm = fields.Str(validate=utils.create_validation_str([
        "sha","sha1","sha256"
    ]))
    pfs = fields.Str(validate=utils.create_validation_str([
        "modp1024","modp1536","modp2048","modp3072"
    ]))
    lifetime_value = fields.Number()
    
    @post_load
    def load_node(self, data):
        return Ipsec_policy(**data)
        


        
        
async def get_ipsec_policies(data_store, amqp, node_id=None):
    
    schema = Ipsec_policy_schema()
    if node_id:
        if not data_store.has((utils.KEY_POLICY_IPSEC, self.node_id)):
            raise web.HTTPNotFound(text = "Ike Policy Not Found")
        ipsec_policy = data_store.get(node_id)
        ipsec_policies_str = schema.dumps(ipsec_policy).data
    else:
        ipsec_policies = data_store.lookup_list(utils.KEY_POLICY_IPSEC)
        ipsec_policies_str = schema.dumps(ipsec_policies, many=True).data
    raise web.HTTPOk(content_type="application/json",
        text = ipsec_policies_str
    )
    
    
async def create_ipsec_policy(data_store, amqp, **kwargs):
    schema = Ipsec_policy_schema()
    ipsec_policy, errors = schema.load(kwargs)
    if errors:
        raise web.HTTPBadRequest( content_type="application/json",
            text = "{}".format(errors)
        )
    data_store.add(ipsec_policy)
    ipsec_policy_str = schema.dumps(ipsec_policy).data
    data_store.save(ipsec_policy)
    raise web.HTTPCreated(content_type="application/json",
        text = ipsec_policy_str
    )
    
    
async def delete_ipsec_policy(data_store, amqp, node_id):
    if not data_store.has((utils.KEY_POLICY_IPSEC, self.node_id)):
        raise web.HTTPNotFound(text = "Ipsec Policy Not Found")
    if data_store.has((utils.KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "Ipsec Policy in use")
    ipsec_policy = data_store.get(node_id)
    data_store.remove(ipsec_policy)
    data_store.delete(node_id)
    raise web.HTTPOk()

