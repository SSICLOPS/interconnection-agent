from common import amqp_client
import logging
import sys
import traceback
import json

class Amqp_agent(amqp_client.Amqp_client):
    def __init__(self, agent, *args, **kwargs):
        self.agent = agent
        super().__init__(*args, **kwargs)
        self.controller_uuid = None
        self.controller_runtime_id = None
        
        
    def modify_runtime_id_hb_payload(self):
        self.hearbeat_payload = self.agent.update_runtime_id()
        self.runtime_id = self.agent.runtime_id
        
    def modify_addresses_hb_payload(self, addresses):
        self.hearbeat_payload = self.agent.update_addresses(addresses)
    
    def modify_networks_mapping_hb_payload(self, mappings):
        self.hearbeat_payload = self.agent.update_networks_mapping(mappings)

        
    async def heartbeat_callback(self, channel, body, envelope, properties):
        heartbeat = json.loads(body.decode("utf-8"))
        if self.controller_uuid is None:
            self.controller_uuid = heartbeat["node_uuid"]
            self.controller_runtime_id = heartbeat["runtime_id"]
            logging.info("Synchronized with controller {}".format(
                self.controller_uuid
            ))
        else:
            if self.controller_uuid != heartbeat["node_uuid"]:
                logging.error("Different controller sending heartbeat, exiting")
                sys.exit()
            if self.controller_runtime_id != heartbeat["runtime_id"]:
                logging.error("Desynchronized with controller, exiting")
                sys.exit()