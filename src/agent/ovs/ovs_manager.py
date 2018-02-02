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


import os
import subprocess
import logging
import asyncio
import re

import utils
from ovs import ovs_utils
from helpers_n_wrappers import utils3
import pyroute_utils

RETCODE_ERROR = -1
RETCODE_NOTEXIST = 0
RETCODE_NOTOK = 1
RETCODE_OK = 2


_pattern_segId_tun = re.compile("pop_vlan,load:(0x[0-9a-fA-F]+)->NXM_NX_TUN_ID")
_pattern_vlanId_tun = re.compile("dl_vlan=([0-9]+)")



"""
Objects that manages the ovs-setup (= ovs-vsctl)
"""
class Ovs_manager(object):

    def __init__(self, **kwargs):
        self.controller_ip = None
        self.controller_port = None
        utils3.set_attributes(self, override = True, **kwargs)


    def find_port(self, port_name):
        return str(ovs_utils.find_port_id(port_name))
        
    def set_infra(self):
        #Creates the bridges
        self.dpid_in = self.create_bridge(
            self.dp_in, self.controller_ip, self.controller_port)
        self.dpid_tun = self.create_bridge(
            self.dp_tun, self.controller_ip, self.controller_port)
        self.dpid_out = self.create_bridge(
            self.dp_out, self.controller_ip, self.controller_port)

        #Add the patch port beween the tunnel and namespace out bridges
        self.add_patch_port(self.dp_tun, self.dp_out, "patch-tun-out",
            "patch-out-tun"
        )
        
        #add the patch port between br-int and namespace in bridges
        self.add_patch_port( self.internal_bridge, self.dp_in, "patch-int-lan",
            "patch-lan-int"
        )

        #Get the details of OpenStack setup
        if not self.standalone:
            self.opstk_bridge = self.get_openstack_bridge()
            self.version = self.get_openstack_openflow_version(self.opstk_bridge)

        #Get the port numbers
        self.internalPort = str(ovs_utils.find_port_id("patch-lan-int"))
        self.patchOutPort = str(ovs_utils.find_port_id("patch-out-tun"))
        self.patchTunPort = str(ovs_utils.find_port_id("patch-tun-out"))

    def set_infra_mptcp(self, dp_mptcp):
        self.dp_mptcp = dp_mptcp
        self.dpid_mptcp = self.create_bridge(
            self.dp_mptcp, self.controller_ip, self.controller_port)
        #Add the patch port beween the tunnel and namespace out bridges
        self.add_patch_port(self.dp_tun, self.dp_mptcp, "patch-tun-mptcp",
            "patch-mptcp-tun"
        )
        self.patchMptcpPort = str(ovs_utils.find_port_id("patch-mptcp-tun"))
        self.patchTunPortMptcp = str(ovs_utils.find_port_id("patch-tun-mptcp"))

    #Find the tunneling bridge of OpenStack (br-tun for GRE/vxlan or br-prv for
    #vlans
    def get_openstack_bridge(self):
        bridges = utils.execute("ovs-vsctl show")
        if "br-tun" in bridges:
            logging.info("OpenStack bridge br-tun detected")
            return "br-tun"
        else:
            logging.info("No OpenStack bridge detected")
            return None

    def get_openstack_openflow_version(self, bridge):
        if bridge is None:
            return 13
        protocols = utils.execute(
            "ovs-vsctl get bridge {} protocols".format(bridge))
        if "OpenFlow13" in protocols:
            return 13
        elif "OpenFlow10" in protocols:
            return 10
        else:
            return 13


    #Creates the bridge, configures it and return the DPID
    def create_bridge(self, bridge_name, ip, port):
        ovs_utils.add_bridge(bridge_name, silent=True)
        if ip is not None and port is not None:
            ovs_utils.configure_bridge(bridge_name, ip, port, "OpenFlow13")
        dpid = ovs_utils.get_dpid(bridge_name, "openflow13")
        logging.info("Bridge {} ({}) set".format(bridge_name, dpid))
        return dpid




    def check_existing_tunnels(self, local_ip, remote_ip, proto):
        output = utils.execute_list(["ovs-vsctl", "--columns=name",
            "find", "interface", "{}{}{}".format(
                "options={df_default=False, in_key=flow, ",
                "local_ip=\"{}\", out_key=flow, ".format(local_ip),
                "remote_ip=\"{}\" tos=inherit}}".format( remote_ip)
                ),
            "type={}".format(proto)
            ])
        if output:
            name = output.split(":")[1].split()[0]
            return name[1:-1]
        return None
        
    
    # Get the port configuration, and check it using the callback function
    def _check_port(self, port_name, bridge, check_function, func_args):
        #Get the port configuration
        output = utils.execute( "{}{}".format(
            "ovs-vsctl --columns=name,type,options find interface ",
            "name={}".format( port_name )
            ))
        if port_name not in output:
            return RETCODE_NOTEXIST
        
        #Check it is on the correct bridge
        output2 = utils.execute("ovs-vsctl port-to-br {}".format(port_name))
        if output2.split()[0] != bridge:
            return RETCODE_NOTOK
        
        #Check the configuration by calling the callback
        if check_function(output, *func_args):
            return RETCODE_OK
        
        return RETCODE_NOTOK

    #Callback for patch port
    def _patch_port_conf_check(self, output, peer):
        if output.find("type") == -1 or output.find("peer") == -1:
            return False
        return (output.split("type")[1].split(":")[1].split()[0].startswith(
                'patch'
            ) and
            output.split("peer")[1].split("=")[1].split()[0].startswith(peer)
        )

    #Callback for tun port
    def _tun_port_conf_check(self, output, proto, local_ip, remote_ip):
        if output.find("type") == -1 or output.find("local_ip") == - \
                1 or output.find("remote_ip") == -1:
            return False
        return (output.split("type")[1].split(":")[1].split()[0].startswith(proto)
            and output.split("local_ip")[1].split("=")[1].split()[0].startswith("\"" + local_ip)
            and output.split("remote_ip")[1].split("=")[1].split()[0].startswith("\"" + remote_ip)
            and output.split("in_key")[1].split("=")[1].split()[0].startswith("flow")
            and output.split("out_key")[1].split("=")[1].split()[0].startswith("flow")
        )
        
    #Callback for internal port
    def _internal_port_conf_check(self, output):
        if output.find("type") == -1:
            return False
        return output.split("type")[1].split(
            ":")[1].split()[0].startswith('internal')





    def _add_port(self, ret, name, bridge, args={}, vlan=None, mode="trunk", 
            recreate = False):
        if ret == RETCODE_ERROR:
            raise RuntimeError
        #Incorrect configuration, delete the port to recreate
        if ret == RETCODE_NOTOK or (ret == RETCODE_OK and recreate):
            self.del_port(name)
            logging.debug("Port {} deleted for incorrect configuration".format(
                name
                ))
            ret = RETCODE_NOTOK
        #Create the port and modify the configuration
        if ret != RETCODE_OK:
            ovs_utils.add_port(bridge, name, vlan=vlan, mode=mode, silent=True)
            ovs_utils.modify_port(name, True, **args)
            logging.debug("Port {} created".format( name ))
        else:
            logging.debug("Port {} exists".format( name ))


    #Add a pair of patch port with correct arguments
    def add_patch_port(self, left_bridge, right_bridge, left_port = None,
            right_port = None):
        # Set port names by default
        if not left_port:
            left_port = "patch-{}-{}".format(left_bridge, right_bridge)
        if not right_port:
            right_port = "patch-{}-{}".format(right_bridge, left_bridge)
        
        #Check the ports configuration and act upon to add correct port
        ret = self._check_port(left_port, left_bridge,
                             self._patch_port_conf_check, [right_port])
        self._add_port(ret, left_port, left_bridge, args={
            "type": "patch", "options:peer": right_port
            })
        
        ret = self._check_port(right_port, right_bridge,
            self._patch_port_conf_check, [left_port]
            )
        self._add_port(ret, right_port, right_bridge, args={
            "type": "patch", "options:peer": left_port
            })

    #Add a tunnel port
    def add_tun_port(self, peer_port_name, local_ip, remote_ip, proto):
        #Check if the tunnel already exists or not
        tunnel = self.check_existing_tunnels(local_ip, remote_ip, proto)
        
        #If tunnel exists, then return
        if tunnel is not None:
            logging.debug("Tunnel ({},{}) exists : {}".format(
                local_ip, remote_ip, tunnel
                ))
            return (tunnel, ovs_utils.find_port_id(tunnel))
        
        #Else add the port
        self._add_port(RETCODE_NOTEXIST, peer_port_name, self.dp_tun,
            args={
                "type": proto,
                "options:df_default": "\"False\"",
                "options:tos": "inherit",
                "options:in_key": "flow",
                "options:out_key": "flow",
                "options:local_ip": local_ip,
                "options:remote_ip": remote_ip
                }
            )
        return (peer_port_name, ovs_utils.find_port_id(peer_port_name))

    def add_internal_port(self, bridge, name, vlan=None, recreate=False):
        ret = self._check_port(name, bridge, self._internal_port_conf_check, [])
        self._add_port(ret, name, bridge, args={
                "type": "internal"
                }, vlan=vlan, mode="access",
            recreate=recreate
            )    
        
        

    def del_port(self, name):
        ovs_utils.delete_port(silent=True, port_name=name)
        logging.debug("Port {} deleted".format(name))
    
    def del_tun_port(self, peer_port_name, local_ip, remote_ip, proto):
        ret = self._check_port(peer_port_name, self.dp_tun,
            self._tun_port_conf_check, [proto, local_ip, remote_ip]
            )
        if ret != RETCODE_NOTEXIST:
            self.del_port(peer_port_name)
            logging.debug("Tunnel {} ({},{}) deleted".format(
                peer_port_name, local_ip, remote_ip
                ))
        else:
            logging.debug("Tunnel {} ({},{}) does not exist".format(
                peer_port_name, local_ip, remote_ip
                ))






    async def get_network_vlans(self, amqp):
        #If standalone, the cloud network id is also the vlan
        if self.standalone:
            return
        
        #loop to detect any vlan changes
        while True:
            tmp_network_mapping = {}
            
            #Create the exec list based on the switch and version of OpenStack
            exec_list = ['ovs-ofctl', 'dump-flows']
            exec_list.append(self.opstk_bridge)
            if self.opstk_bridge == "br-tun":
                pattern_segId = _pattern_segId_tun
                pattern_vlanId = _pattern_vlanId_tun
            if self.version == 13:    
                exec_list.append("-O")
                exec_list.append("openflow13")
            
            flows = utils.execute_list(exec_list).split("\n")
            
            for flow in flows:
                #Check the flows in table 22 only (flood)
                if 'table=22' not in flow:
                    continue
                
                #Search the network, if not found, continue
                match = pattern_segId.search(flow)
                if not match:
                    continue
                segId_hex = match.group(1)
                
                #network found, search the vlan
                match = pattern_vlanId.search(flow)
                if not match:
                    continue
                vlan_id = match.group(1)
                
                tmp_network_mapping[int(segId_hex,0)] = int(vlan_id)  
            
            #If there has been a change, modify the heartbeat to notify the
            #controller
            if amqp.agent.networks_mapping != tmp_network_mapping:
                amqp.modify_networks_mapping_hb_payload(
                    tmp_network_mapping
                )
            await asyncio.sleep(3)

