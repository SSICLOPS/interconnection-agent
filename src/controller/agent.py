from helpers_n_wrappers import container3, utils3
import utils
import asyncio

class Agent(container3.ContainerNode):
    def __init__(self, **kwargs):
        super().__init__(name="Agent")
        utils3.set_attributes(self, override = True, **kwargs)
        self.loading = asyncio.Event()

    def lookupkeys(self):
        keys = []
        keys.append((utils.KEY_AGENT, False))
        keys.append(((utils.KEY_AGENT, self.node_uuid), True))
        keys.append((self.node_uuid, True))
        for address in self.addresses:
            keys.append(((utils.KEY_AGENT, utils.KEY_AGENT_IP, 
                address
            ), True))
        return keys
