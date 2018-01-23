from helpers_n_wrappers import container3, utils3
from aiohttp import web
import uuid

import utils
import traceback
import logging

from marshmallow import Schema, fields, post_load, ValidationError


class L2_tunnel_schema(Schema):
    name            = fields.Str()
    node_id         = fields.Str(validate=utils.validate_uuid)
    self_ip         = fields.Str(validate=utils.validate_ip_address)
    peer_id         = fields.Str(validate=utils.validate_uuid)
    peer_ip         = fields.Str(validate=utils.validate_ip_address)
    peer_public_ip  = fields.Str(validate=utils.validate_ip_address)
    type            = fields.Str(validate=utils.create_validation_str([
        "gre","vxlan"
    ]))
    mtu             = fields.Integer()
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
            True
        ))
        return keys
        

        
        
async def get_l2_tunnels(data_store, amqp, node_id=None):
    
    schema = L2_tunnel_schema()
    if node_id:
        if not data_store.has((utils.KEY_L2_TUNNEL, node_id)):
            raise web.HTTPNotFound(text = "L2 Tunnel Not Found")
        l2_tunnel = data_store.get(node_id)
        l2_tunnels_str = schema.dumps(l2_tunnel).data
    else:
        l2_tunnels = data_store.lookup_list(utils.KEY_L2_TUNNEL)
        l2_tunnels_str = schema.dumps(l2_tunnels, many=True).data
    raise web.HTTPOk(content_type="application/json",
        text = l2_tunnels_str
    )
    
    
async def create_l2_tunnel(data_store, amqp, **kwargs):
    schema = L2_tunnel_schema()
    l2_tunnel, errors = schema.load(kwargs)
    if errors:
        raise web.HTTPBadRequest( content_type="application/json",
            text = "{}".format(errors)
        )
    data_store.add(l2_tunnel)
    await send_create_tunnel(data_store, amqp, l2_tunnel)
    l2_tunnel_str = schema.dumps(l2_tunnel).data
    data_store.save(l2_tunnel)
    raise web.HTTPAccepted(content_type="application/json",
        text = l2_tunnel_str
    )
    
    
async def delete_l2_tunnel(data_store, amqp, node_id):
    if not data_store.has((utils.KEY_L2_TUNNEL, node_id)):
        raise web.HTTPNotFound(text = "L2 tunnel Not Found")
    if data_store.has((utils.KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "L2 tunnel in use")
    l2_tunnel = data_store.get(node_id)
    data_store.remove(l2_tunnel)
    data_store.delete(node_id)
    await send_delete_tunnel(data_store, amqp, l2_tunnel)
    raise web.HTTPAccepted()
    
async def send_create_tunnel(data_store, amqp, tunnel):
    await send_action_tunnel(data_store, amqp, utils.ACTION_ADD_TUNNEL, tunnel)

async def send_delete_tunnel(data_store, amqp, tunnel):
    await send_action_tunnel(data_store, amqp, utils.ACTION_DEL_TUNNEL, tunnel) 

async def ack_callback(payload, action):
    logging.debug("{} completed for tunnel {}".format(
        "Setup" if action["operation"]== utils.ACTION_ADD_TUNNEL else "Removal", 
        action["kwargs"]["node_id"]
    ))
    
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
        node_uuid = agent_amqp.node_uuid, callback = ack_callback,
    )
    
 


