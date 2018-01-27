#!/bin/sh

curl -H "Content-Type: application/json" -X POST -d '{"node_id":"59a0c617-0049-40c8-bec3-720e39a3f1a4", "name":"ike1", "ike_version":"ikev2", "encryption_algorithm":"aes256", "auth_algorithm":"sha1", "pfs":"modp1536", "lifetime_value":"3600"}' http://localhost:8880/ike

curl -H "Content-Type: application/json" -X POST -d '{"node_id":"ac03be5e-ca29-4f58-98b3-f0b2a7e0d75a", "name":"ipsec1", "transform_protocol":"esp", "encapsulation_mode":"transport", "encryption_algorithm":"aes256", "auth_algorithm":"sha1", "pfs":"modp1536", "lifetime_value":"3600"}' http://localhost:8880/ipsec

curl -H "Content-Type: application/json" -X POST -d '{"node_id":"117bb106-a08b-412f-9ad8-80582c02be03", "name":"tunnel1", "self_ip":"100.64.254.29", "peer_id":"7a5df967-21f6-4549-bfd4-cd69b11d081a", "peer_ip":"100.64.254.129", "type":"vxlan", "mtu":1500, "enabled":True}' http://localhost:8880/tunnel

curl -H "Content-Type: application/json" -X POST -d '{"node_id": "3c91df0d-cb6d-43e1-88b1-0718b3d72f6a", "name": "con1", "tunnel_id":"117bb106-a08b-412f-9ad8-80582c02be03", "ike_policy_id":"59a0c617-0049-40c8-bec3-720e39a3f1a4", "ipsec_policy_id":"ac03be5e-ca29-4f58-98b3-f0b2a7e0d75a", "dpd_action":"hold", "dpd_interval":30, "dpd_timeout":120, "initiator":"start"}' http://localhost:8880/connection

curl -H "Content-Type: application/json" -X POST -d '{"node_id": "f1c20e9a-efc2-4ff3-b202-211f2a25bbfa", "name": "test", "cloud_network_id":4}' http://localhost:8880/network

curl -H "Content-Type: application/json" -X POST -d '{"network_id": "f1c20e9a-efc2-4ff3-b202-211f2a25bbfa", "tunnel_id": "117bb106-a08b-412f-9ad8-80582c02be03", "intercloud_id_out": 126, "intercloud_id_in": 128}' http://localhost:8880/expansion

