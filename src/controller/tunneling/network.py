from helpers_n_wrappers import container3, utils3
from aiohttp import web
import uuid

import utils
import traceback
import logging

from marshmallow import Schema, fields, post_load, ValidationError


class Network_schema(Schema):
    name             = fields.Str()
    node_id          = fields.Str(validate=utils.validate_uuid)
    cloud_network_id = fields.Int() #segmentation ID from OpenStack or 
    # vlan ID if standalone
    
    @post_load
    def load_node(self, data):
        return Network(**data)
        

class Network(container3.ContainerNode):

    def __init__(self, **kwargs):
        self.node_id = str(uuid.uuid4())
        self.agents_deployed = set()
        utils3.set_attributes(self, override = True, **kwargs)
        super().__init__(name="Network")
            

    def lookupkeys(self):
        """ Return the lookup keys of the node """
        keys = []
        keys.append((utils.KEY_NETWORK, False))
        keys.append((self.node_id, True))
        keys.append(((utils.KEY_NETWORK, self.node_id), True))
        keys.append(((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                self.cloud_network_id
            ), True
        ))
        return keys
        

        
        
async def get_networks(data_store, amqp, node_id=None):
    
    schema = Network_schema()
    if node_id:
        if not data_store.has((utils.KEY_NETWORK, node_id)):
            raise web.HTTPNotFound(text = "Network Not Found")
        network = data_store.get(node_id)
        networks_str = schema.dumps(network).data
    else:
        networks = data_store.lookup_list(utils.KEY_NETWORK)
        networks_str = schema.dumps(networks, many=True).data
    raise web.HTTPOk(content_type="application/json",
        text = networks_str
    )
    
    
async def create_network(data_store, amqp, **kwargs):
    schema = Network_schema()
    network, errors = schema.load(kwargs)
    if errors:
        raise web.HTTPBadRequest( content_type="application/json",
            text = "{}".format(errors)
        )
    data_store.add(network)
    network_str = schema.dumps(network).data
    data_store.save(network)
    raise web.HTTPAccepted(content_type="application/json",
        text = network_str
    )
    
    
async def delete_network(data_store, amqp, node_id):
    if not data_store.has((utils.KEY_NETWORK, node_id)):
        raise web.HTTPNotFound(text = "Network Not Found")
    if data_store.has((utils.KEY_IN_USE, node_id)):
        raise web.HTTPConflict(text = "Network in use")
    network = data_store.get(node_id)
    data_store.remove(network)
    data_store.delete(node_id)
    #TODO remove the network from everywhere it was propagated
    remove_all_propagated_network(data_store, amqp, network)
    raise web.HTTPAccepted()
    
   
    
async def send_create_network(data_store, amqp, agent, network):
    await send_action_network(data_store, amqp, utils.ACTION_ADD_NETWORK, 
        network, agent
    )
    network.agents_deployed.add(agent.node_uuid)

async def send_delete_network(data_store, amqp, agent, network):
    await send_action_network(data_store, amqp, utils.ACTION_DEL_NETWORK, 
        network, agent
    ) 
    network.agents_deployed.discard(agent.node_uuid)
    
async def remove_all_propagated_network(data_store, amqp, network):
    agents_list = list(network.agents_deployed)
    for agent_uuid in agents_list:
        agent = data_store.get(agent_uuid)
        await send_delete_network(data_store, amqp, agent, network)

async def ack_callback(payload, action):
    logging.debug("{} completed {}successfully for network {}".format(
        "Setup" if action["operation"]== utils.ACTION_ADD_NETWORK else "Removal",
        "un" if payload["operation"] == utils.ACTION_NACK else "",
        action["kwargs"]["node_id"]
    ))
    
async def send_action_network(data_store, amqp, action, network, agent_amqp):
    payload = {"operation":action,
        "kwargs": Network_schema().dump(network).data
    }
    await amqp.publish_action(payload=payload, 
        node = agent_amqp, callback = ack_callback,
    )