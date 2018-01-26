import traceback
import os
import subprocess
#from uuid import uuid4
import utils
import re
#from IPy import IP
#from pyrouteUtils import createIpr, closeIPR, getInterfaceIP, createLink, getLink, setUp, addIfBr, InterfaceNotFound
#import netns as netns_manager
#import pyrouteUtils as pyrouteWrapper
#import iptablesHelper as vpnIptables
#from multiprocessing import Process
#from pyroute2 import netlink
from ovs import ovs_utils
import logging
from helpers_n_wrappers import utils3
import asyncio

RETCODE_ERROR = -1
RETCODE_NOTEXIST = 0
RETCODE_NOTOK = 1
RETCODE_OK = 2


pattern_segId_tun = re.compile("pop_vlan,load:(0x[0-9a-fA-F]+)->NXM_NX_TUN_ID")
pattern_vlanId_tun = re.compile("dl_vlan=([0-9]+)")




class Ovs_manager(object):

    def __init__(self, **kwargs):
        self.controller_ip = None
        self.controller_port = None
        utils3.set_attributes(self, override = True, **kwargs)




    def set_infra(self):
        self.dpid_in = self.create_bridge(
            self.dp_in, self.controller_ip, self.controller_port)
        self.dpid_tun = self.create_bridge(
            self.dp_tun, self.controller_ip, self.controller_port)
        self.dpid_out = self.create_bridge(
            self.dp_out, self.controller_ip, self.controller_port)

        self.add_patch_port(self.dp_tun, self.dp_out, "patch-tun-out",
            "patch-out-tun"
        )
        self.add_patch_port( self.internal_bridge, self.dp_in, "patch-int-lan",
            "patch-lan-int"
        )

        self.opstk_bridge = self.get_openstack_bridge()
        self.version = self.get_openstack_openflow_version(self.opstk_bridge)

        self.internalPort = str(ovs_utils.find_port_id("patch-lan-int"))
        self.patchOutPort = str(ovs_utils.find_port_id("patch-out-tun"))
        self.patchTunPort = str(ovs_utils.find_port_id("patch-tun-out"))




    def get_openstack_bridge(self):
        bridges = utils.execute("ovs-vsctl show")
        if "br-tun" in bridges:
            logging.info("br-tun detected")
            return "br-tun"
        #elif "br-prv" in bridges:
        #    logging.info("br-prv detected")
        #    return "br-prv"
        else:
            logging.info("No OpenStack bridge detected")
            return None

    def get_openstack_openflow_version(self, bridge):
        if bridge is None:
            return 13
        protocols = utils.execute(
            "ovs-vsctl get bridge " + bridge + " protocols")
        if "OpenFlow13" in protocols:
            return 13
        elif "OpenFlow10" in protocols:
            return 10
        else:
            return 13


    def create_bridge(self, bridge_name, ip, port):
        ovs_utils.add_bridge(bridge_name, silent=True)
        if ip is not None and port is not None:
            ovs_utils.configure_bridge(bridge_name, ip, port, "OpenFlow13")
        dpid = ovs_utils.get_dpid(bridge_name, "openflow13")
        logging.info("Bridge " + dpid + " (" + bridge_name + ") set")
        return dpid




    def check_port(self, port_name, bridge, check_function, func_args):
        output = utils.execute(
            "ovs-vsctl --columns=name,type,options find interface \
name={}".format( port_name )
        )
        if port_name not in output:
            return RETCODE_NOTEXIST
        output2 = utils.execute("ovs-vsctl port-to-br {}".format(port_name))
        if output2.split()[0] != bridge:
            return RETCODE_NOTOK
        if check_function(output, *func_args):
            return RETCODE_OK
        return RETCODE_NOTOK

    def patch_port_conf_check(self, output, peer):
        if output.find("type") == -1 or output.find("peer") == -1:
            return False
        return (output.split("type")[1].split(":")[1].split()[0].startswith(
                'patch'
            ) and
            output.split("peer")[1].split("=")[1].split()[0].startswith(peer)
        )

    def tun_port_conf_check(self, output, proto, local_ip, remote_ip):
        if output.find("type") == -1 or output.find("local_ip") == - \
                1 or output.find("remote_ip") == -1:
            return False
        return (output.split("type")[1].split(":")[1].split()[0].startswith(proto)
            and output.split("local_ip")[1].split("=")[1].split()[0].startswith("\"" + local_ip)
            and output.split("remote_ip")[1].split("=")[1].split()[0].startswith("\"" + remote_ip)
            and output.split("in_key")[1].split("=")[1].split()[0].startswith("flow")
            and output.split("out_key")[1].split("=")[1].split()[0].startswith("flow")
        )





    def _add_port(self, ret, name, bridge, args={}, vlan=None):
        if ret == RETCODE_ERROR:
            raise RuntimeError
        if ret == RETCODE_NOTOK:
            ovs_utils.delete_port(silent=True, port_name=name)
            logging.info("Port " + name +
                          " deleted for incorrect configuration")
        if ret != RETCODE_OK:
            ovs_utils.add_port(bridge, name, vlan=vlan,
                              mode="trunk", silent=True)
            ovs_utils.modify_port(name, True, **args)
            logging.info("Port " + name + " created")
        else:
            logging.info("Port " + name + " exists")


    def add_patch_port(self, left_bridge, right_bridge, left_port = None,
            right_port = None):
        if not left_port:
            left_port = "patch-{}-{}".format(left_bridge, right_bridge)
        if not right_port:
            right_port = "patch-{}-{}".format(right_bridge, left_bridge)
        ret = self.check_port(left_port, left_bridge,
                             self.patch_port_conf_check, [right_port])
        self._add_port(ret, left_port, left_bridge, args={
                            "type": "patch", "options:peer": right_port})
        ret = self.check_port(right_port, right_bridge,
                             self.patch_port_conf_check, [left_port])
        self._add_port(ret, right_port, right_bridge, args={
                            "type": "patch", "options:peer": left_port})

    def add_tun_port(self, peer_port_name, local_ip, remote_ip, proto):
        tunnel = self.check_existing_tunnels(local_ip, remote_ip, proto)
        if tunnel is not None:
            logging.info("Tunnel ({},{}) exists : {}".format(
                local_ip, remote_ip, tunnel))
            return (tunnel, ovs_utils.find_port_id(tunnel))
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





    def del_tun_port(self, peer_port_name, local_ip, remote_ip, proto):
        ret = self.check_port(peer_port_name, self.dp_tun,
            self.tun_port_conf_check, [proto, local_ip, remote_ip]
        )
        if ret != RETCODE_NOTEXIST:
            ovs_utils.delete_port(silent=True, port_name=peer_port_name)
            logging.info("Tunnel {} ({},{}) deleted".format(
                peer_port_name, local_ip, remote_ip))
        else:
            logging.info("Tunnel {} ({},{}) does not exist".format(
                peer_port_name, local_ip, remote_ip))




    def check_existing_tunnels(self, local_ip, remote_ip, proto):
        output = utils.execute_list(["ovs-vsctl", "--columns=name",
            "find", "interface", "options={{df_default=False, in_key=flow, \
local_ip=\"{}\", out_key=flow, remote_ip=\"{}\" tos=inherit}}".format(
                local_ip, remote_ip
            ), "type={}".format(proto)]
        )
        if output:
            name = output.split(":")[1].split()[0]
            return name[1:-1]
        return None

    async def get_network_vlans(self, amqp):
        if self.standalone:
            return
        while True:
            tmp_network_mapping = {}
            exec_list = ['ovs-ofctl', 'dump-flows']
            if self.opstk_bridge == "br-tun":
                exec_list.append(self.opstk_bridge)
                pattern_segId = pattern_segId_tun
                pattern_vlanId = pattern_vlanId_tun
            #elif self.opstk_bridge == "br-prv":
            #    exec_list.append(self.opstk_bridge)
            #    pattern_segId = 
            #    pattern_vlanId =
            if self.version == 13:    
                exec_list.append("-O")
                exec_list.append("openflow13")
            flows = utils.execute_list(exec_list).split("\n")
            for flow in flows:
                if 'table=22' not in flow:
                    continue
                match = pattern_segId.search(flow)
                if not match:
                    continue
                segId_hex = match.group(1)
                match = pattern_vlanId.search(flow)
                if not match:
                    continue
                vlan_id = match.group(1)
                tmp_network_mapping[int(segId_hex,0)] = int(vlan_id)  
            if amqp.agent.networks_mapping != tmp_network_mapping:
                amqp.modify_networks_mapping_hb_payload(
                    tmp_network_mapping
                )
            await asyncio.sleep(3)











