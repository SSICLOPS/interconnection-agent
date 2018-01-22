from helpers_n_wrappers import container3
import logging
from ipsec import ike_policy

KEY_IN_USE = "KEY_IN_USE"
KEY_AGENT = "KEY_AGENT"
KEY_AGENT_IP = "KEY_AGENT_IP"
KEY_POLICY_IKE = "KEY_POLICY_IKE"

_type_name_eq = {
#    "tunnels" :     {"node_schema": Interco_schema,
#        "node_key": KEY_PEER_CLOUD,"node_type_name": "tunnels"},
#    "networks" :   {"node_schema": Network_schema, 
#        "node_key": KEY_NET,"node_type_name": "networks"},
#    "connections" : {"node_schema": Connection_schema, 
#        "node_key": KEY_CONNECTION,"node_type_name": "connections"},
#    "links" :       {"node_schema": Link_schema, 
#        "node_key": KEY_LINK,"node_type_name": "links"},
    "ike_policies" :     {"node_schema": ike_policy.Ike_policy_schema, 
        "node_key": KEY_POLICY_IKE,"node_type_name": "ike_policies"},
#    "ipsec_policies" :   {"node_schema": Ipsec_schema, 
#        "node_key": KEY_POLICY_IPSEC,"node_type_name": "ipsec_policies"},
#    "netPeers" :       {"node_schema": Net_peer_schema, 
#        "node_key": KEY_NETPEER,"node_type_name": "netPeers"},
#    "mptcpProxies" :    {"node_schema": Mptcp_proxy_schema, 
#        "node_key": KEY_MPTCP_PROXY,"node_type_name": "mptcpProxies"},
#    "policies" :        {"node_schema": Policy_schema, 
#        "node_key": KEY_POLICY,"node_type_name": "policies"}
}
_type_eq = {
#    "Peer_cloud" :     _type_name_eq["tunnels"],
#    "Expanded_net" :   _type_name_eq["networks"],
#    "Vpn_connection" : _type_name_eq["connections"],
#    "Vpn_link" :       _type_name_eq["links"],
    "Ike_policy" :     _type_name_eq["ike_policies"],
#    "Ipsec_policy" :   _type_name_eq["ipsec_policies"],
#    "Net_peer" :       _type_name_eq["netPeers"],
#    "Mptcp_proxy" :    _type_name_eq["mptcpProxies"],
#    "Policy" :         _type_name_eq["policies"],
}

class Data_container(container3.Container):

    def __init__(self,backend, mode):
        super(Data_container, self).__init__(name="data", datatype="set")
        self.store = backend
        # The mode is for the type of dump done to save data
        # either "node" if you want to save a single node, for example for Mysql
        # or "overwrite" if you want to dump everything everytime there is a 
        # change to save everything at once.
        if mode == "node":
            self._dump = self._dump_node
            self._delete = self.store.delete
        elif mode == "overwrite":
            self._dump = self._dump_all
            self._delete = self.save


    def lookup_list(self, key, update=True, check_expire=True):
        ret = super(Data_container, self).lookup(
            key, update=update, check_expire=check_expire)
        
        # No elements with that key are stored
        if ret is None:
            return set()
        
        # A single element was returned
        if not isinstance(ret, set):
            return set(ret)
        
        return ret
    
    def _dump(self, node_id = None):
        # This is an internal function overridden in __init__ based on 
        # backend type
        pass
        # The dump methods should return a dictionary with the type of object
        # as keys and the list of dictionaries containing the objects attributes
        # as value
        
    def _delete(self, node_id = None):
        # This is an internal function overridden in __init__ based on 
        # backend type
        pass
        

    def _dump_all(self, node_id):
        ret = {}
        
        #For all types of nodes, get the Schema and the nodes list
        for node_type_name in _type_name_eq:
            node_schema = _type_name_eq[node_type_name]["node_schema"]
            node_key = _type_name_eq[node_type_name]["node_key"]
            nodes = self.lookup_list(node_key, False, False)
            
            #Create a list of dictionaries with the nodes attributes
            ret[node_type_name] = node_schema().dump(nodes, many=True).data
        logging.debug("{}".format(ret))
        return ret
        
    
    def _dump_node(self, node_id):
        #Node not found -> No-op
        if not self.has(node_id, check_expire=False):
            return
        node = self.get(node_id, update=False)
        
        #fill the dictionnary using the keys defined
        node_type = type(node).__name__
        type_name = _type_eq[node_type]["node_type_name"]
        type_schema = _type_eq[node_type]["node_schema"]
        
        return {type_name:[type_schema().dump(node).data]}
    
    def get_node(self, node_id):
        return self.lookup(node_id, False, False)
        
    def load_nodes(self, nodes_data):
        objects = []
        
        # For each type of node, find the Marshmallow schema and use it to load
        # the nodes. 
        for node_type in nodes_data:
            type_schema = _type_name_eq[node_type]["node_schema"](many=True)
            objects.append(type_schema.load(nodes_data[node_type]).data)
        
        logging.debug("{}".format(objects))
        #For all nodes loaded, add them to the container
        for nodes in objects:
            for node in nodes:
                self.add(node)
            
    def save(self, node_id):
        self.store.save(self._dump(node_id))
        
    def delete(self, node_id):
        self._delete(node_id)
        
    def restore(self):
        self.load_nodes(self.store.load())
