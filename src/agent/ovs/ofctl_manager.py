import traceback

import utils

import logging

from helpers_n_wrappers import utils3

TABLE_START = 0
TABLE_VNI_SPLIT = 10
TABLE_VLAN_CHECK = 11
TABLE_LEARNING = 12
TABLE_TYPE_SPLIT = 20
TABLE_UNICAST_LEARNT = 21
TABLE_UNICAST_APPLY = 22
TABLE_MULTICAST = 25
TABLE_ROUTING = 30

class Ofctl_manager(object):

    def __init__(self, **kwargs):
        utils3.set_attributes(self, override = True, **kwargs)
        self.init_tun()
        self.init_in()
        self.init_out()
        #need to know the 3 path ports ids, the name of the three
        #switches
        #patch_in_id
        #patch_out_id
        #patch_tun_id
        #dp_in
        #dp_tun
        #dp_out
        #dpid_in
        #dpid_out
        #dpid_tun
        #self_vni
        
    def remove_all(self):
        for dp in self.dps.values():
            utils.execute("ovs-ofctl del-flows {}".format(dp))
        
    def init_tun(self):
        #reg0 : local vlan
        #reg1 : remote vlan
        #reg2 : local VNI
        #reg3 : remote VNI
        #Add bridge
        utils.execute("ovs-ofctl del-flows {}".format(self.dp_tun))
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_START)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, in_port={}, actions=goto_table:{}".format(
                TABLE_START, self.patch_tun_id, TABLE_TYPE_SPLIT
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=goto_table:{}".format(TABLE_VNI_SPLIT,
                TABLE_ROUTING
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, tun_id={}/0xfff, actions=goto_table:{}".format(
                TABLE_VNI_SPLIT, self.self_vni, TABLE_VLAN_CHECK
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_VLAN_CHECK)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun,
            "table={}, priority=0, actions=learn(\
table={},hard_timeout=300,priority=10,\
NXM_OF_VLAN_TCI[0..11]=NXM_NX_REG0[0..11]\
,NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],\
load:NXM_NX_REG1[]->NXM_NX_REG1[],\
load:NXM_NX_TUN_ID[0..11]->NXM_NX_REG2[12..23],\
load:NXM_NX_TUN_ID[12..23]->NXM_NX_REG2[0..11]),output:{}".format(TABLE_LEARNING, 
                TABLE_UNICAST_LEARNT, self.patch_tun_id
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, \
dl_dst=00:00:00:00:00:00/01:00:00:00:00:00, \
actions=resubmit(,{}),resubmit(,{})".format(TABLE_TYPE_SPLIT, 
                TABLE_UNICAST_LEARNT, TABLE_UNICAST_APPLY
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, \
dl_dst=01:00:00:00:00:00/01:00:00:00:00:00, actions=goto_table:{}".format(
                TABLE_TYPE_SPLIT, TABLE_MULTICAST
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_UNICAST_LEARNT)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=20, reg1=0, \
actions=goto_table:{}".format(TABLE_UNICAST_APPLY, TABLE_MULTICAST)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, actions=\
move:NXM_NX_REG1[0..11]->NXM_OF_VLAN_TCI[0..11],\
move:NXM_NX_REG2[0..24]->NXM_NX_TUN_ID[0..24],\
goto_table:{}".format(TABLE_UNICAST_APPLY, TABLE_ROUTING)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_MULTICAST)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_ROUTING)
        ])
        
    def init_in(self):
        utils.execute("ovs-ofctl del-flows {}".format(self.dp_in))
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_in, 
            "table={}, priority=0, actions=normal".format(TABLE_START)
        ])
    
    def init_out(self):
        utils.execute("ovs-ofctl del-flows {}".format(self.dp_out))
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_out, 
            "table={}, priority=0, actions=normal".format(TABLE_START)
        ])
        
    def add_tunnel(self, port_id):
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, in_port={}, actions=goto_table:{}".format(
                TABLE_START, port_id, TABLE_VNI_SPLIT
            )
        ])
        
    def add_route(self, vni, port_id):
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, tun_id={}/0xfff, actions=output:{}".format(
                TABLE_ROUTING, vni, port_id
            )
        ])
        
    def del_tunnel(self, port_id):
        utils.execute_list(["ovs-ofctl", "del-flow", "--strict", self.dp_tun, 
            "table={}, priority=10, in_port={}".format(TABLE_START, port_id)
        ])
        
    def del_route(self, vni):
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, tun_id={}/0xfff".format(TABLE_ROUTING, vni)
        ])
        

    def add_expansion(self, expansion, expansions_list, local_vlan):
        #{'inter_id_out': 126, 'inter_id_in': 128, 'node_id': '19e4b5fc-474e-41e8-a181-6729a1d1f633', 'peer_vni': 156, 'cloud_network_id': 4}
        #self.self_vni
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, tun_id=0x{:03x}{:03x}, vlan_vid=0x1{:03x}/0x1fff, \
actions=mod_vlan_vid:{},load:{}->NXM_NX_REG0[],load:{}->NXM_NX_REG1[],goto_table:{}".format(TABLE_VLAN_CHECK, 
                expansion["peer_vni"], self.self_vni, expansion["inter_id_in"], 
                local_vlan, hex(expansion["inter_id_in"]), 
                hex(expansion["inter_id_out"]), TABLE_LEARNING
            )
        ])
        actions=[]
        for expansion_mult in expansions_list:
            actions.append("mod_vlan_vid:{}".format(expansion_mult["inter_id_out"]))
            actions.append("set_field:0x{:03x}{:03x}->tun_id".format(self.self_vni,
                expansion_mult["peer_vni"]
            ))
            actions.append("resubmit(,{})".format(TABLE_ROUTING))
        actions_str = ",".join(actions)
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, vlan_vid=0x1{:03x}/0x1fff, actions={}".format(
                TABLE_MULTICAST, 
                local_vlan, 
                actions_str
            )
        ])
    
    
    
    
    def del_expansion(self, expansion, expansions_list, local_vlan):
        #{'inter_id_out': 126, 'inter_id_in': 128, 'node_id': '19e4b5fc-474e-41e8-a181-6729a1d1f633', 'peer_vni': 156, 'cloud_network_id': 4}
        #self.self_vni
        utils.execute_list(["ovs-ofctl", "del-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, tun_id=0x{:x}{:x}, vlan_vid=0x1{:03x}/0x1fff".format(TABLE_VLAN_CHECK, 
                expansion["peer_vni"], self.self_vni, expansion["inter_id_in"]
            )
        ])
        actions=[]
        for expansion_mult in expansions_list:
            actions.append("mod_vlan_vid:{}".format(expansion_mult["inter_id_out"]))
            actions.append("set_field:0x{:03x}{:03x}->tun_id".format(self.self_vni,
                expansion_mult["peer_vni"]
            ))
            actions.append("resubmit(,{})".format(TABLE_ROUTING))
        actions_str = ",".join(actions)
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, vlan_vid=0x1{:03x}/0x1fff, actions={}".format(
                TABLE_MULTICAST, 
                local_vlan, 
                actions_str
            )
        ])
        
        
        
        
        
        
        
    