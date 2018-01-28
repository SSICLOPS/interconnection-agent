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

from aiohttp import web
import json
import logging
import traceback
import uuid
import functools

from common import amqp_client
import data_container
import api_interface


async def process(req, callback, url_args = [], required_args = [], 
    opt_args = []):
    
    try:
        arguments = {"data_store": req.app["data"], "amqp":req.app["amqp"]}
        # Get the arguments from the body
        body_data = await req.text()
        
        # If no body but required arguments, return 400
        if not body_data and required_args:
            raise web.HTTPBadRequest( content_type="plain/text",
                text= " ".join(["A JSON body is expected with the required",
                    "parameters : \n{}\nand the".format(required_args),
                    "optional parameters :\n{}\n".format(opt_args)
                    ])
                )
            
        #Try to load the body from json
        if body_data:
            req_body = json.loads(body_data)
        else:
            req_body = {}
            
        # Required arguments. If missing, return 400
        for k in required_args:
            if k not in req_body:
                raise web.HTTPBadRequest( content_type="plain/text",
                    text=" ".join(["{} is a required parameter".format(k),
                        "\nA JSON body is expected with the required parameters",
                        ": \n{}\n and the optional".format(required_args),
                        "parameters :\n{}\n".format(opt_args)
                        ])
                    )
            arguments[k] = req_body[k]
            
        # Optional arguments (None keeps the arguments in correct position)
        for k in opt_args:
            if k not in req_body:
                continue
            arguments[k] = req_body[k]
            
        # URL arguments, the arguments are defined in the route. if the 
        # argument is not present, this means that there is an argument in
        # url_args that is not in the route, otherwise the routing wouldn't 
        # take us here and would probably return a 404. So internal error.
        for k in url_args:
            try:
                arguments[k] = req.match_info.get(k)
            except:
                raise HTTPInternalServerError(text="Unknown error")
    
        # Callback
        resp = await callback(**arguments)
        
        if isinstance(resp, web.Response):
            raise resp
        
    except Exception as e:
        if isinstance(e, web.Response):
            del arguments["amqp"]
            del arguments["data_store"]
            logging.debug(" ".join(["REST API : {}".format(req.method),
                "endpoint {} called with parameters".format(req.path),
                "{} and returned {}".format( arguments, e.status)
                ]))
            return e

    del arguments["amqp"]
    del arguments["data_store"]
    logging.error(" ".join(["REST API : {}".format(req.method),
        "endpoint {} called with parameters".format(req.path),
        "{} and didn't complete properly".format( arguments)
        ]))

    return web.HTTPInternalServerError(text="Unknown error")
        

def set_rest_routes(router):
    for route_dict in api_interface.api_mappings:
        if route_dict["method"] == "GET":
            router_func = router.add_get
        elif route_dict["method"] == "POST":
            router_func = router.add_post
        elif route_dict["method"] == "PUT":
            router_func = router.add_put
        elif route_dict["method"] == "DELETE":
            router_func = router.add_delete
        else:
            continue
        router_func(route_dict["endpoint"], functools.partial(process, 
                callback = route_dict["callback"], 
                url_args = route_dict["url_args"], 
                required_args = route_dict["required_args"], 
                opt_args = route_dict["opt_args"]
                )
            )




async def build_server(loop, address, port, data_store, amqp_client):
    app = web.Application(loop=loop)
    app['data'] = data_store
    app['amqp'] = amqp_client
    
    set_rest_routes(app.router)
    
    return await loop.create_server(app.make_handler(), address, port)