#class OVSAgent(object):
#
#    def __init__(self, log, dp_in="br-cloud", dp_tun="br-cloud-tun",
#                 dp_out="br-cloud-out", internal_bridge="br-int", proto="gre", standalone=False, local=False):
#        self.log = log
#        self.dp_in = dp_in
#        self.dp_out = dp_out
#        self.dp_tun = dp_tun
#        self.internal_bridge = internal_bridge
#        if self.internal_bridge is not None:
#            self.internalPort = str(ovsUtils.find_port_id(
#                self.dp_in + "-" + self.internal_bridge))
#        else:
#            self.internalPort = None
#        self.peer_clouds = {}
#        self.ipr = createIpr()
#        self.netIpr = {}
#        self.standalone = standalone
#        self.local = local
#        self.proto = proto
#        self.defaultNetNS = netns_manager.DefaultNetNS()
#
#    def __del__(self):
#        if self.ipr:
#            closeIPR(self.ipr)
#
#    def create_bridge(self, bridgeName, ip, port):
#        ovsUtils.add_bridge(bridgeName, silent=True)
#        ovsUtils.configure_bridge(bridgeName, ip, port, "OpenFlow13")
#        dpid = ovsUtils.get_dpid(bridgeName, "openflow13")
#        self.log.info("Bridge " + dpid + " (" + bridgeName + ") set")
#        return dpid
#
#    def createMPTCPBridge(self):
#        ovsUtils.add_bridge("br-cloud-mptcp", silent=True)
#        ovsUtils._add_port("br-cloud-out", "patchout-cm", silent=True)
#        ovsUtils.modify_port(
#            "patchout-cm", **{"type": "patch", "options:peer": "patchcm-out"})
#        ovsUtils._add_port("br-cloud-mptcp", "patchcm-out", silent=True)
#        ovsUtils.modify_port(
#            "patchcm-out", **{"type": "patch", "options:peer": "patchout-cm"})
#
#    def setDpid(self, dpid):
#        self.dpid = dpid
#
#
#
#
#
#    def get_network_vlan(self, segmentation_id):
#        if isinstance(segmentation_id, int):
#            seg_id_str = hex(segmentation_id)
#            seg_id_int = segmentation_id
#        elif isinstance(segmentation_id, str):
#            seg_id_int = int(segmentation_id, 16)
#            seg_id_str = segmentation_id
#        # find the internal vlan ID used by the agent by parsing the command
#        # line output, different cases if vlan or GRE/Vxlan
#        if self.version == 13:
#            exec_str = "ovs-ofctl -O openflow13 dump-flows "
#        else:
#            exec_str = "ovs-ofctl dump-flows "
#
#        if self.opstkBridge == "br-tun":
#            exec_str += "br-tun | grep "
#            if self.version == 13:
#                exec_str += "'" + seg_id_str + "->tun_id'"
#            elif self.version == 10:
#                exec_str += "set_tunnel:" + seg_id_str
#
#        elif self.opstkBridge == "br-prv":
#            exec_str += "br-prv | grep "
#            if self.version == 13:
#                exec_str += "'" + str(seg_id_int + 4096) + "->vlan_vid'"
#            elif self.version == 10:
#                exec_str += "mod_vlan_vid:" + seg_id_str
#
#        try:
#            flow = utils.execute_with_shell(exec_str)
#        except OSError as e:
#            if e.errno == 1:
#                self.log.info("Vlan for " + seg_id_str + " is None")
#                return None
#            else:
#                raise e
#
#        if flow.find("dl_vlan=") >= 0:
#            vlan = int(flow.split("dl_vlan=", 1)[1].split()[0].split(",")[0])
#        else:
#            vlan = None
#        self.log.info("Vlan for " + seg_id_str + " is " + str(vlan))
#        return vlan
#
#    def check_network_vlan(self, vlan):
#        output = utils.execute("ovs-vsctl list-ports " + self.internal_bridge)
#        for port in output.split():
#            vlan_check_line = utils.execute("ovs-vsctl find port name=" + port)
#            if vlan_check_line.split("tag")[1].split(
#                    ":")[1].split()[0] == str(vlan):
#                return True
#        return False
#
#    def dummyPortConfCheck(self):
#        return True
#
#
#
#    def checkInternalPortConf(self, output):
#        if output.find("type") == -1:
#            return False
#        return output.split("type")[1].split(
#            ":")[1].split()[0].startswith('internal')
#
#
#
#
#
#
#    def addPhysicalPort(self, bridgeName, portName, vlan):
#        ret = self.checkPort(portName, bridgeName, self.dummyPortConfCheck, [])
#        self._add_port(ret, portName, bridgeName, vlan=vlan)
#
#    def delPhysicalPort(self, portName):
#        ovsUtils.delete_port(silent=True, port_name=portName)
#
#    """
#    Check if the patch port exists, if not, create on both sides. Correct a wrong patch port.
#    """
#
#    def add_patch_port(self, internalBridge="br-int",
#                     intercoBridge="br-cloud", patch_name1=None, patch_name2=None):
#        if patch_name1 is None:
#            patch_name1 = internalBridge + "-" + intercoBridge
#        if patch_name2 is None:
#            patch_name2 = intercoBridge + "-" + internalBridge
#        ret = self.checkPort(patch_name1, internalBridge,
#                             self.patchPortConfCheck, [patch_name2])
#        self._add_port(ret, patch_name1, internalBridge, args={
#                            "type": "patch", "options:peer": patch_name2})
#        ret = self.checkPort(patch_name2, intercoBridge,
#                             self.patchPortConfCheck, [patch_name1])
#        self._add_port(ret, patch_name2, intercoBridge, args={
#                            "type": "patch", "options:peer": patch_name1})
#
#    """
#    Check if the internal port exists, if not, create. Correct a wrong internal port.
#    """
#
#    def addInternalPort(self, bridge, name, vlans):
#        if name is None or bridge is None:
#            patch_name1 = internalBridge + "-" + intercoBridge
#        ret = self.checkPort(name, bridge, self.checkInternalPortConf, [])
#        self._add_port(ret, name, bridge, args={
#                            "type": "internal"}, vlan=vlans)
#
#    def updateTunPort(self, peerPortName, local_ip, remote_ip, ip_version):
#        if ip_version == 4:
#            return self.updateTunPortv4(
#                peerPortName, self.dp_tun, local_ip, remote_ip)
#        elif ip_version == 6:
#            return self.updateTunPortv6(
#                peerPortName, self.dp_tun, local_ip, remote_ip)
#
#    def updateTunPortv4(self, peerPortName, bridge, local_ip, remote_ip):
#        ret = self.checkPort(peerPortName, bridge, self.tunPortConfCheck, [
#                             self.proto, local_ip, remote_ip])
#        self._add_port(ret, peerPortName, ovsUtils.addTunPort, bridge, args={
#                            "type": self.proto, "options:df_default": "\"False\"", "options:tos": "inherit", "options:in_key": "flow", "options:out_key": "flow", "options:local_ip": local_ip, "options:remote_ip": remote_ip})
#        return ovsUtils.find_port_id(peerPortName)
#
#    def updateTunPortv6(self, peerPortName, bridge, local_ip, remote_ip):
#        # TODO
#        return ovsUtils.find_port_id(peerPortName)

