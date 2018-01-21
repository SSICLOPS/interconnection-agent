from aiohttp import web
import json
import utils
import logging
import models
import traceback
from common import amqp_client
import uuid



async def process(req, callback, url_args = [], required_args = [], 
    opt_args = []):

    arguments = {"data_store": req.app["data"], "amqp":req.app["amqp"]}
    # Get the arguments from the body
    body_data = await req.text()
    # If no body but required arguments, return 400
    if not body_data and required_args:
        return send_response(status=400,  
            text="A JSON body is expected with the required parameters : \n{}\
            \nand the optional parameters :\n{}\n".format(
                required_args, opt_args
            )
        )
    #Try to load the body from json
    if body_data:
        req_body = json.load(body_data)
    else:
        req_body = {}
    
    # Required arguments. If missing, return 400
    for k in required_args:
        if k not in req_body:
            return send_response(status=400, text="{} is a required parameter\
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
    
    # URL arguments
    for k in url_args:
        try:
            arguments[k] = request.match_info.get(k)
        except:
            return send_response(
                status=400, 
                text="A required parameter present in the URL is missing now,\
                \nUnexpected error!"
            )
    
    # Callback and handle exceptions
    try:
        resp = await callback(**arguments)
        del arguments["amqp"]
        del arguments["data_store"]
        logging.debug(
            "REST API : Function {} called with parameters {}".format(
                callback.__name__, arguments
            )
        )
    except Exception as e:
        return send_response(**handle_exception(e, False))

    return send_response(status=200,content_type='application/json', text=resp)

def send_response(**kwargs):
    log = "REST API: status {}".format(kwargs["status"])
    return web.Response(**kwargs)

async def test_callback(**kwargs):
    payload_uuid = str(uuid.uuid4())
    payload = {"uuid":payload_uuid, "operation":"No-op"}
    await kwargs["amqp"].publish_action(payload=payload, callback = ack_callback,
        properties = {"content_type":'application/json'},
        exchange_name = amqp_client.AMQP_EXCHANGE_ACTIONS,
        routing_key="abc"
        #routing_key="{}#".format(amqp_client.AMQP_KEY_ACTIONS)
    )
    
async def handle(request):
    await process(request, test_callback)
    
async def ack_callback(payload, action):
    logging.info("Received ACK for action {}".format(payload["uuid"]))
    
def handle_exception(e, silent=False):
    try:
        errors_dict = {
            models.NotFound_error: 404, 
            models.Input_error: 400, 
            models.Internal_error: 500,
            models.Conflict_error: 409, 
            models.IsInUse_error: 403, 
            models.Forbidden_error: 403
        }
        status = 500
        if type(e) in errors_dict:
            status = errors_dict[type(e)]
            
        error_msg = '[{}] {}'.format(status, e.message)
        
        if not silent:
            logging.error(error_msg)
        if status == 500:
            logging.error(traceback.format_exc())
        if status == 500:
            error_msg = "Internal Error"
    except:
        status = 500
        error_msg = "Internal Error"
        
    finally:
        return {"status":status, "text":error_msg}



async def build_server(loop, address, port, data_store, amqp_client):
    app = web.Application(loop=loop)
    app['data'] = data_store
    app['amqp'] = amqp_client
    
    app.router.add_get('/', handle)
    
    return await loop.create_server(app.make_handler(), address, port)
