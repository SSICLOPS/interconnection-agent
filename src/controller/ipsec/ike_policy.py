from helpers_n_wrappers import container3, utils3
from aiohttp import web
import uuid
import models
import utils
import traceback
import logging

from marshmallow import Schema, fields, post_load, ValidationError

class Ike_policy(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Ike_policy")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_POLICY_IKE, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_POLICY_IKE, self.node_id), True))
        return keys
    

class Ike_policy_schema(Schema):
    name = fields.Str()
    node_id = fields.Str(validate=utils.validate_uuid)
    ike_version = fields.Str(validate=utils.create_validation_str([
        "ikev1","ikev2"
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
    lifetime_value = fields.Integer()
    
    @post_load
    def load_node(self, data):
        return Ike_policy(**data)
        
        
async def get_ike_policies(data_store, amqp, node_id=None):
    
    schema = Ike_policy_schema()
    if node_id:
        if not data_store.has((utils.KEY_POLICY_IKE, node_id)):
            raise web.HTTPNotFound(text = "Ike Policy Not Found")
        ike_policy = data_store.get(node_id)
        ike_policies_str = schema.dumps(ike_policy).data
    else:
        ike_policies = data_store.lookup_list(utils.KEY_POLICY_IKE)
        ike_policies_str = schema.dumps(ike_policies, many=True).data
    raise web.HTTPOk(content_type="application/json",
        text = ike_policies_str
    )
    
    
async def create_ike_policy(data_store, amqp, **kwargs):
    schema = Ike_policy_schema()
    ike_policy, errors = schema.load(kwargs)
    if errors:
        raise web.HTTPBadRequest( content_type="application/json",
            text = "{}".format(errors)
        )
    data_store.add(ike_policy)
    ike_policy_str = schema.dumps(ike_policy).data
    data_store.save(ike_policy)
    raise web.HTTPCreated(content_type="application/json",
        text = ike_policy_str
    )
    
    
async def delete_ike_policy(data_store, amqp, node_id):
    if not data_store.has((utils.KEY_POLICY_IKE, node_id)):
        raise web.HTTPNotFound(text = "Ike Policy Not Found")
    if data_store.has((utils.KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "Ike Policy in use")
    ike_policy = data_store.get(node_id)
    data_store.remove(ike_policy)
    data_store.delete(node_id)
    raise web.HTTPOk()
    


