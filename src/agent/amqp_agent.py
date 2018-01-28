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

import logging
import sys
import traceback
import json

from common import amqp_client


class Amqp_agent(amqp_client.Amqp_client):
    def __init__(self, agent, *args, **kwargs):
        self.agent = agent
        super().__init__(*args, **kwargs)
        self.controller_uuid = None
        self.controller_runtime_id = None
        
        
    #Change the runtime ID
    def modify_runtime_id_hb_payload(self):
        self.hearbeat_payload = self.agent.update_runtime_id()
        self.runtime_id = self.agent.runtime_id
        
    #Change the agent addresses
    def modify_addresses_hb_payload(self, addresses):
        self.hearbeat_payload = self.agent.update_addresses(addresses)
    
    #Change the networks present on node
    def modify_networks_mapping_hb_payload(self, mappings):
        self.hearbeat_payload = self.agent.update_networks_mapping(mappings)

        
    #Handle the callback from controller
    async def heartbeat_callback(self, channel, body, envelope, properties):
        heartbeat = json.loads(body.decode("utf-8"))
        
        
        
        #Set the synchronization items from the controller
        if self.controller_uuid is not None:
            if self.controller_uuid != heartbeat["node_uuid"]:
                logging.error("Different controller sending heartbeat, exiting")
                sys.exit()
            if self.controller_runtime_id != heartbeat["runtime_id"]:
                logging.error("Desynchronized with controller, exiting")
                sys.exit()
        else:
            self.controller_uuid = heartbeat["node_uuid"]
            self.controller_runtime_id = heartbeat["runtime_id"]
            logging.info("Synchronized with controller {}".format(
                self.controller_uuid
                ))
            