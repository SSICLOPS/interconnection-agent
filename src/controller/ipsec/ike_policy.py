from helpers_n_wrappers import container3, utils3
from aiohttp import web
import uuid
import models
import data_container
import traceback
import logging

from marshmallow import Schema, fields, post_load


class Ike_policy_schema(Schema):
    name = fields.Str()
    node_id = fields.Str()
    ike_version = fields.Str()
    encryption_algorithm = fields.Str()
    auth_algorithm = fields.Str()
    pfs = fields.Str()
    lifetime_value = fields.Str()
    
    @post_load
    def load_node(self, data):
        return Ike_policy(**data)
        

class Ike_policy(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Ike_policy")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((data_container.KEY_POLICY_IKE, False))
        keys.append((self.node_id, True))
        keys.append(((data_container.KEY_POLICY_IKE, self.node_id), True))
        return keys
        
        
def get_ike_policies(data_store, amqp, node_id=None):
    
    schema = Ike_policy_schema()
    if node_id:
        if not data_store.has(node_id):
            raise web.HTTPNotFound(text = "Ike Policy Not Found")
        ike_policy = data_store.get(node_id)
        ike_policies_str = schema.dumps(ike_policy).data
    else:
        ike_policies = data_store.lookup_list(data_container.KEY_POLICY_IKE)
        ike_policies_str = schema.dumps(ike_policies, many=True).data
    raise web.HTTPOk(content_type="application/json",
        text = ike_policies_str
    )
    
    
def create_ike_policy(data_store, amqp, **kwargs):
    schema = Ike_policy_schema()
    ike_policy = schema.load(kwargs).data
    data_store.add(ike_policy)
    ike_policy_str = schema.dumps(ike_policy).data
    data_store.save(ike_policy)
    raise web.HTTPCreated(content_type="application/json",
        text = ike_policy_str
    )
    
    
def delete_ike_policy(data_store, amqp, node_id):
    if not data_store.has(node_id):
        raise web.HTTPNotFound(text = "Ike Policy Not Found")
    if data_store.has((data_container.KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "Ike Policy in use")
    ike_policy = data_store.get(node_id)
    data_store.remove(ike_policy)
    data_store.delete(node_id)
    raise web.HTTPOk()

