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
   
#Mapping from action name sent by controller to function   
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