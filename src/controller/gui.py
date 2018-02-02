from jinja2 import Environment, FileSystemLoader
import json
from aiohttp import web

import utils
from ipsec import ike_policy, ipsec_policy, vpn_connection
from tunneling import l2_tunnel, network, expansion, mptcp_proxy

template_folder = ""

env_main = Environment(
    autoescape=False,
    loader=FileSystemLoader("/root/interco/interco-v2/templates"),
    trim_blocks=False)



async def get_main(data_store, amqp):
    lookup = data_store.lookup_list
    connections = []
    expansions = []
    for connection in lookup(utils.KEY_CONNECTION, False, False):
        tunnel = data_store.get(connection.tunnel_id)
        ike = data_store.get(connection.ike_policy_id)
        ipsec = data_store.get(connection.ipsec_policy_id)

        data = vpn_connection.convert_con_template(connection=connection, 
            tunnel = tunnel, ike = ike, ipsec = ipsec
            )
        connections.append(data)
    for expansion_obj in lookup(utils.KEY_EXPANSION, False, False):
        tunnel = data_store.get(expansion_obj.tunnel_id)
        network_obj = data_store.get(expansion_obj.network_id)
        data = expansion.convert_expansion(expansion = expansion_obj, 
            tunnel = tunnel, network = network_obj
            )
        expansions.append(data)
    return web.HTTPOk(content_type="text/html",
        text=env_main.get_template("main.html").render(
            {"ike_policies": lookup(utils.KEY_POLICY_IKE, False, False),
                "ipsec_policies": lookup(utils.KEY_POLICY_IPSEC, False, False),
                "agents": lookup(utils.KEY_AGENT, False, False),
                "connections": connections,
                "tunnels": lookup(utils.KEY_L2_TUNNEL, False, False),
                "networks": lookup(utils.KEY_NETWORK, False, False),
                "expansions": expansions,
                "mptcp_proxies": lookup(utils.KEY_MPTCP_PROXY, False, False),
                }
            )
        )


async def process_query(data_store, amqp, callback, kwargs):
    try:
        await callback(data_store, amqp, **kwargs)
    except Exception as e:
        if not isinstance(e, web.HTTPSuccessful):
            raise e
    return web.HTTPOk(content_type="text/html",
        text=env_main.get_template("output.html").render()
        )


async def create_ike(data_store, amqp, **kwargs):
    kwargs["lifetime_value"] = int(kwargs["lifetime_value"])
    return await process_query(data_store, amqp, ike_policy.create_ike_policy, 
        kwargs
        )


async def delete_ike(data_store, amqp, **kwargs):
    return await process_query(data_store, amqp, ike_policy.delete_ike_policy, 
        kwargs
        )


async def create_ipsec(data_store, amqp, **kwargs):
    kwargs["lifetime_value"] = int(kwargs["lifetime_value"])
    return await process_query(data_store, amqp, 
        ipsec_policy.create_ipsec_policy, kwargs
        )


async def delete_ipsec(data_store, amqp, **kwargs):
    return await process_query(data_store, amqp, 
        ipsec_policy.delete_ipsec_policy, kwargs
        )
        
        
async def create_tunnel(data_store, amqp, **kwargs):
    kwargs["peer_vni"] = int(kwargs["peer_vni"])
    kwargs["enabled"] = kwargs["enabled"] == "True"
    if not kwargs["peer_public_ip"] :
        del kwargs["peer_public_ip"]
    return await process_query(data_store, amqp, 
        l2_tunnel.create_l2_tunnel, kwargs
        )


async def delete_tunnel(data_store, amqp, **kwargs):
    return await process_query(data_store, amqp, 
        l2_tunnel.delete_l2_tunnel, kwargs
        )
        
        
async def create_connection(data_store, amqp, **kwargs):
    kwargs["dpd_interval"] = int(kwargs["dpd_interval"])
    kwargs["dpd_timeout"] = int(kwargs["dpd_timeout"])
    return await process_query(data_store, amqp, 
        vpn_connection.create_vpn_connection, kwargs
        )


async def delete_connection(data_store, amqp, **kwargs):
    return await process_query(data_store, amqp, 
        vpn_connection.delete_vpn_connection, kwargs
        )


async def create_network(data_store, amqp, **kwargs):
    kwargs["cloud_network_id"] = int(kwargs["cloud_network_id"])
    return await process_query(data_store, amqp, 
        network.create_network, kwargs
        )


async def delete_network(data_store, amqp, **kwargs):
    return await process_query(data_store, amqp, 
        network.delete_network, kwargs
        )

        
async def create_expansion(data_store, amqp, **kwargs):
    kwargs["intercloud_id_in"] = int(kwargs["intercloud_id_in"])
    kwargs["intercloud_id_out"] = int(kwargs["intercloud_id_out"])
    return await process_query(data_store, amqp, 
        expansion.create_expansion, kwargs
        )


async def delete_expansion(data_store, amqp, **kwargs):
    return await process_query(data_store, amqp, 
        expansion.delete_expansion, kwargs
        )
        
        
async def create_mptcp(data_store, amqp, **kwargs):
    kwargs["peer_vni"] = int(kwargs["peer_vni"])
    kwargs["peer_port"] = int(kwargs["peer_port"])
    kwargs["self_port_lan"] = int(kwargs["self_port_lan"])
    kwargs["self_port_wan"] = int(kwargs["self_port_wan"])
    return await process_query(data_store, amqp, 
        mptcp_proxy.create_mptcp_proxy, kwargs
        )


async def delete_mptcp(data_store, amqp, **kwargs):
    return await process_query(data_store, amqp, 
        mptcp_proxy.delete_mptcp_proxy, kwargs
        )