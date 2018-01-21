import json
import logging
import sys


class Heartbeat_manager(object):

    def __init__(self):
        self.controller_uuid = None
        self.controller_runtime_id = None
        
    async def heartbeat_callback(self, *args):
        heartbeat = json.loads(args[1].decode("utf-8"))
        if self.controller_uuid is None:
            self.controller_uuid = heartbeat["uuid"]
            self.controller_runtime_id = heartbeat["runtime_id"]
            logging.info("Synchronized with controller {}".format(
                self.controller_uuid
            ))
        else:
            if self.controller_uuid != heartbeat["uuid"]:
                logging.error("Different controller sending heartbeat, exiting")
                sys.exit()
            if self.controller_runtime_id != heartbeat["runtime_id"]:
                logging.error("Desynchronized with controller, exiting")
                sys.exit()
            