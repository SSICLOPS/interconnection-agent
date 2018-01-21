from common import amqp_client
import json
import traceback

class Amqp_controller(amqp_client.Amqp_client):

    def __init__(self, cloud_id, **kwargs):
        super().__init__(cloud_id, **kwargs)
        self.actions_list = {}
        self.callbacks_list = {}
        self.action_callback = self.on_message
        
    async def publish_action(self, callback, **kwargs):
        self.actions_list[kwargs["payload"]["uuid"]] = kwargs["payload"]
        if callback:
            self.callbacks_list[kwargs["payload"]["uuid"]] = callback
        else:
            self.callbacks_list[kwargs["payload"]["uuid"]] = None
        kwargs["payload"] = json.dumps(kwargs["payload"])
        kwargs["properties"]["reply_to"] = self.process_queue
        await self.publish_msg(**kwargs)
        
    async def on_message(self, channel, body, envelope, properties):
        payload = json.loads(body.decode("utf-8"))
        if "uuid" in payload :
            if payload["uuid"] in self.actions_list:
                callback = self.callbacks_list[payload["uuid"]]
                if callback is not None:
                    await callback(payload, 
                        self.actions_list[payload["uuid"]]
                    )
                del self.callbacks_list[payload["uuid"]]
                del self.actions_list[payload["uuid"]]