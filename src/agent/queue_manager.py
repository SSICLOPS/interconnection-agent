import asyncio
import logging
import json
from common import amqp_client
import traceback

class Queue_manager(object):

    def __init__(self):
        self.action_queue = asyncio.Queue()
        self.amqp = None
    
    def set_amqp(self, amqp):
        self.amqp = amqp
        
    async def add_to_queue(self, element):
        await self.action_queue.put(element)
        
    async def add_msg_to_queue(self, channel, body, envelope, properties):
        logging.debug("Received an action : {}".format(body))
        element = json.loads(body.decode("utf-8"))
        element["reply-to"] = properties.reply_to
        await self.add_to_queue(element)
        
    async def close_queue(self):
        await self.action_queue.join()
        
    async def process_queue(self):
        while True:
            element = await self.action_queue.get()
            logging.debug("Got queue element {}".format(element))
            uuid = element["uuid"]
            await self.amqp.publish_msg(payload=json.dumps(
                    {"uuid":uuid,"operation":"ack"}
                ),
                properties = {"content_type":'application/json'},
                exchange_name='',
                routing_key=element["reply-to"]
            )
