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

from parse import search

import utils

# Bridge only functions


def add_bridge(name, silent=False):
    utils.execute("ovs-vsctl add-br {}".format(name), silent)


def has_bridge(name):
    return utils.execute("ovs-vsctl find bridge name={}".format(name))


def delete_bridge(name, silent=False):
    utils.execute("ovs-vsctl del-br {}".format(name), silent)


def configure_bridge(bridge_name, ip, port, protocol="OpenFlow13"):
    utils.execute(
        "ovs-vsctl set-controller {} tcp:{}:{}".format(bridge_name, ip, port)
        )
    utils.execute(
        "ovs-vsctl set controller {} connection-mode=out-of-band".format(
            bridge_name
            )
        )
    utils.execute(
        "ovs-vsctl set bridge {} other-config:disable-in-band=true".format(
            bridge_name
            )
        )
    utils.execute(
        "ovs-vsctl set bridge {} protocols={}".format(bridge_name, protocol)
        )
    utils.execute("ovs-vsctl set-fail-mode {} secure".format(bridge_name))

# Port only functions


def add_port(bridge_name, port_name, port_number=None,
             vlan=None, mode="access", silent=False):
    """
    Specify port_number so it could potentially fail
    # May return error code if the port does not exist yet
    """
    utils.execute(
        "ovs-vsctl add-port {} {}".format(bridge_name, port_name), silent
        )
    if vlan is None:
        return
    if mode == "access":
        utils.execute(
            "ovs-vsctl set port {} tag={}".format(port_name, vlan), silent
            )
    elif mode == "trunk":
        utils.execute(
            "ovs-vsctl set port {} trunks={}".format(port_name, vlan), silent
            )


def has_port(bridge_name, port_name=None, port_number=None):
    pass


def delete_port(port_name, silent=False):
    utils.execute("ovs-vsctl del-port {}".format(port_name), silent)


def modify_port(port_name=None, silent=False, **kwargs):
    """{'type':'internal', '}"""
    for key in kwargs:
        utils.execute(
            "ovs-vsctl set interface {} {}={}".format(port_name, key, kwargs[key]), 
            silent
            )


def find_port_id(name):
    output = utils.execute(
        "ovs-vsctl --columns=ofport find interface name={}".format(name)
        )
    try:
        return int(output.split(":")[1])
    except IndexError:
        return None


def get_dpid(bridge_name, protocol):
    dpid_str = utils.execute(
        "ovs-ofctl -O {} show {}".format(protocol, bridge_name)
        )
    return hex(search("dpid:{dpid:x}", dpid_str).named['dpid'])
