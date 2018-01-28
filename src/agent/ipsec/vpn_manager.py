import iptables
import logging


class Vpn_manager(object):

    def __init__(self, vpnDriver, iface):
        self.driver = vpnDriver
        iptables.createChain("filter", "INTERCO")
        for i in iface:
            iptables.addRules(iptables.defRulesVPNChain(i))
        self.driver.restart()
        self.configs = {}

    def getVPNStatus(self):
        self.driver.status()
        return self.driver.connection_status

    def _load_vpn_conf(self):
        self.driver.overwrite_conf(self.configs)
        self.driver.reload()
        for node_id in self.configs:
            config = self.configs[node_id]
            if "peer_public_ip" in config:
                iptables.addRules(iptables.defVPNConnections(
                    config["self_ip"], config["peer_public_ip"]
                ))
            else:
                iptables.addRules(iptables.defVPNConnections(
                    config["self_ip"], config["peer_ip"]
                ))
            self.driver.start_connection(node_id)
        logging.debug("VPN configuration applied")
       
       
    def add_conf(self, config):
        self.configs[config["node_id"]] = config
        self._load_vpn_conf()
        
    def del_conf(self, config_id):
        if config_id not in self.configs:
            return
        del self.configs[config_id]
        self._load_vpn_conf()
        
