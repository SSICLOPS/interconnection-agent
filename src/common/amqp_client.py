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

import uuid
import asyncio
import aioamqp
import logging
import traceback
import json
import random

from helpers_n_wrappers import utils3



AMQP_EXCHANGE_ACTIONS = "actions"
AMQP_EXCHANGE_HEARTBEATS = "heartbeats"
AMQP_KEY_HEARTBEATS_AGENTS = "heartbeat.agent."
AMQP_KEY_HEARTBEATS_CTRL = "heartbeat.controller"
AMQP_KEY_ACTIONS = "agent."
MAX_KEY = 999

def no_op_callback(channel, body, envelope, properties):
    #pass
    logging.debug("Message received {}".format(body.decode("utf-8")))

class Amqp_client(object):

    def __init__(self, **kwargs):
        default_values = {
            "host": "127.0.0.1", 
            "login": "guest", 
            "loop": None, 
            "password": "guest", 
            "virtualhost": "/", 
            "port": None, 
            "ssl": False,
            "transport": None, 
            "protocol": None, 
            "channel": None,
            "bind_action_queue": False, 
            "heartbeat_receive_key": AMQP_KEY_HEARTBEATS_CTRL,
            "heartbeat_callback": no_op_callback,
            "action_callback": no_op_callback
            }
        
        #Initialize the agent
        utils3.set_attributes(self, override = False, **default_values)
        utils3.set_attributes(self, override = True, **kwargs)
        
        if self. port is None:
            if self.ssl:
                self.port = 5671
            else:
                self.port = 5672
        
        #Synchronization elements
        self.connect_lock = asyncio.Lock()
        self.connected = asyncio.Event()
        
        #Update the runtime ID
        self.modify_runtime_id_hb_payload()
        
        
    #Default heartbeat payload
    def modify_runtime_id_hb_payload(self):
        self.runtime_id = random.randint(1,MAX_KEY)
        self.hearbeat_payload = json.dumps({"node_uuid":self.node_uuid,
            "runtime_id":self.runtime_id
            })

    async def connect(self, ):
        #Mutex to proceed with the connection
        await self.connect_lock.acquire()
        
        #If already connected (parallel), do nothing
        if self.connected.is_set():
            self.connect_lock.release()
            return
            
        logging.info("Connecting to AMQP {}:{} {} as {}".format(self.host,
            self.port, self.virtualhost, self.login)
            )
        
        self.transport = None
        self.protocol = None
        
        #Loop on trying to connect, retry every 3 seconds
        while self.protocol is None :
            try:
                self.transport, self.protocol = await aioamqp.connect(
                    host=self.host, login=self.login, password=self.password, 
                    virtualhost=self.virtualhost, loop=self.loop
                    )
            except Exception as e:
                self.protocol = None
                logging.debug("Connection failure to AMQP : {} {}".format(
                    e.errno, e.strerror
                    ))
                await asyncio.sleep(3)
        self.modify_runtime_id_hb_payload()
        self.channel = await self.protocol.channel()

        
        #create the exchanges
        await self.channel.exchange(AMQP_EXCHANGE_ACTIONS, 'topic')
        await self.channel.exchange(AMQP_EXCHANGE_HEARTBEATS, 'topic')
        
        #Create the queues for receive heartbeats and actions ACKs
        actions_result = await self.channel.queue_declare(queue_name='', 
            durable=False, auto_delete=True, exclusive=True
            )
        self.process_queue = actions_result['queue']
        
        heartbeat_result = await self.channel.queue_declare(queue_name='', 
            durable=False, auto_delete=True, exclusive=True
            )
        heartbeat_queue = heartbeat_result['queue']

        #Bind the queue to the heartbeat exchange 
        await self.channel.queue_bind(
            exchange_name=AMQP_EXCHANGE_HEARTBEATS,
            queue_name=heartbeat_queue,
            routing_key=self.heartbeat_receive_key
            )
        
        if self.bind_action_queue:
            await self.channel.queue_bind(
                exchange_name=AMQP_EXCHANGE_ACTIONS,
                queue_name=self.process_queue,
                routing_key="{}{}".format(AMQP_KEY_ACTIONS, self.node_uuid)
                )
            
        
        #Start the consumers
        await self.channel.basic_consume(
            self.action_callback,
            no_ack=True,
            queue_name=self.process_queue,
            )
        
        await self.channel.basic_consume(
            self.heartbeat_callback,
            no_ack=True,
            queue_name=heartbeat_queue,
            )
        
        logging.info("AMQP connected")
        self.connected.set()
        self.connect_lock.release()
        
        
    async def send_heartbeat(self, routing_key):
        while True:
            await self.publish_msg(payload=self.hearbeat_payload,
                properties = {"content_type":'application/json'},
                exchange_name=AMQP_EXCHANGE_HEARTBEATS,
                routing_key=routing_key
                )
            await asyncio.sleep(3)
                
    
    #Publish a message, handling exceptions if disconnected
    async def publish_msg(self,**kwargs):
        await self.connected.wait()
        try : 
            await self.channel.basic_publish(**kwargs)
        except aioamqp.AmqpClosedConnection:
            self.connected.clear()
        if not self.connected.is_set():
            await self.connect()