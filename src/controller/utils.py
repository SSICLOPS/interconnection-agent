from marshmallow import ValidationError
import uuid
import ipaddress

KEY_IN_USE = "KEY_IN_USE"
KEY_AGENT = "KEY_AGENT"
KEY_AGENT_IP = "KEY_AGENT_IP"
KEY_POLICY_IKE = "KEY_POLICY_IKE"
KEY_POLICY_IPSEC = "KEY_POLICY_IPSEC"
KEY_L2_TUNNEL = "KEY_L2_TUNNEL"
KEY_L2_TUNNEL_IP = "KEY_L2_TUNNEL_IP"

ACTION_NO_OP = "No-op"
ACTION_DIE = "Die"
ACTION_ADD_TUNNEL = "Add-tunnel"
ACTION_DEL_TUNNEL = "Del-tunnel"


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