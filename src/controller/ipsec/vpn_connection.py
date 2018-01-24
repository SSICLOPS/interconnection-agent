from helpers_n_wrappers import container3, utils3
from aiohttp import web
import uuid
import models
import utils
import traceback
import logging

from marshmallow import Schema, fields, post_load, ValidationError

_jinja_con_args = {
    "node_id": ("connection", "node_id"),
    "dpd_action": ("connection", "dpd_action"),
    "dpd_interval": ("connection", "dpd_interval"),
    "dpd_timeout": ("connection", "dpd_timeout"),
    "self_ip": ("tunnel", "self_ip"),
    "peer_ip": ("tunnel", "peer_ip"),
    "peer_public_ip": ("tunnel", "peer_public_ip"),
    "peer_id": ("tunnel", "peer_id"),
    "ike_version": ("ike", "ike_version"),
    "ike_encryption_algorithm": ("ike", "encryption_algorithm"),
    "ike_auth_algorithm": ("ike", "auth_algorithm"),
    "ike_pfs": ("ike", "pfs"),
    "ike_lifetime": ("ike", "lifetime_value"),
    "ipsec_transform_protocol": ("ipsec", "transform_protocol"),
    "ipsec_encryption_algorithm": ("ipsec", "encryption_algorithm"),
    "ipsec_auth_algorithm": ("ipsec", "auth_algorithm"),
    "ipsec_pfs": ("ipsec", "pfs"),
    "ipsec_lifetime": ("ipsec", "lifetime_value"),
    "ipsec_encapsulation_mode": ("ipsec", "encapsulation_mode"),
    "secret": ("connection", "secret"),
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
    con_args["self_id"]=kwargs["self_id"]
    return con_args

class Vpn_connection(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Vpn_connection")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_CONNECTION, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_CONNECTION, self.node_id), True))
        keys.append(((utils.KEY_IN_USE, self.tunnel_id), False))
        keys.append(((utils.KEY_IN_USE, self.ike_policy_id), False))
        keys.append(((utils.KEY_IN_USE, self.ipsec_policy_id), False))
        
        return keys
    

class Vpn_connection_schema(Schema):
    name = fields.Str()
    node_id = fields.Str(validate=utils.validate_uuid)
    tunnel_id = fields.Str(validate=utils.l2_validator)
    ike_policy_id = fields.Str(validate=utils.ike_validator)
    ipsec_policy_id = fields.Str(validate=utils.ipsec_validator)
    dpd_action = fields.Str(validate=utils.create_validation_str([
        "hold"
    ]))
    dpd_interval = fields.Integer()
    dpd_timeout = fields.Integer()
    initiator = fields.Str(validate=utils.create_validation_str([
        "start"
    ]))
    secret = fields.Str()
    
    
    @post_load
    def load_node(self, data):
        return Vpn_connection(**data)
        
        
async def get_vpn_connections(data_store, amqp, node_id=None):
    
    schema = Vpn_connection_schema()
    if node_id:
        if not data_store.has((utils.KEY_CONNECTION, node_id)):
            raise web.HTTPNotFound(text = "VPN connection Not Found")
        vpn_connection = data_store.get(node_id)
        vpn_connections_str = schema.dumps(vpn_connection).data
    else:
        vpn_connections = data_store.lookup_list(utils.KEY_CONNECTION)
        vpn_connections_str = schema.dumps(vpn_connections, many=True).data
    raise web.HTTPOk(content_type="application/json",
        text = vpn_connections_str
    )
    
    
async def create_vpn_connection(data_store, amqp, **kwargs):
    schema = Vpn_connection_schema()
    vpn_connection, errors = schema.load(kwargs)
    if errors:
        raise web.HTTPBadRequest( content_type="application/json",
            text = "{}".format(errors)
        )
    data_store.add(vpn_connection)
    send_create_connection(data_store, amqp, vpn_connection)
    vpn_connection_str = schema.dumps(vpn_connection).data
    data_store.save(vpn_connection)
    raise web.HTTPCreated(content_type="application/json",
        text = vpn_connection_str
    )
    
    
async def delete_vpn_connection(data_store, amqp, node_id):
    if not data_store.has((utils.KEY_CONNECTION, node_id)):
        raise web.HTTPNotFound(text = "Vpn connection Not Found")
    if data_store.has((utils.KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "Vpn connection in use")
    vpn_connection = data_store.get(node_id)
    data_store.remove(vpn_connection)
    data_store.delete(vpn_connection)
    send_delete_connection(data_store, amqp, vpn_connection)
    raise web.HTTPOk()
    

async def send_create_connection(data_store, amqp, connection):
    tunnel = data_store.get(connection.tunnel_id)
    ike = data_store.get(connection.ike_policy_id)
    ipsec = data_store.get(connection.ipsec_policy_id)
    if not data_store.has((utils.KEY_AGENT, utils.KEY_AGENT_IP, tunnel.self_ip)):
        return
    agent_amqp = data_store.get((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
        tunnel.self_ip
    ))
    data = convert_con_template(connection=connection, tunnel = tunnel,
        ike = ike, ipsec = ipsec, self_id = agent_amqp.node_uuid
    )
    await send_action_connection(agent_amqp, amqp, utils.ACTION_ADD_CONNECTION, 
        data
    )

async def send_delete_connection(data_store, amqp, connection):
    data = {"node_id":connection.node_id}
    tunnel = data_store.get(connection.tunnel_id)
    if not data_store.has((utils.KEY_AGENT, utils.KEY_AGENT_IP, tunnel.self_ip)):
        return
    agent_amqp = data_store.get((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
        tunnel.self_ip
    ))
    await send_action_connection(agent_amqp, amqp, utils.ACTION_DEL_CONNECTION, 
        data
    ) 

async def ack_callback(payload, action):
    logging.debug("{} completed {}successfully for connection {}".format(
        "Setup" if action["operation"]== utils.ACTION_ADD_CONNECTION else "Removal", 
        "un" if payload["operation"] == utils.ACTION_NACK else "",
        action["kwargs"]["node_id"]
    ))
    
async def send_action_connection(agent_amqp, amqp, action, connection_args):
    payload = {"operation":action,
        "kwargs": connection_args
    }
    await amqp.publish_action(payload=payload, 
        node_uuid = agent_amqp.node_uuid, callback = ack_callback,
    )
