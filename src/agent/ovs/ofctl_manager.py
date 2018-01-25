import traceback

import utils

import logging

from helpers_n_wrappers import utils3



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
            "table=0, priority=0, actions=drop"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=0, priority=10, in_port={}, actions=goto_table:20".format(
                self.patch_tun_id
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=10, priority=0, actions=goto_table:30"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=10, priority=0, tun_id={}/0xfff, actions=goto_table:11".format(
                self.self_vni
            )
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=11, priority=0, actions=drop"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun,
            "table=12, priority=0, actions=learn(\
table=21,hard_timeout=300,priority=10,\
NXM_OF_VLAN_TCI[0..11]=NXM_NX_REG0[0..11]\
,NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],\
load:NXM_NX_REG1[]->NXM_NX_REG1[],\
load:NXM_NX_TUN_ID[0..11]->NXM_NX_REG2[12..23],\
load:NXM_NX_TUN_ID[12..23]->NXM_NX_REG2[0..11])"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=20, priority=10, \
dl_dst=00:00:00:00:00:00/01:00:00:00:00:00, \
actions=resubmit(,21),resubmit(,22)"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=20, priority=10, \
dl_dst=01:00:00:00:00:00/01:00:00:00:00:00, actions=goto_table:25"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=21, priority=0, actions=drop"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=22, priority=20, reg1=0, \
actions=goto_table:25"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=22, priority=10, actions=\
move:NXM_NX_REG1[0..11]->NXM_OF_VLAN_TCI[0..11],\
move:NXM_NX_REG2[0..24]->NXM_NX_TUN_ID[0..24],\
goto_table:30"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=25, priority=0, actions=drop"
        ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=30, priority=0, actions=drop"
        ])
        
    def init_in(self):
        utils.execute("ovs-ofctl del-flows {}".format(self.dp_in))
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_in, 
            "table=0, priority=0, actions=normal"
        ])
    
    def init_out(self):
        utils.execute("ovs-ofctl del-flows {}".format(self.dp_out))
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_out, 
            "table=0, priority=0, actions=normal"
        ])
        
    def add_tunnel(self, port_id):
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=0, priority=10, in_port={}, actions=goto_table:10".format(
                port_id
            )
        ])
        
    def add_route(self, vni, port_id):
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=30, priority=10, tun_id={}/0xfff, actions=output:{}".format(
                vni, port_id
            )
        ])
        
    def del_tunnel(self, port_id):
        utils.execute_list(["ovs-ofctl", "del-flow", "--strict", self.dp_tun, 
            "table=0, priority=10, in_port={}".format(port_id)
        ])
        
    def del_route(self, vni):
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table=30, priority=10, tun_id={}/0xfff".format(vni)
        ])
        


    