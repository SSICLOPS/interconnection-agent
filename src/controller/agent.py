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

    def update(self, **kwargs):
        utils3.set_attributes(self, override = True, **kwargs)
        
    async def reload(self, data_store, amqp):
        tunnels = []
        connections = []
        for address in self.addresses:
            tunnels.extend(data_store.lookup_list((utils.KEY_L2_TUNNEL, 
                    utils.KEY_L2_TUNNEL_IP, address
                ), False, False
            ))
        logging.debug("Applying tunnels configuration: {}".format(
            [tunnel.node_id for tunnel in tunnels]
        ))
        for tunnel in tunnels:
            await l2_tunnel.send_create_tunnel(data_store, amqp, tunnel)
            connections.extend(data_store.lookup_list((utils.KEY_IN_USE, 
                    tunnel.node_id
                ), False, False
            ))
        logging.debug("Applying connections configuration: {}".format(
            [con.node_id for con in connections]
        ))
        for connection in connections:
            await vpn_connection.send_create_connection(data_store, self, 
                connection
            )