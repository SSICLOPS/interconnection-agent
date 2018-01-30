# Interconnection Agent

This is the interconnection agent implementation using Asyncio, Aiohttp and 
message queues

## Components

### Controller

The controller runs a REST API and uses AMQP to communicate with the agents. 
Only a single instance can run on a specific virtualhost (for Rabbitmq). The 
controller is identified by a UUID.

### Agent

The agent can be run in as many nodes as needed. They are identified by a UUID
and a 12 bits integer that MUST be unique accross the federation.

In case of desynchronization with the controller, the agent dies.

## Installation

see INSTALL.md

## Usage

The controller offers a REST API on the IP and port defined in the configuration
file. It also offers a very simple and basic web GUI (http://<ip>:<port>/gui)

A file containing curl command examples can be found in the examples folder.

The storage backend is a json file that can also be edited and populated before
running the controller.

To run the controller without installation :

```sh
cd src
python3 controller/controller.py -c ../../conf/controller.conf 
```

To run the agent without installation :

```sh
cd src
python3 agent/agent.py -c ../../conf/agent.conf 
```