#
#    def find_ips(self, interfaces):
#        addresses = set()
#        for interface in interfaces:
#            for address in getInterfaceIP(self.ipr, interface):
#                addresses.add(address)
#        self.log.info("Found ips " + str(addresses))
#        return addresses
#
#    def updatePort(self, node_id, vlan, networkId):
#
#        inPort = int(ovsUtils.find_port_id("vethinns" + str(vlan)))
#        outPort = int(ovsUtils.find_port_id("vethoutns" + str(vlan)))
#        netPort = None
#        if self.standalone:
#            netPort = int(ovsUtils.find_port_id(networkId))
#        self.log.info("Network {} in-port: {}, out-port:{}, standalone port: {}".format(
#            node_id, inPort, outPort, netPort if self.standalone else "None"))
#        return (inPort, outPort, netPort)
#
#    def removeNetns(self, node_id, vlan, networkId):
#        ovsUtils.delPort("vethinns" + str(vlan))
#        ovsUtils.delPort("vethoutns" + str(vlan))
#        pyrouteWrapper.delNetNS("mtu-" + networkId)
#        if self.standalone:
#            ovsUtils.delete_port(silent=True, port_name=networkId)
#        self.log.info("Network {} namespace removed".format(node_id))
#
#    def createLinks(self, node_id, vlan, mtu_wan, mtu_lan,
#                    networkId, recreatePort=False):
#        if self.standalone:
#            ovsUtils.delete_port(silent=True, port_name=networkId)
#
#        if recreatePort:
#            ovsUtils.delPort("vethinns" + str(vlan), silent=True)
#            ovsUtils.delPort("vethoutns" + str(vlan), silent=True)
#        self.addInternalPort(self.dp_in,
#                             "vethinns" + str(vlan), str(vlan))
#        self.addInternalPort(self.dp_out,
#                             "vethoutns" + str(vlan), str(vlan))
#        try:
#            pyrouteWrapper.setMtu(self.ipr, 'vethinns' + str(vlan), mtu_lan)
#        except BaseException:
#            pass
#        try:
#            pyrouteWrapper.setMtu(self.ipr, 'vethoutns' + str(vlan), mtu_lan)
#        except BaseException:
#            pass
#        if self.standalone:
#            ovsUtils._add_port(self.dp_in, networkId, silent=True)
#        self.log.info("Network {} links created".format(node_id))
#
#    """
#    Modify the link MTU, set the clamping rules, reset other Iptables rules, restart the ICMP responder
#    """
#
#    def updateMTUWan(self, node_id, vlan, networkId, mtu_wan, mtu_lan, mtu):
#        vlan = str(vlan)
#
#        ns = pyrouteWrapper.getNetNS("mtu-" + networkId)
#        self.log.info("mtu_lan : {} type: {}".format(mtu, type(mtu)))
#        pyrouteWrapper.setMtu(ns, 'vethoutns' + vlan, mtu_lan)
#        pyrouteWrapper.setMtu(ns, 'vethinns' + vlan, mtu_lan)
#        pyrouteWrapper.setMtu(ns, 'lxb', mtu_lan)
#        pyrouteWrapper.setMtu(ns, 'lxb.' + vlan, mtu_lan)
#        ns.close()
#
#        with netns_manager.NetNS("mtu-" + networkId):
#            low_mtu = mtu_wan if mtu_wan < mtu_lan else mtu_lan
#            vpnIptables.delRules(vpnIptables.defTCPClamping(
#                [("vethinns" + str(vlan), low_mtu - 40), ("vethoutns" + str(vlan), low_mtu - 40)]))
#            mtu_wan = mtu
#            vpnIptables.addRules(vpnIptables.defTCPClamping(
#                [("vethinns" + str(vlan), low_mtu - 40), ("vethoutns" + str(vlan), low_mtu - 40)]))
#
#        self.log.info("Network {} mtu updated to {} and TCP clamping to {}".format(
#            node_id, str(mtu_lan), str(mtu_wan)))
#
#    """
#    Create the namespace, the linux bridge and add all the links to the namespace and bridge
#    """
#
#    def addNetns(self, node_id, networkId, vlan, mtu_wan, mtu_lan):
#        pyrouteWrapper.createNetNS("mtu-" + networkId)
#        self.defaultNetNS.resetNetNS()
#        ns = pyrouteWrapper.getNetNS("mtu-" + networkId)
#        pyrouteWrapper.createLink(ns, 'lxb', 'bridge')
#        pyrouteWrapper.createVlan(ns, 'lxb.' + str(vlan), 'lxb', vlan)
#        idx_in = pyrouteWrapper.setNetNS(
#            self.ipr, "mtu-" + networkId, interfaceName='vethinns' + str(vlan))
#        idx_out = pyrouteWrapper.setNetNS(
#            self.ipr, "mtu-" + networkId, interfaceName='vethoutns' + str(vlan))
#        idx_lxb = pyrouteWrapper.addIfBr(ns, ifIdx=idx_in, brName='lxb')[1]
#        idx_lxb = pyrouteWrapper.addIfBr(ns, ifIdx=idx_out, brName='lxb')[1]
#        pyrouteWrapper.setUp(ns, idx=idx_in)
#        pyrouteWrapper.setUp(ns, idx=idx_out)
#        pyrouteWrapper.setUp(ns, idx=idx_lxb)
#        ns.close()
#
#        with netns_manager.NetNS("mtu-" + networkId):
#            vpnIptables.addRules(vpnIptables.defInputOutputDrop())
#            vpnIptables.addRules(vpnIptables.defNoTrack())
#            utils.execute("sysctl -w net.ipv6.conf.lxb.disable_ipv6=1")
#            utils.execute("sysctl -w net.ipv6.conf.lxb/" +
#                          str(vlan) + ".disable_ipv6=1")
#
#        return
#
#    def setNetUp(self, networkId, vlan):
#
#        ns = pyrouteWrapper.getNetNS("mtu-" + networkId)
#        for iface in [
#                "vethinns" + str(vlan), "vethoutns" + str(vlan), "lxb", "lxb" + str(vlan)]:
#            try:
#                idx = pyrouteWrapper.getLink(self.ipr, iface)
#            except pyrouteWrapper.InterfaceNotFound:
#                continue
#            pyrouteWrapper.setUp(self.ipr, idx=idx)
#        ns.close()
#
#        self.log.info("Network {} set up".format(networkId))
#
#    def setNetDown(self, networkId, vlan):
#
#        ns = pyrouteWrapper.getNetNS("mtu-" + networkId)
#        for iface in [
#                "vethinns" + str(vlan), "vethoutns" + str(vlan), "lxb", "lxb" + str(vlan)]:
#            try:
#                idx = pyrouteWrapper.getLink(self.ipr, iface)
#            except pyrouteWrapper.InterfaceNotFound:
#                continue
#            pyrouteWrapper.setDown(self.ipr, idx=idx)
#        ns.close()
#
#        self.log.info("Network {} set down".format(networkId))
#
#    """
#    Set up ebtables and iptables for the namespace. start the queues processes
#    """
#
#    def setIptables(self, networkId, vlan, mtu_wan, mtu_lan):
#
#        with netns_manager.NetNS("mtu-" + networkId):
#            low_mtu = mtu_wan if mtu_wan < mtu_lan else mtu_lan
#            vpnIptables.addRules(vpnIptables.defTCPClamping(
#                [("vethinns" + str(vlan), low_mtu), ("vethoutns" + str(vlan), low_mtu)]))
#
#        self.log.info("Network {} iptables rules added".format(networkId))
#
#    def initTCNamespace(self, ns, iface):
#        pyrouteWrapper.tc_add_qdisc(ns, iface, 'prio', 0x1, bands=8, priomap=(
#            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
#        for i in xrange(0x1, 0x9):
#            pyrouteWrapper.tc_add_qdisc(ns, iface, 'prio', 0x10 + i, parent=0x10000 + i,
#                                        bands=2, priomap=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
#
#    def initTCNetwork(self, ns, iface, vlan):
#        for i in xrange(0, 8):
#            try:
#                pyrouteWrapper.tc_del_filter(ns, iface, 0x10 + i + 0x1, 0x1)
#            except BaseException:
#                pass
#            pyrouteWrapper.tc_add_filter(
#                ns, iface, 0x10 + i + 0x1, 0x1, vlan, i)
#