from helpers_n_wrappers import iptc_helper3


def createChain(table, chain):
    iptc_helper3.add_chain(table, chain, ipv6=False, silent=True)
    iptc_helper3.flush_chain(table, chain, ipv6=False, silent=True)


def addRules(rules):
    for table, chain, rule in rules:
        iptc_helper3.delete_rule(
            table, chain, rule, ipv6=False, silent=True)
        iptc_helper3.insert_rule(table, chain, rule, ipv6=False)


def delRules(rules):
    for table, chain, rule in rules:
        iptc_helper3.delete_rule(
            table, chain, rule, ipv6=False, silent=True)


def defRulesVPNChain(ifName):
    rules = []
    for chain, dir in [("INPUT", "in"), ("OUTPUT", "out")]:
        for k in ["500", "4500"]:
            rules.append(("filter", chain, {dir + '-interface': ifName,
                                            'protocol': 'udp',
                                            'target': 'INTERCO',
                                            'udp': {'dport': k, 'sport': k}}))
        for k in ["gre", "esp"]:
            rules.append(("filter", chain, {dir + '-interface': ifName,
                                            'protocol': k,
                                            'target': 'INTERCO'}))
    return rules


def defVPNConnections(src, dst):
    rules = [("filter", "INTERCO", {'dst': dst,
                                    'src': src,
                                    'target': 'ACCEPT'}),
             ("filter", "INTERCO", {'dst': src,
                                    'src': dst,
                                    'target': 'ACCEPT'})]
    return rules


def defInputOutputDrop():
    return [("filter", "INPUT", {'target': 'DROP'}),
            ("filter", "OUTPUT", {'target': 'DROP'})]


def defTCPClamping(interfaces):
    rules = []
    for interface, mtu in interfaces:
        rules.append(("filter", "FORWARD", {'physdev': {'physdev-in': interface,
                                                        'physdev-is-bridged': ''},
                                            'protocol': 'tcp',
                                            'tcp': {'tcp-flags': ['SYN,RST', 'SYN']},
                                            'target': {'TCPMSS': {'set-mss': str(int(mtu) - 40)}}}))
    return rules


def defNoTrack():
    return [('raw', 'PREROUTING', {'target': {'CT': {'notrack': ''}}})]
