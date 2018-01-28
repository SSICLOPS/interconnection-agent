from helpers_n_wrappers import container3, utils3
import utils
import asyncio
import logging
from tunneling import l2_tunnel, network, expansion
from ipsec import vpn_connection
import traceback

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
        expansions = []
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
                    utils.KEY_CONNECTION, tunnel.node_id
                ), False, False
            ))
            expansions.extend(data_store.lookup_list((utils.KEY_IN_USE, 
                    utils.KEY_EXPANSION, tunnel.node_id
                ), False, False
            ))
        logging.debug("Applying connections configuration: {}".format(
            [con.node_id for con in connections]
        ))
        for connection in connections:
            await vpn_connection.send_create_connection(data_store, amqp, 
                connection
            )
        for network_obj in data_store.lookup_list(utils.KEY_NETWORK, 
                False, False):
            if self.node_uuid in network_obj.agents_deployed:
                network_obj.agents_deployed.discard(self.node_uuid)
        for expansion_obj in expansions:
            await expansion.send_create_expansion(data_store, amqp, 
                expansion_obj
            )
            
    async def update_tunnels(self, data_store, amqp, old_addresses, new_addresses):
        for address in old_addresses - new_addresses:
            if not data_store.has((utils.KEY_L2_TUNNEL, utils.KEY_L2_TUNNEL_IP, 
                    address)):
                continue
            for tunnel in data_store.get(utils.KEY_L2_TUNNEL, 
                    utils.KEY_L2_TUNNEL_IP, address):
                for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                        utils.KEY_EXPANSION, tunnel.node_id ), False, False):
                    await expansion.send_delete_expansion(data_store, amqp, 
                        expansion_obj
                    ) 
                await l2_tunnel.send_delete_tunnel(data_store, amqp, tunnel)
        self.addresses = payload["addresses"]
        self.data_store.updatekeys(self)
        for address in new_addresses - old_addresses:
            if not data_store.has((utils.KEY_L2_TUNNEL, utils.KEY_L2_TUNNEL_IP, 
                    address)):
                continue
            for tunnel in data_store.get(utils.KEY_L2_TUNNEL, 
                    utils.KEY_L2_TUNNEL_IP, address):
                await l2_tunnel.send_create_tunnel(data_store, amqp, tunnel)
                for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                        utils.KEY_EXPANSION, tunnel.node_id ), False, False):
                    await expansion.send_create_expansion(data_store, amqp,
                        expansion_obj)
                
    async def update_networks(self, data_store, amqp, old_networks, new_networks):
        logging.debug("Updating the networks")
        try:
            for network_cloud_id in old_networks - new_networks:
                if not data_store.has((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                    network_cloud_id )):
                    continue
                network_obj = data_store.get((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                    network_cloud_id ))
                for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                        utils.KEY_EXPANSION, network_obj.node_id ), False, False):
                    await expansion.send_delete_expansion(data_store, amqp,
                        expansion_obj) 
                await network.remove_all_propagated_network(data_store, amqp, network_obj)
            self.networks = new_networks
            data_store.updatekeys(self)
            for network_cloud_id in new_networks - old_networks:
                if not data_store.has((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                    network_cloud_id )):
                    continue
                network_obj = data_store.get((utils.KEY_NETWORK, utils.KEY_CLOUD_NET_ID, 
                    network_cloud_id ))
                for expansion_obj in data_store.lookup_list((utils.KEY_IN_USE, 
                        utils.KEY_EXPANSION, network_obj.node_id ), False, False):
                    await expansion.send_create_expansion(data_store, amqp,
                        expansion_obj)
        except:
            traceback.print_exc()