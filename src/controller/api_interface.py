import data_container
import uuid
import logging
from aiohttp import web
import utils

from ipsec import ike_policy, ipsec_policy
from tunneling import l2_tunnel

async def test_callback(**kwargs):
    for agent_amqp in kwargs["data_store"].lookup_list(data_container.KEY_AGENT,
        False, False
    ):
        payload = {"operation":utils.ACTION_NO_OP}
        await kwargs["amqp"].publish_action(payload=payload, 
            node_uuid = agent_amqp.node_uuid, callback = ack_callback,
        )
    raise web.HTTPOk()
    
async def ack_callback(payload, action):
    logging.debug("Received ACK for action {}".format(payload["action_uuid"]))
    
api_mappings = [
    {"method":"GET", "endpoint":"/test", "callback":test_callback, 
        "url_args": [], "required_args" : [], "opt_args" : []
    },
    {"method":"GET", "endpoint":"/ike", "callback":ike_policy.get_ike_policies, 
        "url_args": [], "required_args" : [], "opt_args" : []
    },
    {"method":"GET", "endpoint":"/ike/{node_id}", 
        "callback":ike_policy.get_ike_policies, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
    },
    {"method":"DELETE", "endpoint":"/ike/{node_id}", 
        "callback":ike_policy.delete_ike_policy, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
    },
    {"method":"POST", "endpoint":"/ike", 
        "callback":ike_policy.create_ike_policy, "url_args": [], 
        "required_args" : ["name", "ike_version", 
            "encryption_algorithm", "auth_algorithm", "pfs", "lifetime_value"
        ], "opt_args" : []
    },
    {"method":"GET", "endpoint":"/ipsec", "callback":ipsec_policy.get_ipsec_policies, 
        "url_args": [], "required_args" : [], "opt_args" : []
    },
    {"method":"GET", "endpoint":"/ipsec/{node_id}", 
        "callback":ipsec_policy.get_ipsec_policies, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
    },
    {"method":"DELETE", "endpoint":"/ipsec/{node_id}", 
        "callback":ipsec_policy.delete_ipsec_policy, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
    },
    {"method":"POST", "endpoint":"/ipsec", 
        "callback":ipsec_policy.create_ipsec_policy, "url_args": [], 
        "required_args" : ["name", "transform_protocol", "encapsulation_mode",
            "encryption_algorithm", "auth_algorithm", "pfs", "lifetime_value"
        ], "opt_args" : []
    },
    {"method":"GET", "endpoint":"/tunnel", "callback":l2_tunnel.get_l2_tunnels, 
        "url_args": [], "required_args" : [], "opt_args" : []
    },
    {"method":"GET", "endpoint":"/tunnel/{node_id}", 
        "callback":l2_tunnel.get_l2_tunnels, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
    },
    {"method":"DELETE", "endpoint":"/tunnel/{node_id}", 
        "callback":l2_tunnel.delete_l2_tunnel, "url_args": ["node_id"], 
        "required_args" : [], "opt_args" : []
    },
    {"method":"POST", "endpoint":"/tunnel", 
        "callback":l2_tunnel.create_l2_tunnel, "url_args": [], 
        "required_args" : ["name", "self_ip", "peer_id", "peer_ip", 
            "type", "mtu", "enabled"
        ], "opt_args" : ["peer_public_ip"]
    },
]
