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

import utils
from helpers_n_wrappers import utils3

TABLE_START = 0
TABLE_IN_MPTCP = 10
TABLE_VNI_SPLIT = 20
TABLE_VLAN_CHECK = 21
TABLE_LEARNING = 22
TABLE_TYPE_SPLIT = 30
TABLE_UNICAST_LEARNT = 31
TABLE_UNICAST_APPLY = 32
TABLE_MULTICAST = 35
TABLE_SPLIT_MPTCP = 40
TABLE_APPLY_MPTCP = 41
TABLE_ROUTING = 42

TABLE_MPTCP_VLAN = 2
TABLE_MPTCP_LEARN = 1
TABLE_MPTCP_LEARNT = 3
TABLE_MPTCP_FORWARD = 4


class Ofctl_manager(object):

    def __init__(self, **kwargs):
        utils3.set_attributes(self, override = True, **kwargs)
    
    def init_flows(self):
        self.init_tun()
        self.init_in()
        self.init_out()
        
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
            "".join([
                "table={}, priority=0, actions=learn(".format(TABLE_LEARNING),
                "table={},hard_timeout=300,priority=10,".format(TABLE_UNICAST_LEARNT),
                "NXM_OF_VLAN_TCI[0..11]=NXM_NX_REG0[0..11]",
                ",NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],",
                "load:NXM_NX_REG0[]->NXM_NX_REG0[],",
                "load:NXM_NX_TUN_ID[0..11]->NXM_NX_REG2[12..23],",
                "load:NXM_NX_TUN_ID[12..23]->NXM_NX_REG2[0..11]),",
                "output:{}".format(self.patch_tun_id)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "".join([
                "table={}, priority=10, ".format(TABLE_TYPE_SPLIT),
                "dl_dst=00:00:00:00:00:00/01:00:00:00:00:00, ",
                "actions=resubmit(,{}),resubmit(,{})".format( 
                    TABLE_UNICAST_LEARNT, TABLE_UNICAST_APPLY
                    )
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "".join(["table={}, priority=10, ".format(TABLE_TYPE_SPLIT),
                "dl_dst=01:00:00:00:00:00/01:00:00:00:00:00, ",
                "actions=goto_table:{}".format(TABLE_MULTICAST)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_UNICAST_LEARNT)
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "".join(["table={}, priority=20, reg0=0, ".format(TABLE_UNICAST_APPLY),
                "actions=goto_table:{}".format(TABLE_MULTICAST)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "".join([
                "table={}, priority=10, actions=".format(TABLE_UNICAST_APPLY),
                "move:NXM_NX_REG0[0..11]->NXM_OF_VLAN_TCI[0..11],",
                "move:NXM_NX_REG2[0..23]->NXM_NX_TUN_ID[0..23],",
                "goto_table:{}".format(TABLE_SPLIT_MPTCP)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_MULTICAST)
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=goto_table:{}".format(TABLE_SPLIT_MPTCP,
                TABLE_ROUTING
                )
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=goto_table:{}".format(TABLE_APPLY_MPTCP,
                TABLE_ROUTING
                )
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
            
    def init_mptcp(self, **kwargs):
        utils3.set_attributes(self, override=True, **kwargs)
        utils.execute("ovs-ofctl del-flows {}".format(self.dp_mptcp))
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=0, actions=goto_table:{}".format(TABLE_START,
                TABLE_MPTCP_VLAN
                )
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            " ".join([
                "table={}, priority=10, in_port={},".format(TABLE_START,
                    self.patch_mptcp_port
                    ),
                "actions=goto_table:{}".format(TABLE_MPTCP_LEARN)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=10, tcp, actions=goto_table:{}".format(
                TABLE_MPTCP_LEARN, TABLE_MPTCP_FORWARD)
            ])   
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            " ".join([
                "table={}, priority=10, arp,".format(TABLE_MPTCP_LEARN),
                "actions=learn(table={}, priority=10,".format(TABLE_MPTCP_LEARNT),
                "eth_src=E1:8E:36:8C:F6:0D, eth_type=0x0800,",
                "NXM_OF_IP_DST[]=NXM_OF_ARP_SPA[],",
                "load:NXM_NX_ARP_SHA[]->NXM_OF_ETH_DST[],",
                "output:NXM_OF_IN_PORT[])"
                ])
            ])   
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=0, actions=drop".format(TABLE_MPTCP_LEARN)
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=0, actions=drop".format(TABLE_MPTCP_VLAN)
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=0, actions=drop".format(TABLE_MPTCP_LEARNT)
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=0, actions=drop".format(TABLE_MPTCP_FORWARD)
            ])
            
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, in_port={}, actions=goto_table:{}".format(
                TABLE_START, self.patch_tun_port_mptcp, TABLE_IN_MPTCP
                )
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=0, actions=drop".format(TABLE_IN_MPTCP)
            ])

            
        
        
        

    def add_proxy(self, port, vni, eth_addr):
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            " ".join([
                "table={}, priority=10, in_port={}".format(TABLE_MPTCP_VLAN, port),
                "actions=mod_vlan_vid:{},goto_table:{}".format(vni, 
                    TABLE_MPTCP_LEARNT
                    )
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_mptcp, 
            " ".join([
                "table={}, priority=10, vlan_vid=0x1{:03x}".format(TABLE_MPTCP_FORWARD, vni),
                "actions=set_field:{}->eth_dst,strip_vlan,".format(eth_addr),
                "output:{}".format(port)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            " ".join([
                "table={}, priority=10,".format(TABLE_APPLY_MPTCP),
                "tcp, tun_id=0x{:x}/0xfff".format(vni), 
                "actions=move:NXM_OF_VLAN_TCI[0..11]->NXM_NX_PKT_MARK[0..11]",
                "move:NXM_NX_TUN_ID[0..11]->NXM_OF_VLAN_TCI[0..11]",
                "output:{}".format(self.patch_tun_port_mptcp)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            " ".join([
                "table={}, priority=10,".format(TABLE_APPLY_MPTCP),
                "arp, tun_id=0x{:x}/0xfff".format(vni), 
                "actions=resubmit(,{}),".format(TABLE_ROUTING),
                "move:NXM_OF_VLAN_TCI[0..11]->NXM_NX_PKT_MARK[0..11]",
                "move:NXM_NX_TUN_ID[0..11]->NXM_OF_VLAN_TCI[0..11]",
                "output:{}".format(self.patch_tun_port_mptcp)
                ])
            ])
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            " ".join([
                "table={}, priority=10,".format(TABLE_IN_MPTCP),
                "vlan_vid=0x1{:03x}/0x1fff".format(vni),
                "actions=move:NXM_OF_VLAN_TCI[0..11]->NXM_NX_TUN_ID[12..23]",
                "move:NXM_NX_PKT_MARK[0..11]->NXM_OF_VLAN_TCI[0..11]",
                "load:{}->NXM_NX_TUN_ID[0..11]".format(self.self_vni),
                "goto_table:{}".format(TABLE_VLAN_CHECK)
                ])
            ])
        
            
    def del_proxy(self, port, vni):
        utils.execute_list(["ovs-ofctl", "del-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=10, in_port={}".format(TABLE_MPTCP_VLAN, port),
            ])
        utils.execute_list(["ovs-ofctl", "del-flows", "--strict", self.dp_mptcp, 
            "table={}, priority=10, vlan_vid={}".format(TABLE_MPTCP_VLAN, vni),
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
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "".join(["table={}, priority=10, ".format(TABLE_VLAN_CHECK),
                "tun_id=0x{:03x}{:03x}, ".format(expansion["peer_vni"], 
                    self.self_vni
                    ),
                "vlan_vid=0x1{:03x}/0x1fff, ".format(expansion["intercloud_id"]),
                "actions=mod_vlan_vid:{},".format(local_vlan),
                "load:{}->NXM_NX_REG0[],".format(hex(expansion["intercloud_id"])),
                "goto_table:{}".format(TABLE_LEARNING) 
                ])
            ])
        actions=[]
        for expansion_mult in expansions_list:
            actions.append("mod_vlan_vid:{}".format(expansion_mult["intercloud_id"]))
            actions.append("set_field:0x{:03x}{:03x}->tun_id".format(self.self_vni,
                expansion_mult["peer_vni"]
                ))
            actions.append("resubmit(,{})".format(TABLE_SPLIT_MPTCP))
        actions_str = ",".join(actions)
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            "table={}, priority=10, vlan_vid=0x1{:03x}/0x1fff, actions={}".format(
                TABLE_MULTICAST, 
                local_vlan, 
                actions_str
                )
            ])
    
    
    
    
    def del_expansion(self, expansion, expansions_list, local_vlan):
        utils.execute_list(["ovs-ofctl", "del-flows", "--strict", self.dp_tun, 
            "".join(["table={}, priority=10, ".format(TABLE_VLAN_CHECK),
                "tun_id=0x{:x}{:x}, ".format(expansion["peer_vni"], 
                    self.self_vni
                    ),
                "vlan_vid=0x1{:03x}/0x1fff".format(expansion["intercloud_id"])
                ])
            ])
        actions=[]
        for expansion_mult in expansions_list:
            actions.append("mod_vlan_vid:{}".format(expansion_mult["intercloud_id"]))
            actions.append("set_field:0x{:03x}{:03x}->tun_id".format(
                    self.self_vni,
                    expansion_mult["peer_vni"]
                    )
                )
            actions.append("resubmit(,{})".format(TABLE_SPLIT_MPTCP))
        actions_str = ",".join(actions)
        utils.execute_list(["ovs-ofctl", "mod-flows", "--strict", self.dp_tun, 
            " ".join(["table={}, priority=10,".format(TABLE_MULTICAST),
                "vlan_vid=0x1{:03x}/0x1fff,".format(local_vlan),
                "actions={}".format(actions_str)
                ])
            ])
        