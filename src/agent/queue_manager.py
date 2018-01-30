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

import asyncio
import logging
import json
import sys

from common import amqp_client
import actions_interface

from helpers_n_wrappers import utils3


class Queue_manager(object):

    def __init__(self, agent):
        self.action_queue = asyncio.Queue()
        self.amqp = None
        self.agent = agent
    
    def set_amqp(self, amqp):
        self.amqp = amqp
        
    async def add_to_queue(self, element):
        await self.action_queue.put(element)
        
    async def add_msg_to_queue(self, channel, body, envelope, properties):
        element = json.loads(body.decode("utf-8"))
        logging.debug("Received action {} : {}".format(element["action_uuid"],
            element["operation"]
            ))
        element["reply-to"] = properties.reply_to
        await self.add_to_queue(element)
        
    async def close_queue(self):
        await self.action_queue.join()
        
    async def process_queue(self):
        while True:
        
            #Get the next action
            try:
                element = await self.action_queue.get()
            except:
                return
            
            resp = None
            try:
                logging.debug("Processing queue element {}".format(
                    element["action_uuid"]
                    ))
                
                action_uuid = element["action_uuid"]
                
                try:
                    action_func = actions_interface.actions_mapping[element["operation"]]
                except KeyError:
                    logging.debug("Unknown action")
                    self.action_queue.task_done()
                    continue
                
                #Call the function
                if "args" not in element:
                    element["args"] = []
                if "kwargs" not in element:
                    element["kwargs"] = {}
                resp = await action_func(self.agent, *element["args"],**element["kwargs"])
                
                self.action_queue.task_done()
                logging.debug("Action completed")
            
            except SystemExit:
                sys.exit()
            except :
                logging.error("Action failed")
                resp = False
            
            #Send the status back to the controller
            if resp:
                action_ack = "Ack"
            else:
                action_ack = "Nack"

            await self.amqp.publish_msg(payload=json.dumps(
                    {"action_uuid":action_uuid,"operation":action_ack}
                    ),
                properties = {"content_type":'application/json'},
                exchange_name='',
                routing_key=element["reply-to"]
                )