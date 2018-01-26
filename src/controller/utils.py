from marshmallow import ValidationError
import uuid
import ipaddress
import functools

KEY_IN_USE = "KEY_IN_USE"
KEY_AGENT = "KEY_AGENT"
KEY_AGENT_IP = "KEY_AGENT_IP"
KEY_POLICY_IKE = "KEY_POLICY_IKE"
KEY_POLICY_IPSEC = "KEY_POLICY_IPSEC"
KEY_L2_TUNNEL = "KEY_L2_TUNNEL"
KEY_L2_TUNNEL_IP = "KEY_L2_TUNNEL_IP"
KEY_CONNECTION = "KEY_CONNECTION"
KEY_NETWORK = "KEY_NETWORK"
KEY_CLOUD_NET_ID = "KEY_CLOUD_NET_ID"

ACTION_ACK = "Ack"
ACTION_NACK = "Nack"
ACTION_NO_OP = "No-op"
ACTION_DIE = "Die"
ACTION_ADD_TUNNEL = "Add-tunnel"
ACTION_DEL_TUNNEL = "Del-tunnel"
ACTION_ADD_CONNECTION = "Add-connection"
ACTION_DEL_CONNECTION = "Del-connection"



def validate_uuid(uuid_str):
    try:
        uuid.UUID(uuid_str, version=4)
    except ValueError:
        raise ValidationError("{} is not a correct UUID".format(uuid_str))
    return True
    
def create_validation_str(list):
    def func(element):
        if element not in list:
            raise ValidationError("{} not in {}".format(element, list))
        return True
    return func

def validate_ip_address(address):
    try:
        ipaddress.ip_address(address)
    except ValueError:
        raise ValidationError("Incorrect IP : {}".format(address))
    return True
    
class Data_store_validator(object):
    
    def __init__(self):
        self.data_store = None
        
    def add_data_store(self, data_store):
        self.data_store = data_store
        
    def check_in_data(self, key, node_id):
        validate_uuid(node_id)
        if not self.data_store:
            raise ValidationError("No data structure initialized")
        if not self.data_store.has((key, node_id)):
            raise ValidationError("{} not found".format(node_id))
        return True
        
data_store_validator = Data_store_validator()
l2_validator = functools.partial(data_store_validator.check_in_data,
    KEY_L2_TUNNEL
)
ike_validator = functools.partial(data_store_validator.check_in_data,
    KEY_POLICY_IKE
)
ipsec_validator = functools.partial(data_store_validator.check_in_data,
    KEY_POLICY_IPSEC
)