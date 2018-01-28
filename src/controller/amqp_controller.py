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


import json
import traceback
import logging
import uuid

from common import amqp_client
import agent
import utils


class Amqp_controller(amqp_client.Amqp_client):

    def __init__(self, data_store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions_list = {}
        self.callbacks_list = {}
        self.data_store = data_store
        
    async def publish_action(self, node, callback=None, no_wait=False, **kwargs):
        if "properties" not in kwargs:
            kwargs["properties"] = {}
        action_uuid = str(uuid.uuid4())
        kwargs["payload"]["action_uuid"] = action_uuid
        kwargs["properties"]["content_type"] = 'application/json'
        kwargs["properties"]["reply_to"] = self.process_queue
        kwargs["exchange_name"] = amqp_client.AMQP_EXCHANGE_ACTIONS
        kwargs["routing_key"] = "{}{}".format(amqp_client.AMQP_KEY_ACTIONS, 
            node.node_uuid
            )
        if callback:
            self.actions_list[action_uuid] = kwargs["payload"]
            self.callbacks_list[action_uuid] = callback
        kwargs["payload"] = json.dumps(kwargs["payload"])
        
        if not no_wait:
            await node.loading.wait()
        await self.publish_msg(**kwargs)
        
    async def action_callback(self, channel, body, envelope, properties):
        payload = json.loads(body.decode("utf-8"))
        if "action_uuid" in payload :
            if payload["action_uuid"] in self.actions_list:
                callback = self.callbacks_list[payload["action_uuid"]]
                if callback is not None:
                    await callback(payload, 
                        self.actions_list[payload["action_uuid"]]
                        )
                del self.callbacks_list[payload["action_uuid"]]
                del self.actions_list[payload["action_uuid"]]

                
    async def heartbeat_callback(self, channel, body, envelope, properties):
        payload = json.loads(body.decode("utf-8"))
        payload["addresses"] = set(payload["addresses"])
        payload["networks"] = set(payload["networks"])
        reload_agent = False
        
        #The agent is unknown, not registered yet, register and mark for kill
        if not self.data_store.has(payload["node_uuid"]):
            agent_obj = agent.Agent(**payload)
            self.data_store.add(agent_obj)
            agent_obj.runtime_id = None
            agent_obj.previous_runtime_id = payload["runtime_id"]
            logging.info("Agent {} registered".format(payload["node_uuid"]))
        
        else:
            agent_obj = self.data_store.get(payload["node_uuid"])
            
            #The agent is restarting after a kill
            if agent_obj.runtime_id is None:
                #If the runtime_id has changed, the agent has restarted, then
                #update the addresses and reload the conf
                if payload["runtime_id"] != agent_obj.previous_runtime_id:
                    agent_obj.runtime_id = payload["runtime_id"]
                    logging.info("Agent {} restarted".format(payload["node_uuid"]))
                    agent_obj.update(**payload)
                    self.data_store.updatekeys(agent_obj)
                    #THis should be set after the reload only, but needs to add all no_wait flags
                    agent_obj.loading.set()
                    await agent_obj.reload(self.data_store, self)
            
            # The runtime_id has changed unexpectedly, mark for kill
            elif ( agent_obj.runtime_id != payload["runtime_id"] ):
                agent_obj.loading.clear()
                agent_obj.previous_runtime_id = payload["runtime_id"]
                agent_obj.runtime_id = None
                logging.info(
                    "Agent {} restarted unexpectedly, killing it".format(
                        payload["node_uuid"]
                        )
                    )
            
            # The agent keeps running normally, check for addresses updates
            else:
                if agent_obj.addresses != payload["addresses"]:
                    #do something with the tunnels
                    await agent_obj.update_tunnels(self.data_store, self, 
                        agent_obj.addresses, payload["addresses"]
                        )
                if agent_obj.networks != payload["networks"]:
                    await agent_obj.update_networks(self.data_store, self, 
                        agent_obj.networks, payload["networks"]
                        )
                    
        
        #If the agent was marked for kill, then send kill command
        if agent_obj.runtime_id is None:
            payload = {"operation":utils.ACTION_DIE}
            await self.publish_action(payload=payload, 
                node = agent_obj, no_wait = True
                )

    