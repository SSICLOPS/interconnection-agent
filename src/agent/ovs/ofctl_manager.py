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

def add_flow(switch, *args, strict=True):
    apply(switch, "mod-flows", *args, strict=strict)

def del_flow(switch, *args, strict=True):
    apply(switch, "del-flows", *args, strict=strict)

def apply(switch, action, *args, strict=True):
    cmd = ["ovs-ofctl"]
    cmd.append(action)
    if strict:
        cmd.append("--strict")
    cmd.append(switch)
    if args:
        cmd.append(" ".join(args))
    utils.execute_list(cmd)


class Ofctl_manager(object):

    def __init__(self, **kwargs):
        utils3.set_attributes(self, override = True, **kwargs)

    def init_flows(self):
        self.init_tun()
        self.init_in()
        self.init_out()


    def init_tun(self):
        del_flow(self.dp_tun, strict=False)
        add_flow(self.dp_tun,
            "table={}, priority=0, actions=drop".format(TABLE_START)
            )
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_START),
            "in_port={},".format(self.patch_tun_id),
            "actions=goto_table:{}".format(TABLE_TYPE_SPLIT)
            )
        add_flow(self.dp_tun,"table={}, priority=0,".format(TABLE_VNI_SPLIT),
            "actions=goto_table:{}".format(TABLE_ROUTING)
            )
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_VNI_SPLIT),
            "tun_id={}/0xfff,".format(self.self_vni),
            "actions=goto_table:{}".format(TABLE_VLAN_CHECK)
            )
        add_flow(self.dp_tun,"table={}, priority=0,".format(TABLE_VLAN_CHECK),
            "actions=drop"
            )
        add_flow(self.dp_tun,
            "table={}, priority=0, actions=learn(".format(TABLE_LEARNING),
            "table={}, hard_timeout=300,".format(TABLE_UNICAST_LEARNT),
            "priority=10, NXM_OF_VLAN_TCI[0..11]",
            "NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],",
            "load:NXM_NX_REG0[]->NXM_NX_REG0[],",
            "load:NXM_NX_TUN_ID[0..11]->NXM_NX_REG2[12..23],",
            "load:NXM_NX_TUN_ID[12..23]->NXM_NX_REG2[0..11]),",
            "output:{}".format(self.patch_tun_id)
            )
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_TYPE_SPLIT),
            "dl_dst=00:00:00:00:00:00/01:00:00:00:00:00,",
            "actions=resubmit(,{}),resubmit(,{})".format(
                TABLE_UNICAST_LEARNT, TABLE_UNICAST_APPLY
                )
            )
        add_flow(self.dp_tun,"table={}, priority=10,".format(TABLE_TYPE_SPLIT),
            "dl_dst=01:00:00:00:00:00/01:00:00:00:00:00,",
            "actions=goto_table:{}".format(TABLE_MULTICAST)
            )
        add_flow(self.dp_tun, "table={},".format(TABLE_UNICAST_LEARNT),
            "priority=0, actions=drop"
            )
        add_flow(self.dp_tun, "table={},".format(TABLE_UNICAST_APPLY),
            "priority=20, reg0=0, actions=goto_table:{}".format(TABLE_MULTICAST)
            )
        add_flow(self.dp_tun, "table={},".format(TABLE_UNICAST_APPLY),
            "priority=10,",
            "actions=move:NXM_NX_REG0[0..11]->NXM_OF_VLAN_TCI[0..11],",
            "move:NXM_NX_REG2[0..23]->NXM_NX_TUN_ID[0..23],",
            "goto_table:{}".format(TABLE_SPLIT_MPTCP)
            )
        add_flow(self.dp_tun, "table={}, priority=0,".format(TABLE_MULTICAST),
            "actions=drop"
            )
        add_flow(self.dp_tun, "table={}, priority=0,".format(TABLE_SPLIT_MPTCP),
            "actions=goto_table:{}".format(TABLE_ROUTING)
            )
        add_flow(self.dp_tun, "table={}, priority=0,".format(TABLE_APPLY_MPTCP),
            "actions=goto_table:{}".format(TABLE_ROUTING)
            )
        add_flow(self.dp_tun, "table={}, priority=0,".format(TABLE_ROUTING),
            "actions=drop"
            )

    def init_in(self):
        del_flow(self.dp_in, strict=False)
        add_flow(self.dp_in, "table={}, priority=0,".format(TABLE_START),
            "actions=normal"
            )

    def init_out(self):
        del_flow(self.dp_out, strict=False)
        add_flow(self.dp_out, "table={}, priority=0,".format(TABLE_START),
            "actions=normal"
            )

    def init_mptcp(self, **kwargs):
        utils3.set_attributes(self, override=True, **kwargs)
        del_flow(self.dp_mptcp, strict=False)
        add_flow(self.dp_mptcp, "table={}, priority=0,".format(TABLE_START),
            "actions=goto_table:{}".format(TABLE_MPTCP_VLAN)
            )
        add_flow(self.dp_mptcp, "table={}, priority=10,".format(TABLE_START),
            "in_port={},".format(self.patch_mptcp_port),
            "actions=goto_table:{}".format(TABLE_MPTCP_LEARN)
            )
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_LEARN),
            "priority=10, tcp,",
            "actions=goto_table:{}".format(TABLE_MPTCP_FORWARD)
            )
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_LEARN),
            "priority=10, arp,",
            "actions=learn(table={}, priority=10,".format(TABLE_MPTCP_LEARNT),
            "eth_src=E1:8E:36:8C:F6:0D, eth_type=0x0800,",
            "NXM_OF_IP_DST[]=NXM_OF_ARP_SPA[],",
            "load:NXM_NX_ARP_SHA[]->NXM_OF_ETH_DST[],",
            "output:NXM_OF_IN_PORT[])"
            )
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_LEARN),
            "priority=0, actions=drop"
            )
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_VLAN),
            "priority=0, actions=drop"
            )
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_LEARNT),
            "priority=0, actions=drop"
            )
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_FORWARD),
            "priority=0, actions=drop"
            )

        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_START),
            "in_port={},".format(self.patch_tun_port_mptcp),
            "actions=goto_table:{}".format(TABLE_IN_MPTCP)
            )
        add_flow(self.dp_tun, "table={}, priority=0,".format(TABLE_IN_MPTCP),
            "actions=drop"
            )


    def add_proxy(self, port, vni, eth_addr):
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_VLAN),
            "priority=10, in_port={}".format(port),
            "actions=mod_vlan_vid:{},".format(vni),
            "goto_table:{}".format(TABLE_MPTCP_LEARNT)
            )
        add_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_FORWARD),
            "priority=10, vlan_vid=0x1{:03x}".format(vni),
            "actions=set_field:{}->eth_dst,strip_vlan,".format(eth_addr),
            "output:{}".format(port)
            )
        add_flow(self.dp_tun,"table={}, priority=10,".format(TABLE_APPLY_MPTCP),
            "tcp, tun_id=0x{:x}/0xfff".format(vni),
            "actions=move:NXM_OF_VLAN_TCI[0..11]->NXM_NX_PKT_MARK[0..11]",
            "move:NXM_NX_TUN_ID[0..11]->NXM_OF_VLAN_TCI[0..11]",
            "output:{}".format(self.patch_tun_port_mptcp)
            )
        add_flow(self.dp_tun,"table={}, priority=10,".format(TABLE_APPLY_MPTCP),
            "arp, tun_id=0x{:x}/0xfff".format(vni),
            "actions=resubmit(,{}),".format(TABLE_ROUTING),
            "move:NXM_OF_VLAN_TCI[0..11]->NXM_NX_PKT_MARK[0..11]",
            "move:NXM_NX_TUN_ID[0..11]->NXM_OF_VLAN_TCI[0..11]",
            "output:{}".format(self.patch_tun_port_mptcp)
            )
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_IN_MPTCP),
            "vlan_vid=0x1{:03x}/0x1fff".format(vni),
            "actions=move:NXM_OF_VLAN_TCI[0..11]->NXM_NX_TUN_ID[12..23]",
            "move:NXM_NX_PKT_MARK[0..11]->NXM_OF_VLAN_TCI[0..11]",
            "load:{}->NXM_NX_TUN_ID[0..11]".format(self.self_vni),
            "goto_table:{}".format(TABLE_VLAN_CHECK)
            )


    def del_proxy(self, port, vni):
        del_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_VLAN),
            "priority=10, in_port={}".format(port)
            )
        del_flow(self.dp_mptcp, "table={},".format(TABLE_MPTCP_FORWARD),
            "priority=10, vlan_vid=0x1{:03x}".format(vni)
            )
        del_flow(self.dp_tun,"table={}, priority=10,".format(TABLE_APPLY_MPTCP),
            "tcp, tun_id=0x{:x}/0xfff".format(vni)
            )
        del_flow(self.dp_tun,"table={}, priority=10,".format(TABLE_APPLY_MPTCP),
            "arp, tun_id=0x{:x}/0xfff".format(vni),
            )
        del_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_IN_MPTCP),
            "vlan_vid=0x1{:03x}/0x1fff".format(vni),
            )



    def add_tunnel(self, port_id):
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_START),
            "in_port={}, actions=goto_table:{}".format(port_id, TABLE_VNI_SPLIT)
            )

    def del_tunnel(self, port_id):
        del_flow(self.dp_tun, "table={},".format(TABLE_START),
            "priority=10, in_port={}".format(port_id)
            )


    def add_route(self, vni, port_id):
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_ROUTING),
            "tun_id={}/0xfff, actions=output:{}".format(vni, port_id)
            )

    def del_route(self, vni):
        del_flow(self.dp_tun, "table={},".format(TABLE_ROUTING),
            "priority=10, tun_id={}/0xfff".format(vni)
            )



    def add_expansion(self, expansion, expansions_list, local_vlan):
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_VLAN_CHECK),
            "tun_id=0x{:03x}{:03x},".format(expansion["peer_vni"],self.self_vni),
            "vlan_vid=0x1{:03x}/0x1fff, ".format(expansion["intercloud_id"]),
            "actions=mod_vlan_vid:{},".format(local_vlan),
            "load:{}->NXM_NX_REG0[],".format(hex(expansion["intercloud_id"])),
            "goto_table:{}".format(TABLE_LEARNING)
            )
        if expansion["mptcp"]:
            add_flow(self.dp_tun, "table={},".format(TABLE_SPLIT_MPTCP),
                "priority=10, tun_id=0x{:03x}{:03x},".format(self.self_vni,
                    expansion["peer_vni"]
                    ),
                "vlan_vid=0x1{:03x}/0x1fff,".format(expansion["intercloud_id"]),
                "actions=goto_table:{}".format(TABLE_APPLY_MPTCP)
                )
        actions=[]
        for expansion_mult in expansions_list:
            actions.append("mod_vlan_vid:{}".format(expansion_mult["intercloud_id"]))
            actions.append("set_field:0x{:03x}{:03x}->tun_id".format(self.self_vni,
                expansion_mult["peer_vni"]
                ))
            actions.append("resubmit(,{})".format(TABLE_SPLIT_MPTCP))
        actions_str = ",".join(actions)
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_MULTICAST),
            "vlan_vid=0x1{:03x}/0x1fff,".format(local_vlan),
            "actions={}".format(actions_str)
            )

    def del_expansion(self, expansion, expansions_list, local_vlan):
        del_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_VLAN_CHECK),
            "tun_id=0x{:03x}{:03x},".format(expansion["peer_vni"],self.self_vni),
            "vlan_vid=0x1{:03x}/0x1fff, ".format(expansion["intercloud_id"]),
            )
        if expansion["mptcp"]:
            del_flow(self.dp_tun, "table={},".format(TABLE_SPLIT_MPTCP),
                "priority=10, tun_id=0x{:03x}{:03x},".format(self.self_vni,
                    expansion["peer_vni"]
                    ),
                "vlan_vid=0x1{:03x}/0x1fff,".format(expansion["intercloud_id"]),
                )
        actions=[]
        for expansion_mult in expansions_list:
            actions.append("mod_vlan_vid:{}".format(expansion_mult["intercloud_id"]))
            actions.append("set_field:0x{:03x}{:03x}->tun_id".format(self.self_vni,
                expansion_mult["peer_vni"]
                ))
            actions.append("resubmit(,{})".format(TABLE_SPLIT_MPTCP))
        actions_str = ",".join(actions)
        add_flow(self.dp_tun, "table={}, priority=10,".format(TABLE_MULTICAST),
            "vlan_vid=0x1{:03x}/0x1fff,".format(local_vlan),
            "actions={}".format(actions_str)
            )