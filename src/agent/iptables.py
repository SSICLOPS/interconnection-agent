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

from helpers_n_wrappers import iptc_helper3


def createChain(table, chain):
    iptc_helper3.add_chain(table, chain, ipv6=False, silent=True)
    iptc_helper3.flush_chain(table, chain, ipv6=False, silent=True)


def addRules(rules):
    for table, chain, rule in rules:
        iptc_helper3.delete_rule(
            table, chain, rule, ipv6=False, silent=True
            )
        iptc_helper3.insert_rule(table, chain, rule, ipv6=False)


def delRules(rules):
    for table, chain, rule in rules:
        iptc_helper3.delete_rule(
            table, chain, rule, ipv6=False, silent=True)


def defRulesVPNChain(ifName):
    rules = []
    for chain, dir in [("INPUT", "in"), ("OUTPUT", "out")]:
        for k in ["500", "4500"]:
            rules.append(
                ("filter", chain, 
                    {dir + '-interface': ifName,
                        'protocol': 'udp',
                        'target': 'INTERCO',
                        'udp': {'dport': k, 'sport': k}
                        }
                    )
                )
        for k in ["gre", "esp"]:
            rules.append(
                ("filter", chain, 
                    {dir + '-interface': ifName,
                        'protocol': k,
                        'target': 'INTERCO'
                        }
                    )
                )
    return rules


def defVPNConnections(src, dst):
    rules = [
        ("filter", "INTERCO", 
            {'dst': dst,
                'src': src,
                'target': 'ACCEPT'
                }
            ),
        ("filter", "INTERCO", 
            {'dst': src,
                'src': dst,
                'target': 'ACCEPT'
                }
            )
        ]
    return rules


def defInputOutputDrop():
    return [("filter", "INPUT", {'target': 'DROP'}),
        ("filter", "OUTPUT", {'target': 'DROP'})
        ]


def defTCPClamping(interfaces):
    rules = []
    for interface, mtu in interfaces:
        rules.append(
            ("filter", "FORWARD", 
                {'physdev': {'physdev-in': interface,
                        'physdev-is-bridged': ''
                        },
                    'protocol': 'tcp',
                    'tcp': {'tcp-flags': ['SYN,RST', 'SYN']},
                    'target': {'TCPMSS': {'set-mss': str(int(mtu) - 40)}}
                    }
                )
            )
    return rules
    
def def_masquerade(interfaces):
    rules = []
    for interface in interfaces:
        rules.append(
            ("nat", "POSTROUTING", {"out-interface":interface,
                'target':"MASQUERADE"
                }))
    return rules
    
def def_DNAT(interface, orig_port, ip, dst_port):
    rules = []
    rules.append(
        ("nat", "PREROUTING", {"in-interface":interface,
            "protocol": "tcp",
            "tcp": {"dport":"{}".format(orig_port)},
            'target':{"DNAT":{"to-destination":"{}:{}".format(ip, dst_port)}},
            }))
    return rules
    
def def_REDIRECT(interface, dst_port):
    rules = []
    rules.append(
        ("nat", "PREROUTING", {"in-interface":interface,
            "protocol": "tcp",
            'target':{"REDIRECT":{"to-ports":"{}".format(dst_port)}},
            }))
    return rules

def defNoTrack():
    return [('raw', 'PREROUTING', {'target': {'CT': {'notrack': ''}}})]
