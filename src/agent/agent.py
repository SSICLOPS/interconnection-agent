import sys, getopt, os
import configparser
from common import amqp_client
import asyncio
import logging.config
import logging
import queue_manager
import heartbeat_manager

class Input_error(Exception):
    pass

def get_filename(config, section, file):
        filename = config.get(section, file)
        filename_tmp = filename
        
        #Absolute path, use as is
        if filename.startswith("/"):
            if not os.path.isfile(filename):
                raise Input_error(filename + " does not exist")
            return filename
        
        #Relative path: 
        # if a work directory is given, use this, otherwise use the 
        #current directory
        env_dir_path = os.getenv("DIR_AGT_PATH")
        
        if env_dir_path:
            filename_tmp = os.getenv("DIR_AGT_PATH")
            
            #If the variable does not end with /, add one
            if filename_tmp[-1:] == "/":
                filename_tmp += "/"
            
            filename_tmp += filename
        
        else:
            filename_tmp = filename
        
        #Check if it exists
        if not os.path.isfile(filename_tmp):
            raise Input_error(filename + " does not exist")
        
        return filename_tmp

def init_controller(argv):
    cli_error_str = "agent.py -c <configuration file>"
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
        raise Input_error("The given vpn backend is not supported.")

    template_filename = get_filename(config, vpn_backend, "template_file")
    template_secrets_filename = get_filename(
        config, vpn_backend, "template_secrets_file")

    self_id = config.get('DEFAULT', "agent_id")
    
    amqp_auth = {}
    amqp_auth["host"] = config.get('amqp', 'host')
    amqp_auth["login"] = config.get('amqp', 'login')
    amqp_auth["password"] = config.get('amqp', 'password')
    amqp_auth["virtualhost"] = config.get('amqp', 'virtualhost')
    amqp_auth["port"] = config.get('amqp', 'port')
    amqp_auth["loop"] = asyncio_loop
    amqp_auth["bind_action_queue"] = True
    amqp_auth["heartbeat_receive_key"] = amqp_client.AMQP_KEY_HEARTBEATS_CTRL
    
    queue_manager_obj = queue_manager.Queue_manager()
    heartbeat_manager_obj = heartbeat_manager.Heartbeat_manager()
    amqp_auth["action_callback"] = queue_manager_obj.add_msg_to_queue
    amqp_auth["heartbeat_callback"] = heartbeat_manager_obj.heartbeat_callback
    
    amqp_client_obj = amqp_client.Amqp_client(self_id,**amqp_auth)
    queue_manager_obj.set_amqp(amqp_client_obj)
    asyncio_loop.run_until_complete(amqp_client_obj.connect())
    asyncio.ensure_future(amqp_client_obj.send_heartbeat("{}{}".format(
        amqp_client.AMQP_KEY_HEARTBEATS_AGENTS, self_id)))
    asyncio.ensure_future(queue_manager_obj.process_queue())

    logging.info("Agent started")
    
    try:
        asyncio_loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Stopping")
        asyncio.get_event_loop().close()

if __name__ == "__main__":
   init_controller(sys.argv[1:])
