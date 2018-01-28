"""
BSD 3-Clause License

Copyright (c) 2018, Maël Kimmerlin, Aalto University, Finland
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import logging
import sys


from ipsec import ike_policy, ipsec_policy, vpn_connection
from tunneling import l2_tunnel, network, expansion
import utils

from helpers_n_wrappers import container3

#Objects to restore, orders matter as there are dependencies
_restores = ["ike_policies", "ipsec_policies", "tunnels", "connections", 
    "networks", "expansions"]

#Types for the API
_type_name_eq = {
    "tunnels" :     {"node_schema": l2_tunnel.L2_tunnel_schema,
        "node_key": utils.KEY_L2_TUNNEL, "node_type_name": "tunnels"},
    "networks" :   {"node_schema": network.Network_schema, 
        "node_key": utils.KEY_NETWORK,"node_type_name": "networks"},
    "connections" : {"node_schema": vpn_connection.Vpn_connection_schema, 
        "node_key": utils.KEY_CONNECTION,"node_type_name": "connections"},
    "ike_policies" :     {"node_schema": ike_policy.Ike_policy_schema, 
        "node_key": utils.KEY_POLICY_IKE,"node_type_name": "ike_policies"},
    "ipsec_policies" :   {"node_schema": ipsec_policy.Ipsec_policy_schema, 
        "node_key": utils.KEY_POLICY_IPSEC,"node_type_name": "ipsec_policies"},
    "expansions" :       {"node_schema": expansion.Expansion_schema, 
        "node_key": utils.KEY_EXPANSION,"node_type_name": "expansions"},
    }


#Class names to API types    
_type_eq = {
    "L2_tunnel" :      _type_name_eq["tunnels"],
    "Network" :        _type_name_eq["networks"],
    "Vpn_connection" : _type_name_eq["connections"],
    "Ike_policy" :     _type_name_eq["ike_policies"],
    "Ipsec_policy" :   _type_name_eq["ipsec_policies"],
    "Expansion" :      _type_name_eq["expansions"],
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
            return {ret}
        
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
        for node_type in _restores:
            if node_type not in nodes_data:
                continue
            type_schema = _type_name_eq[node_type]["node_schema"](many=True)
            data, errors = type_schema.load(nodes_data[node_type])
            if errors:
                logging.error("Error while loading {} data : {}".format(
                    node_type, errors
                    ))
                sys.exit()
            objects.append(data)
        
            #For all nodes loaded, add them to the container
            for node in data:
                try:
                    self.add(node)
                except Exception as e:
                    logging.error("Error while loading node {} : {}".format(
                        node.node_id, e.args
                        ))
                    sys.exit()
            
    def save(self, node_id):
        self.store.save(self._dump(node_id))
        
    def delete(self, node_id):
        self._delete(node_id)
        
    def restore(self):
        self.load_nodes(self.store.load())
