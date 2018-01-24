import sys
import logging


async def action_add_tunnel(agent, *args, **kwargs):
    logging.debug("Creating tunnel {}".format(kwargs))
    agent.add_tunnel(*args, **kwargs)
    return True

async def action_del_tunnel(agent, *args, **kwargs):
    logging.debug("deleting tunnel {}".format(kwargs))
    agent.del_tunnel(*args, **kwargs)
    return True
    
async def action_add_connection(agent, *args, **kwargs):
    logging.debug("Creating connection {}".format(kwargs))
    return True

async def action_del_connection(agent, *args, **kwargs):
    logging.debug("deleting connection {}".format(kwargs))
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
}