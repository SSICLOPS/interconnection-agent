import uuid
import asyncio
import aioamqp

from aiohttp import web
import json

async def handle(request):
    #https://docs.aiohttp.org/en/stable/web_reference.html
    # for example path and method
    var = request.match_info.get('var')
    response_obj = { 'status' : 'success', 'var': var }
    data = await request.json()
    print(data)
    response_obj['var'] = await request.app['fibo_client'].call(int(var))
    return web.Response(status=200, content_type="application/json", 
        text=json.dumps(response_obj))

async def build_server(loop, address, port, fibo_client):
    app = web.Application(loop=loop)
    app['fibo_client'] = fibo_client
    app.router.add_post('/{var}', handle)
    return await loop.create_server(app.make_handler(), address, port)


class FibonacciRpcClient(object):
    def __init__(self):
        self.transport = None
        self.protocol = None
        self.channel = None
        self.callback_queue = None
        self.heartbeat_queue = None
        self.waiter = asyncio.Event()

        
    async def connect(self):
        """ an `__init__` method can't be a coroutine"""
        self.transport, self.protocol = await aioamqp.connect(host="127.0.0.1",
            login="interco", password="interco", virtualhost="/interco", 
            loop=asyncio.get_event_loop())
        self.channel = await self.protocol.channel()

        

        await self.channel.exchange('actions', 'topic')
        await self.channel.exchange('heartbeats', 'topic')
        
        
        actions_result = await self.channel.queue_declare(queue_name='', 
            durable=False, auto_delete=True, exclusive=True)
        self.callback_queue = actions_result['queue']
        
        heartbeat_result = await self.channel.queue_declare(queue_name='', 
            durable=False, auto_delete=True, exclusive=True)
        heartbeat_queue = heartbeat_result['queue']

        await self.channel.basic_consume(
            self.on_response,
            no_ack=True,
            queue_name=self.callback_queue,
        )
        
        
        binding_keys = ["heartbeat.agent.#"]

        for binding_key in binding_keys:
            await self.channel.queue_bind(
                exchange_name="heartbeats",
                queue_name=heartbeat_queue,
                routing_key=binding_key
            )
        
        await self.channel.basic_consume(
            self.on_heartbeat,
            no_ack=True,
            queue_name=heartbeat_queue,
        )

    
    async def send_heartbeat(self):
        while True:
            if not self.protocol:
                await self.connect()
            await self.channel.basic_publish(
            payload="Hello from controller",
            exchange_name="heartbeats",
            routing_key="heartbeat.controller"
            )
            await asyncio.sleep(3)
    
    async def on_response(self, channel, body, envelope, properties):
        if self.corr_id == properties.correlation_id:
            self.response = body

        self.waiter.set()
        
    async def on_heartbeat(self, channel, body, envelope, properties):
        print("Heartbeat : {}".format(body))

    
    async def call(self, n):
        if not self.protocol:
            await self.connect()
        self.response = None
        self.corr_id = str(uuid.uuid4())
        await self.channel.basic_publish(
            payload=str(n),
            exchange_name='actions',
            routing_key='agent.XXX',
            properties={
                'reply_to': self.callback_queue,
                'correlation_id': self.corr_id,
            },
        )
        print("request sent, waiting for an answer")
        await self.waiter.wait()
        self.waiter.clear()

        #await self.protocol.close()
        return int(self.response)



async def rpc_client(fibonacci_rpc):
    print(" [x] Requesting fib(30)")
    response = await fibonacci_rpc.call(3)
    print(" [.] Got %r" % response)
    
async def connect_Fibo(fibonacci_rpc):
    await fibonacci_rpc.connect()
 
fibonacci_rpc = FibonacciRpcClient() 
asyncio.get_event_loop().run_until_complete(connect_Fibo(fibonacci_rpc))
asyncio.get_event_loop().run_until_complete(build_server(
    asyncio.get_event_loop(), '0.0.0.0', 80, fibonacci_rpc))
asyncio.ensure_future(fibonacci_rpc.send_heartbeat())
asyncio.ensure_future(rpc_client(fibonacci_rpc))

try:
    asyncio.get_event_loop().run_forever()
except KeyboardInterrupt:
    asyncio.get_event_loop().close()
