import re
from utils import execute_list
import os
from jinja2 import Environment, FileSystemLoader


STATUS_RE = '([a-z0-9\-]+)\{[0-9]+\}: (ROUTED|CONNECTING|INSTALLED)'
STATUS_NOT_RUNNING_RE = 'Command:.*ipsec.*status.*Exit code: [1|3] '
STATUS_IPSEC_SA_ESTABLISHED_RE = (
    '\d{3} #\d+: "([a-f0-9\-]+).*IPsec SA established.*')
STATUS_IPSEC_SA_ESTABLISHED_RE2 = (
    '\d{3} #\d+: "([a-f0-9\-\/x]+).*IPsec SA established.*')


# Service operation status constants
ACTIVE = "ACTIVE"
DOWN = "DOWN"
CREATED = "CREATED"
PENDING_CREATE = "PENDING_CREATE"
PENDING_UPDATE = "PENDING_UPDATE"
PENDING_DELETE = "PENDING_DELETE"
INACTIVE = "INACTIVE"
ERROR = "ERROR"

_STATUS_MAP = {
    'ROUTED': DOWN,
    'CONNECTING': DOWN,
    'INSTALLED': ACTIVE
}


class Strongswan_driver(object):
    binary = "ipsec"

    def __init__(self, conf_filename = "/etc/ipsec.conf", 
            secrets_filename = "/etc/ipsec.secrets",
            conf_template = "./templates/ipsec.conf.strongswan.template",
            secrets_template = "./templates/ipsec.secrets.template",
            binary = "/usr/sbin/ipsec"):
        self.binary = binary
        self.conf_filename = conf_filename
        self.secrets_filename = secrets_filename
        self.template_conf_folder, self.template_conf = os.path.split(
            conf_template)
        self.template_secrets_folder, self.template_secrets = os.path.split(
            secrets_template)
        # Check if the given files are the default configuration file, if not,
        # include them (ipsec.conf and ipsec.secrets)
        if self.conf_filename != "/etc/ipsec.conf":
            conf_file = open("/etc/ipsec.conf", "r+")
            include = False
            for line in conf_file.readlines():
                if line.startswith("include " + self.conf_filename):
                    include = True
            if include == False:
                conf_file.write("include " + self.conf_filename + "\n\n")
            conf_file.close()
        if self.secrets_filename != "/etc/ipsec.secrets":
            conf_secrets_file = open("/etc/ipsec.secrets", "r+")
            include = False
            for line in conf_secrets_file.readlines():
                if line.startswith("include " + self.secrets_filename):
                    include = True
            if include == False:
                conf_secrets_file.write(
                    "include " + self.secrets_filename + "\n\n")
            conf_secrets_file.close()

        self.STATUS_PATTERN = re.compile(STATUS_RE)
        self.STATUS_NOT_RUNNING_PATTERN = re.compile(
            STATUS_NOT_RUNNING_RE)
        self.STATUS_IPSEC_SA_ESTABLISHED_PATTERN = re.compile(
            STATUS_IPSEC_SA_ESTABLISHED_RE)
        self.STATUS_IPSEC_SA_ESTABLISHED_PATTERN2 = re.compile(
            STATUS_IPSEC_SA_ESTABLISHED_RE2)

        

        self.connection_status = {}

    def overwrite_conf(self, configs):
        configs_list = configs.values()
        env = Environment(
            autoescape=False,
            loader=FileSystemLoader(self.template_conf_folder),
            trim_blocks=False)
        conf =  env.get_template(self.template_conf).render(
            {"vpn_connections": configs_list})

    
        env = Environment(
            autoescape=False,
            loader=FileSystemLoader(self.template_secrets_folder),
            trim_blocks=False)
        secrets = env.get_template(self.template_secrets).render(
            {"vpn_connections": configs_list})
            
        with open(self.conf_filename, 'w') as f:
            f.write(conf)
        with open(self.secrets_filename, 'w') as f:
            f.write(secrets)

    """
    Extract and stores the status of the connections
    """

    def _extract_and_record_connection_status(self, status_output):
        if not status_output:
            self.connection_status = {}
            return
        for line in status_output.split('\n'):
            try:
                conn_id, conn_status = self._check_status_line(line)
            except StopIteration:
                break
            if not conn_id:
                continue
            self.connection_status[conn_id] = conn_status

        

    def status(self):
        """Check if the process is active or not."""
        try:
            status = self._execute([self.binary, 'status'])
            self._extract_and_record_connection_status(status)
            if not self.connection_status:
                return False
        except RuntimeError:
            return False
        return True

    def _execute(self, cmd, extra_ok_codes=None):
        return execute_list(cmd)


        

    def _check_status_line(self, line):
        """Parse a line and search for status information.
        If a given line contains status information for a connection,
        extract the status and mark the connection as ACTIVE or DOWN
        according to the STATUS_MAP.
        """
        m = self.STATUS_PATTERN.search(line)
        if not m:
            return None, None
        connection_id = m.group(1)
        status = _STATUS_MAP[m.group(2)]
        return connection_id, status


    def restart(self, vpn_connections=[]):
        self._execute([self.binary, 'restart'])
        
    def start_connection(self, vpn_connection_id):
        self._execute([self.binary, 'stroke', 'up-nb', vpn_connection_id])

    def reload(self):
        self._execute([self.binary, 'rereadsecrets'])
        self._execute([self.binary, 'reload'])

