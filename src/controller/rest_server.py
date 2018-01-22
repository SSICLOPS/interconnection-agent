from aiohttp import web
import json
import utils
import logging
import models
import traceback
from common import amqp_client
import uuid
import data_container
import functools
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
                text="A JSON body is expected with the required parameters : \n{}\
\nand the optional parameters :\n{}\n".format(
                    required_args, opt_args
                )
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
                    text="{} is a required parameter\
\nA JSON body is expected with the required parameters : \n\
{}\n and the optional parameters :\n{}\n".format(k,
                        required_args, opt_args
                    )
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
            return resp
        
    except Exception as e:
        if isinstance(e, web.Response):
            del arguments["amqp"]
            del arguments["data_store"]
            logging.debug("REST API : {} endpoint {} called with parameters {} \
and returned {}".format( req.method, req.path, arguments,
                    e.status
                )
            )
            return e
        else:
            traceback.print_exc()
    del arguments["amqp"]
    del arguments["data_store"]
    logging.error("REST API : {} endpoint {} / {} called with parameters {} \
and didn't complete properly".format( req.method, req.path, callback.__name__,
            arguments
        )
    )
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
