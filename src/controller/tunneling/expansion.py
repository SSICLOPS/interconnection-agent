from helpers_n_wrappers import container3, utils3
from aiohttp import web
import uuid

import utils
import traceback
import logging
from tunneling import network

from marshmallow import Schema, fields, post_load, ValidationError, validate

_expansion_args = {
    "node_id": ("expansion", "node_id"),
    "network_id": ("network", "node_id"),
    "cloud_network_id": ("network", "cloud_network_id"),
    "peer_vni": ("tunnel", "peer_vni"),
    "inter_id_in": ("expansion", "intercloud_id_in"),
    "inter_id_out": ("expansion", "intercloud_id_out")
}


def convert_expansion(**kwargs):
    con_args = {}
    for key in _expansion_args:
        object = kwargs[_expansion_args[key][0]]
        try:
            value = getattr(object, _expansion_args[key][1])
            con_args[key]=value
        except AttributeError:
            pass
    return con_args



class Expansion_schema(Schema):
    node_id           = fields.Str(validate=utils.validate_uuid)
    network_id        = fields.Str(validate=utils.network_validator)
    tunnel_id         = fields.Str(validate=utils.l2_validator)
    intercloud_id_out = fields.Int(validate=validate.Range(2,4095))
    intercloud_id_in  = fields.Int(validate=validate.Range(2,4095))

    
    @post_load
    def load_node(self, data):
        return Expansion(**data)
        

class Expansion(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        self.applied = False
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Expansion")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_EXPANSION, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_EXPANSION, self.node_id), True))
        keys.append(((utils.KEY_EXPANSION, self.network_id, self.tunnel_id), True))
        keys.append(((utils.KEY_IN_USE, self.network_id
            ), False
        ))
        keys.append(((utils.KEY_IN_USE, utils.KEY_EXPANSION, self.network_id
            ), False
        ))
        
        keys.append(((utils.KEY_IN_USE, self.tunnel_id
            ), False
        ))
        keys.append(((utils.KEY_IN_USE, utils.KEY_EXPANSION, self.tunnel_id
            ), False
        ))
        return keys
        
        
async def get_expansions(data_store, amqp, node_id=None, network_id=None):
    
    schema = Expansion_schema()
    if node_id:
        if not data_store.has((utils.KEY_EXPANSION, node_id)):
            raise web.HTTPNotFound(text = "Expansion Not Found")
        expansion = data_store.get(node_id)
        expansions_str = schema.dumps(expansion).data
    elif network_id:
        if not data_store.has((utils.KEY_NETWORK, network_id)):
            raise web.HTTPNotFound(text = "Network Not Found")
        expansions = data_store.lookup_list((utils.KEY_IN_USE, network_id))
        expansions_str = schema.dumps(expansions, many=True).data
    else:
        expansions = data_store.lookup_list(utils.KEY_EXPANSION)
        expansions_str = schema.dumps(expansions, many=True).data
    raise web.HTTPOk(content_type="application/json",
        text = expansions_str
    )
    
    
async def create_expansion(data_store, amqp, **kwargs):
    schema = Expansion_schema()
    expansion, errors = schema.load(kwargs)
    if errors:
        raise web.HTTPBadRequest( content_type="application/json",
            text = "{}".format(errors)
        )
    data_store.add(expansion)
    expansion_str = schema.dumps(expansion).data
    data_store.save(expansion)
    await send_create_expansion(data_store, amqp, expansion)
    raise web.HTTPAccepted(content_type="application/json",
        text = expansion_str
    )
    
    
async def delete_expansion(data_store, amqp, node_id):
    if not data_store.has((utils.KEY_EXPANSION, node_id)):
        raise web.HTTPNotFound(text = "Expansion Not Found")
    if data_store.has((utils.KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "Expansion in use")
    expansion = data_store.get(node_id)
    data_store.remove(expansion)
    data_store.delete(node_id)
    await send_delete_expansion(data_store, amqp, expansion)
    raise web.HTTPAccepted()
    
 
    
    
    
async def send_create_expansion(data_store, amqp, expansion):
    await send_action_expansion(data_store, amqp, utils.ACTION_ADD_EXPANSION, 
        expansion
    )

async def send_delete_expansion(data_store, amqp, expansion):
    await send_action_expansion(data_store, amqp, utils.ACTION_DEL_EXPANSION, 
        expansion
    ) 

async def ack_callback(payload, action):
    logging.debug("{} completed {}successfully for expansion {}".format(
        "Setup" if action["operation"]== utils.ACTION_ADD_EXPANSION else "Removal",
        "un" if payload["operation"] == utils.ACTION_NACK else "",
        action["kwargs"]["node_id"]
    ))
    
async def send_action_expansion(data_store, amqp, action, expansion):
    #Get the elements to send the action
    tunnel = data_store.get(expansion.tunnel_id)
    network_obj = data_store.get(expansion.network_id)
    
    if not data_store.has((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
            tunnel.self_ip )):
        return
        
    
    agent_amqp = data_store.get((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
        tunnel.self_ip
    ))
    
    #If we delete an expansion that was not applied, this is a No op.
    if action == utils.ACTION_DEL_EXPANSION and not expansion.applied:
        return
    
    #If we want to add an expansion in a node where the network is not, No op.
    if ( action == utils.ACTION_ADD_EXPANSION and 
            network_obj.cloud_network_id not in agent_amqp.networks
        ):
        logging.debug("Expansion {} not applicable, network not extended".format(
            expansion.node_id
        ))
        return
        
    #Pre-process the data
    data = convert_expansion(expansion = expansion, tunnel = tunnel,
        network = network_obj
    )
    
    #If we add the expansion, but the network had not been yet propagated on 
    #that agent, propagate it now. If removing, flip the flag
    if action == utils.ACTION_ADD_EXPANSION:
        if agent_amqp.node_uuid not in network_obj.agents_deployed:
            await network.send_create_network(data_store, amqp, agent_amqp, 
                network_obj
            )
        expansion.applied = True
    else:
        expansion.applied = False
    
    #Send the actual action
    payload = {"operation":action,
        "kwargs": data
    }
    await amqp.publish_action(payload=payload, 
        node = agent_amqp, callback = ack_callback,
    )
 
"""
Need to do :
Y - when created, check if it can be applied. if not, don't do anything
Y - when agent reloads, check if it can be applied. if not, don't do anything
- when networks change, check if new networks have applicable expansions, apply them,
  if old networks disappeared, remove the expansion related to those networks.
  also remove the network!  
"""