from pyroute2 import IPRoute, netns, netlink, NetNS, protocols
#import utils
import parse
import platform
from socket import AF_INET


def createIpr():
    return IPRoute()


def createLink(ipr, name, type, peerName=None):
    if not ipr or not name or not type or (type == 'veth' and not peerName):
        raise UndefinedInterface("Cannot create link")
    try:
        if type == 'veth':
            ipr.link('add', ifname=name, kind=type, peer=peerName)
        elif type == 'bridge':
            ipr.link('add', ifname=name, kind=type)
    except netlink.NetlinkError as e:
        if e.code != 17:
            raise e
    return getLink(ipr, name)


def createVlan(ipr, name, link, vlan_id):
    if not ipr or not name or not link or not vlan_id:
        raise UndefinedInterface("Cannot create link")
    try:
        ipr.link('add', ifname=name, kind="vlan",
                 link=getLink(ipr, link), vlan_id=vlan_id)
    except netlink.NetlinkError as e:
        if e.code != 17:
            raise e
    return getLink(ipr, name)


def getLink(ipr, name):
    if not ipr or not name:
        raise UndefinedInterface("Cannot find link")
    idx = ipr.link_lookup(ifname=name)
    if not idx:
        raise InterfaceNotFound("Interface " + name + " not found")
    return idx[0]


def setMtu(ipr, name, mtu, idx=None, netns=None):
    if not ipr or (not name and not idx) or not mtu:
        raise UndefinedInterface("Cannot set MTU")
    if not idx:
        idx = getLink(ipr, name)
    if idx:
        ipr.link("set", index=idx, mtu=mtu)
    return idx


def setUp(ipr, name=None, idx=None, netns=None):
    if not ipr or (not name and not idx):
        raise UndefinedInterface("Cannot set link up")
    if idx is None and name is not None:
        idx = getLink(ipr, name)
    ipr.link('set', index=idx, state="up")
    return idx


def setDown(ipr, name=None, idx=None, netns=None):
    if not ipr or (not name and not idx):
        raise UndefinedInterface("Cannot set link down")
    if idx is None and name is not None:
        idx = getLink(ipr, name)
    ipr.link('set', index=idx, state="down")
    return idx


def createNetNS(name):
    if not name:
        raise UndefinedNamespace("Cannot find namespace")
    try:

        return netns.create(name)
    except OSError as e:
        if e.errno != 17:
            raise e


def delNetNS(name):
    netns.remove(name)


def getNetNS(name):
    if not name:
        raise UndefinedNamespace("Cannot find namespace")
    return NetNS(name)


"""
Set the interface to a namespace, try to find it first in the root namespace, then in the given namespace. If failed, return None
"""


def setNetNS(ipr, namespace, interfaceName=None, interfaceIdx=None):
    if not namespace:
        raise UndefinedNamespace("Cannot find namespace")
    if not ipr or (not interfaceName and not interfaceIdx):
        raise UndefinedInterface("Cannot set namespace")
    if interfaceIdx is None and interfaceName is not None:
        try:
            interfaceIdx = getLink(ipr, interfaceName)
        except InterfaceNotFound:
            interfaceIdx = None
    if not interfaceIdx:
        ns = getNetNS(namespace)
        interfaceIdx = getLink(ns, interfaceName)
        ns.close()
        if interfaceIdx:
            return interfaceIdx
        else:
            raise InterfaceNotFound()
    try:

        ipr.link('set', index=interfaceIdx, net_ns_fd=namespace)
    except netlink.NetlinkError as e:
        if e.code != 17:
            raise e
    return interfaceIdx


def addIfBr(ipr, ifName=None, ifIdx=None, brName=None, brIdx=None):
    if not ipr or (not ifName and not ifIdx) or (not brName and not brIdx):
        raise UndefinedInterface("Cannot add interface to bridge")
    if ifIdx is None and ifName is not None:
        ifIdx = getLink(ipr, ifName)
    if brIdx is None and brName is not None:
        brIdx = getLink(ipr, brName)
    try:
        ipr.link("set", index=ifIdx, master=brIdx)
    except netlink.NetlinkError as e:
        if e.code != 17:
            raise e
    return (ifIdx, brIdx)


def delLink(ipr, name=None, idx=None):
    if not ipr or (not name and not idx):
        raise UndefinedInterface("Cannot delete link")
    if idx is None and name is not None:
        idx = getLink(ipr, name)
    try:
        ipr.link('del', index=idx)
    except netlink.NetlinkError as e:
        if e.code != 19:
            raise e
    return None


def closeIPR(ipr):
    ipr.close()


def getInterfaceIP(ipr, name):
    addr_attrs = ipr.get_addr(family=AF_INET, label=name)
    addresses = set()
    for address in addr_attrs:
        for attr in address["attrs"]:
            if attr[0] == "IFA_ADDRESS":
                addresses.add(attr[1])
    return addresses


class UndefinedInterface(Exception):
    pass


class UndefinedNamespace(Exception):
    pass


class InterfaceNotFound(Exception):
    pass


def getOVSVersion():
    output = utils.execute("ovs-vsctl --version")
    if output:
        return parse.parse(
            "ovs-vsctl (Open vSwitch) {}.{}.{}", output.split("\n")[0])
    else:
        exit()


def getLinuxVersion():
    return parse.parse("{}.{}.{}", platform.release().split("-")[0])


def checkGeneve():
    # TODO try to load the module instead because of custom kernels or create
    # port
    ovs = getOVSVersion()
    linux = getLinuxVersion()
    if (ovs[0] == 2 and ovs[1] >= 5) or (
            linux[0] == 3 and linux[1] >= 18) or (linux[0] > 3):
        return True
    else:
        return False


def tc_add_qdisc(ipr, nic, kind, handle, *args, **kwargs):
    assert(handle in range(1, 0xFFFF))
    if 'default' in kwargs:
        assert(kwargs['default'] in range(1, 0xFFFF))
    nic_id = ipr.link_lookup(ifname=nic)[0]
    try:
        ipr.tc('add', kind, nic_id, handle << 16, *args, **kwargs)
    except netlink.NetlinkError as e:
        if e.code != 17:
            raise e


def tc_del_qdisc(ipr, nic, kind, handle):
    assert(handle in range(1, 0xFFFF))
    nic_id = ipr.link_lookup(ifname=nic)[0]
    ipr.tc('del', kind, nic_id, handle << 16)


def tc_add_filter(ipr, nic, major, target_minor, vlan_id, priority):
    assert(major in range(1, 0xFFFF))
    assert(target_minor in range(1, 0xFFFF))
    nic_id = ipr.link_lookup(ifname=nic)[0]
    ipr.tc("add-filter", "u32", nic_id, parent=major << 16, prio=1, protocol=protocols.ETH_P_ALL, target=major << 16 |
           target_minor, keys=["0x0/0x0+0"], action=[{'kind': "vlan", 'v_action': 'modify', 'id': vlan_id, 'priority': priority}])


def tc_del_filter(ipr, nic, major, target_minor):
    assert(major in range(1, 0xFFFF))
    assert(target_minor in range(1, 0xFFFF))
    nic_id = ipr.link_lookup(ifname=nic)[0]
    ipr.tc("del-filter", "u32", nic_id, parent=major << 16, prio=1,
           protocol=protocols.ETH_P_ALL, target=major << 16 | target_minor, keys=["0x0/0x0+0"])
