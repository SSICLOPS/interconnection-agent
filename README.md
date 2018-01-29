# Interconnection Agent

This is the interconnection agent implementation using Asyncio, Aiohttp and 
message queues

## Controller

The controller runs a REST API and uses AMQP to communicate with the agents. 
Only a single instance can run on a specific virtualhost (for Rabbitmq). The 
controller is identified by a UUID.

## Agent

The agent can be run in as many nodes as needed. They are identified by a UUID
and a 12 bits integer that MUST be unique accross the federation.

In case of desynchronization with the controller, the agent dies.