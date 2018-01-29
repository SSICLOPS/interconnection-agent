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

from pyroute2 import IPRoute, netns, netlink, NetNS, protocols
from socket import AF_INET

IN_PORT_ROOT = "vethin{}"
OUT_PORT_ROOT = "vethout{}"


def createIpr():
    return IPRoute()


def createLink(ipr, name, type, peerName=None):
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
    try:
        ipr.link('add', ifname=name, kind="vlan",
                 link=getLink(ipr, link), vlan_id=vlan_id)
    except netlink.NetlinkError as e:
        if e.code != 17:
            raise e
    return getLink(ipr, name)


def getLink(ipr, name):
    idx = ipr.link_lookup(ifname=name)
    if not idx:
        raise InterfaceNotFound("Interface " + name + " not found")
    return idx[0]


def setMtu(ipr, name, mtu, idx=None, netns=None):
    if not idx:
        idx = getLink(ipr, name)
    if idx:
        ipr.link("set", index=idx, mtu=mtu)
    return idx


def setUp(ipr, name=None, idx=None, netns=None):
    if idx is None and name is not None:
        idx = getLink(ipr, name)
    ipr.link('set', index=idx, state="up")
    return idx


def setDown(ipr, name=None, idx=None, netns=None):
    if idx is None and name is not None:
        idx = getLink(ipr, name)
    ipr.link('set', index=idx, state="down")
    return idx


def createNetNS(name):
    try:

        return netns.create(name)
    except OSError as e:
        if e.errno != 17:
            raise e


def delNetNS(name):
    netns.remove(name)


def getNetNS(name):
    return NetNS(name)


"""
Set the interface to a namespace, try to find it first in the root namespace, 
then in the given namespace. If failed, return None
"""


def setNetNS(ipr, namespace, interfaceName=None, interfaceIdx=None):
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

class InterfaceNotFound(Exception):
    pass
