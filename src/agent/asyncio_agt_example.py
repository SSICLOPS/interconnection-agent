import asyncio
import aioamqp
import json


routing_key = 'agent.XXX'

def fib(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fib(n-1) + fib(n-2)



async def on_request(channel, body, envelope, properties):
    n = int(body)

    print(" [.] fib(%s)" % n)
    response = fib(n)

    await channel.basic_publish(
        payload=str(response),
        exchange_name='',
        routing_key=properties.reply_to,
        properties={
            'correlation_id': properties.correlation_id,
        },
    )

    await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
    
async def on_heartbeat(channel, body, envelope, properties):
    print("Heartbeat : {}".format(json.loads(body.decode('utf-8'))))

  
async def rpc_server():
    protocol = None
    while protocol is None:
        try:
            transport,protocol = await aioamqp.connect(host="127.0.0.1",login="interco",
                password="interco", virtualhost="/interco", 
                loop=asyncio.get_event_loop())
        except:
            protocol = None
            await asyncio.sleep(3)
    channel = await protocol.channel()
    
    await channel.exchange('actions', 'topic')
    await channel.exchange('heartbeats', 'topic')

    result = await channel.queue(queue_name='', durable=False, auto_delete=True, 
        exclusive=True)
    queue_name = result['queue']

    heartbeat_result = await channel.queue_declare(queue_name='', durable=False, 
        auto_delete=True, exclusive=True)
    heartbeat_queue = heartbeat_result['queue']
    
    binding_keys = [routing_key,"agent.YYY"]

    for binding_key in binding_keys:
        await channel.queue_bind(
            exchange_name='actions',
            queue_name=queue_name,
            routing_key=binding_key
        )
        
    binding_keys = ["heartbeat.controller"]

    for binding_key in binding_keys:
        await channel.queue_bind(
            exchange_name="heartbeats",
            queue_name=heartbeat_queue,
            routing_key=binding_key
        )

    await channel.basic_consume(on_request, queue_name=queue_name)
    await channel.basic_consume(on_heartbeat, queue_name=heartbeat_queue)
    print(" [x] Awaiting RPC requests")
    
    return channel

async def send_heartbeat(channel):
    while True:
        if not channel:
            try:
                channel = await rpc_server()
            except:
                await asyncio.sleep(3)
        try : 
            await channel.basic_publish(
                payload='"Hello from agent"',
                properties = {"content_type":'application/json'}
                exchange_name="heartbeats",
                routing_key="heartbeat.agent.1"
                )
            await asyncio.sleep(3)
        except:
            channel = None
        
        
    
event_loop = asyncio.get_event_loop()
channel = event_loop.run_until_complete(rpc_server())
asyncio.ensure_future(send_heartbeat(channel))
event_loop.run_forever()

