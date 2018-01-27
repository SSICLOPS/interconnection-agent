import asyncio
import logging
import json
from common import amqp_client
import traceback
import actions_interface
from helpers_n_wrappers import utils3
import sys

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
        logging.debug("Received an action : {}".format(body))
        element = json.loads(body.decode("utf-8"))
        element["reply-to"] = properties.reply_to
        await self.add_to_queue(element)
        
    async def close_queue(self):
        await self.action_queue.join()
        
    async def process_queue(self):
        while True:
            try:
                element = await self.action_queue.get()
                logging.debug("Processing queue element {}".format(element))
                action_uuid = element["action_uuid"]
                try:
                    action_func = actions_interface.actions_mapping[element["operation"]]
                except KeyError:
                    logging.debug("Unknown action")
                    continue
                if "args" not in element:
                    element["args"] = []
                if "kwargs" not in element:
                    element["kwargs"] = {}
                resp = await action_func(self.agent, *element["args"],**element["kwargs"])
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
                self.action_queue.task_done()
            except SystemExit:
                sys.exit()
            except:
                traceback.print_exc()
