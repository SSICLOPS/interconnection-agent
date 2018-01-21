import uuid
import asyncio
import aioamqp
from helpers_n_wrappers import utils3
import logging
import traceback
import json
import random

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

    def __init__(self, cloud_id, **kwargs):
        default_values = {"host": "127.0.0.1", "login": "guest", "loop": None, 
            "password": "guest", "virtualhost": "/", "port": None, "ssl": False,
            "transport": None, "protocol": None, "channel": None,
            "bind_action_queue": False, 
            "heartbeat_receive_key": AMQP_KEY_HEARTBEATS_CTRL,
            "heartbeat_callback": no_op_callback,
            "action_callback": no_op_callback
        }
        utils3.set_attributes(self, override = False, **default_values)
        utils3.set_attributes(self, override = True, **kwargs)
        if self. port is None:
            if self.ssl:
                self.port = 5671
            else:
                self.port = 5672
        self.connect_lock = asyncio.Lock()
        self.connected = asyncio.Event()
        self.runtime_id = random.randint(1,999)
        self.uuid = cloud_id
        self.hearbeat_payload = json.dumps({"uuid":self.uuid,
            "runtime_id":self.runtime_id
        })

    async def connect(self, ):
        #TODO : put a Mutex
        await self.connect_lock.acquire()
        if self.connected.is_set():
            self.connect_lock.release()
            return
        logging.info("Connecting to AMQP {}:{} {} as {}".format(self.host,
            self.port, self.virtualhost, self.login)
        )
        
        self.transport = None
        self.protocol = None
        
        #Loop on trying to connect
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
        self.runtime_id = random.randint(1,999)
        self.hearbeat_payload = json.dumps({"uuid":self.uuid,
            "runtime_id": self.runtime_id
        })
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
                routing_key="abc"
                #routing_key="{}{}".format(AMQP_KEY_ACTIONS, self.uuid)
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
        
        
    async def on_message(self, channel, body, envelope, properties):
        return
        #don't forget to check the properties.correlation_id:
        # use https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
        # for synchronization

        
    async def on_heartbeat(self, channel, body, envelope, properties):
        logging.debug("Heartbeat received {}".format(body.decode("utf-8")))
        return
        
        
    async def send_heartbeat(self, routing_key):
        while True:
            await self.publish_msg(payload=self.hearbeat_payload,
                properties = {"content_type":'application/json'},
                exchange_name=AMQP_EXCHANGE_HEARTBEATS,
                routing_key=routing_key
            )
            await asyncio.sleep(3)
                
    async def publish_msg(self,**kwargs):
        await self.connected.wait()
        try : 
            await self.channel.basic_publish(**kwargs)
        except aioamqp.AmqpClosedConnection:
            self.connected.clear()
        if not self.connected.is_set():
            await self.connect()