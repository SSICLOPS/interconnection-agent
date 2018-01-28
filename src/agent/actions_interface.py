import sys
import logging


async def action_add_tunnel(agent, *args, **kwargs):
    logging.debug("Creating tunnel {}".format(kwargs["node_id"]))
    agent.add_tunnel(*args, **kwargs)
    return True

async def action_del_tunnel(agent, *args, **kwargs):
    logging.debug("deleting tunnel {}".format(kwargs["node_id"]))
    agent.del_tunnel(*args, **kwargs)
    return True
    
async def action_add_connection(agent, *args, **kwargs):
    logging.debug("Creating connection {}".format(kwargs["node_id"]))
    agent.vpn_manager.add_conf(kwargs)
    return True

async def action_del_connection(agent, *args, **kwargs):
    logging.debug("deleting connection {}".format(kwargs["node_id"]))
    agent.vpn_manager.del_conf(kwargs["node_id"])
    return True
    
async def action_add_network(agent, *args, **kwargs):
    logging.debug("Creating network {}".format(kwargs["node_id"]))
    agent.add_network(*args, **kwargs)
    return True

async def action_del_network(agent, *args, **kwargs):
    logging.debug("deleting network {}".format(kwargs["node_id"]))
    agent.del_network(*args, **kwargs)
    return True
    
async def action_add_expansion(agent, *args, **kwargs):
    logging.debug("Creating expansion {}".format(kwargs["node_id"]))
    agent.add_expansion(*args, **kwargs)
    return True

async def action_del_expansion(agent, *args, **kwargs):
    logging.debug("deleting expansion {}".format(kwargs["node_id"]))
    agent.del_expansion(*args, **kwargs)
    return True

async def action_no_op(agent, *args, **kwargs):
    return True

async def action_die(agent, *args, **kwargs):
    logging.info("Dying")
    sys.exit()
    
actions_mapping = {
    "No-op": action_no_op,
    "Die": action_die,
    "Add-tunnel": action_add_tunnel,
    "Del-tunnel": action_del_tunnel,
    "Add-connection": action_add_connection,
    "Del-connection": action_del_connection,
    "Add-network": action_add_network,
    "Del-network": action_del_network,
    "Add-expansion": action_add_expansion,
    "Del-expansion": action_del_expansion,
}