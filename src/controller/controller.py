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

import sys, getopt, os
import configparser
import asyncio
import logging.config
import logging
import traceback

import amqp_controller
import rest_server
import storage_backend_json
import data_container
import utils
from common import amqp_client
from common import file



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

    log_config_file = file.get_filename(config, "DEFAULT", "log_config_file")
    logging.config.fileConfig(log_config_file)
    

    cloud_id = config.get('DEFAULT', "cloud_id")

    
    #Get the OpenStack configuration
    openstack_auth = {}
    openstack_auth['auth_url'] = config.get('openstack', 'auth_url')
    openstack_auth['project_name'] = config.get(
        'openstack', 'project_name'
        )
    openstack_auth['username'] = config.get('openstack', 'username')
    openstack_auth['password'] = config.get('openstack', 'password')

    
    #Get the storage configuration
    storage_backend = config.get('DEFAULT', 'storage_backend')
    
    if storage_backend not in ["json"]:
        raise models.Input_error("The given storage backend is not supported.")
    
    if storage_backend == "json":
        json_filename = file.get_filename(config, 'json_backend', 'filename')
        storage_backend_obj = storage_backend_json.Storage_backend_json(
            json_filename
            )
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
    server = asyncio_loop.run_until_complete(rest_server.build_server(asyncio_loop, 
        rest_address, rest_port, data_store, amqp_client_obj
        ))
    heartbeat_future = asyncio.ensure_future(amqp_client_obj.send_heartbeat(
        amqp_client.AMQP_KEY_HEARTBEATS_CTRL
        ))

    logging.info("Controller started")
    
    try:
        asyncio_loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Stopping")
        
    heartbeat_future.cancel()
    amqp_client_obj.shutdown()
    server.close()
    asyncio_loop.run_until_complete(server.wait_closed())
    try:
        asyncio.get_event_loop().close()
    except:
        traceback.print_exc

if __name__ == "__main__":
   init_controller(sys.argv[1:])
