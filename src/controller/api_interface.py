import data_container
import uuid
import logging
from aiohttp import web

from ipsec import ike_policy

async def test_callback(**kwargs):
    for agent_amqp in kwargs["data_store"].lookup_list(data_container.KEY_AGENT,
        False, False
    ):
        payload_uuid = str(uuid.uuid4())
        payload = {"action_uuid":payload_uuid, "operation":"No-op"}
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
]
