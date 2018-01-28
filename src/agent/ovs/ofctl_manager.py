import traceback

import utils

import logging

from helpers_n_wrappers import utils3

TABLE_START = 0
TABLE_VNI_SPLIT = 10
TABLE_VLAN_CHECK = 11
TABLE_LEARNING = 12
TABLE_TYPE_SPLIT = 20
TABLE_UNICAST_DUPLICATE = 21
TABLE_UNICAST_LEARNT = 22
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
            "table={}, priority=0, tun_id={}/0xfff, actions=goto_table:{}".format(
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
                TABLE_UNICAST_DUPLICATE, self.patch_tun_id
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, \
dl_dst=00:00:00:00:00:00/01:00:00:00:00:00, \
actions=resubmit(,{}),resubmit(,{})".format(TABLE_TYPE_SPLIT, 
                TABLE_UNICAST_DUPLICATE, TABLE_UNICAST_LEARNT
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, \
dl_dst=01:00:00:00:00:00/01:00:00:00:00:00, actions=goto_table:{}".format(
                TABLE_TYPE_SPLIT, TABLE_MULTICAST
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_UNICAST_DUPLICATE)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=20, reg1=0, \
actions=goto_table:{}".format(TABLE_UNICAST_LEARNT, TABLE_MULTICAST)
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, actions=\
move:NXM_NX_REG1[0..11]->NXM_OF_VLAN_TCI[0..11],\
move:NXM_NX_REG2[0..24]->NXM_NX_TUN_ID[0..24],\
goto_table:{}".format(TABLE_UNICAST_LEARNT, TABLE_ROUTING)
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
        


    