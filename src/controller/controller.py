import sys, getopt, os
import models
import configparser
from common import amqp_client
import amqp_controller
import rest_server
import asyncio
import logging.config
import logging
import storage_backend_json
import data_container
import utils


def get_filename(config, section, file):
        filename = config.get(section, file)
        filename_tmp = filename
        
        #Absolute path, use as is
        if filename.startswith("/"):
            if not os.path.isfile(filename):
                raise models.Input_error(filename + " does not exist")
            return filename
        
        #Relative path: 
        # if a work directory is given, use this, otherwise use the 
        #current directory
        env_dir_path = os.getenv("DIR_CTL_PATH")
        
        if env_dir_path:
            filename_tmp = os.getenv("DIR_CTL_PATH")
            
            #If the variable does not end with /, add one
            if filename_tmp[-1:] == "/":
                filename_tmp += "/"
            
            filename_tmp += filename
        
        else:
            filename_tmp = filename
        
        #Check if it exists
        if not os.path.isfile(filename_tmp):
            raise models.Input_error(filename + " does not exist")
        
        return filename_tmp

def init_controller(argv):
    cli_error_str = "controller.py -c <configuration file>"
    configuration_file = None
    asyncio_loop = asyncio.get_event_loop()
    
    #parse the command line arguments
    # h - help : help
    # c - conf : configuration file
    try:
        cli_opts, _ = getopt.getopt(argv, "hc:",["help","conf="])
    
    except getopt.GetoptError:
        print(cli_error_str)
        sys.exit()
    
    for cli_opt, cli_arg in cli_opts:
        
        if cli_opt in ("-c", "--conf"):
            configuration_file = cli_arg
        
        else:
            print(cli_error_str)
            sys.exit()
    
    #Exit if the configuration file is not set
    if not configuration_file:
        print(cli_error_str)
        sys.exit()
    
    #Parse the configuration file
    config = configparser.ConfigParser()
    config.read(configuration_file)

    log_config_file = get_filename(config, "DEFAULT", "log_config_file")
    logging.config.fileConfig(log_config_file)
    
    
    #Get the VPN configuration
    vpn_backend = config.get('DEFAULT', 'vpn_backend')
    
    if vpn_backend not in ["strongswan"]:
        raise models.Input_error("The given vpn backend is not supported.")

    template_filename = get_filename(config, vpn_backend, "template_file")
    template_secrets_filename = get_filename(
        config, vpn_backend, "template_secrets_file")

    cloud_id = config.get('DEFAULT', "cloud_id")

    
    #Get the OpenStack configuration
    openstack_auth = {}
    openstack_auth['auth_url'] = config.get('openstack', 'auth_url')
    openstack_auth['project_name'] = config.get(
        'openstack', 'project_name')
    openstack_auth['username'] = config.get('openstack', 'username')
    openstack_auth['password'] = config.get('openstack', 'password')

    
    #Get the storage configuration
    storage_backend = config.get('DEFAULT', 'storage_backend')
    
    if storage_backend not in ["json"]:
        raise models.Input_error("The given storage backend is not supported.")
    
    if storage_backend == "json":
        json_filename = get_filename(config, 'json_backend', 'filename')
        storage_backend_obj = storage_backend_json.Storage_backend_json(
            json_filename)
        data_store = data_container.Data_container(storage_backend_obj, 
            "overwrite"
        )
    utils.data_store_validator.add_data_store(data_store) 
    data_store.restore()
    
    amqp_auth = {}
    amqp_auth["host"] = config.get('amqp', 'host')
    amqp_auth["login"] = config.get('amqp', 'login')
    amqp_auth["password"] = config.get('amqp', 'password')
    amqp_auth["virtualhost"] = config.get('amqp', 'virtualhost')
    amqp_auth["port"] = config.get('amqp', 'port')
    amqp_auth["loop"] = asyncio_loop
    amqp_auth["bind_action_queue"] = False
    amqp_auth["heartbeat_receive_key"] = "{}#".format(
        amqp_client.AMQP_KEY_HEARTBEATS_AGENTS
    )
    
    rest_address = config.get('rest_api', 'address')
    rest_port = config.get('rest_api', 'port')
    
    amqp_client_obj = amqp_controller.Amqp_controller(data_store = data_store, 
        node_uuid=cloud_id,**amqp_auth
    )
    asyncio_loop.run_until_complete(amqp_client_obj.connect())
    asyncio_loop.run_until_complete(rest_server.build_server(asyncio_loop, 
        rest_address, rest_port, data_store, amqp_client_obj
    ))
    asyncio.ensure_future(amqp_client_obj.send_heartbeat(
        amqp_client.AMQP_KEY_HEARTBEATS_CTRL
    ))

    logging.info("Controller started")
    
    try:
        asyncio_loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Stopping")
        asyncio.get_event_loop().close()

if __name__ == "__main__":
   init_controller(sys.argv[1:])
