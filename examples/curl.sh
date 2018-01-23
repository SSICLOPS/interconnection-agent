#!/bin/sh

curl -H "Content-Type: application/json" -X POST -d '{"name":"ike1","ike_version":"ikev2","encryption_algorithm":"aes256","auth_algorithm":"sha1","pfs":"modp1536","lifetime_value":"3600"}' http://localhost:8880/ike

curl -H "Content-Type: application/json" -X POST -d '{"name":"ipsec1","transform_protocol":"esp","encapsulation_mode":"transport","encryption_algorithm":"aes256","auth_algorithm":"sha1","pfs":"modp1536","lifetime_value":"3600"}' http://localhost:8880/ipsec

curl -H "Content-Type: application/json" -X POST -d '{"name":"tunnel1", "self_ip":"100.64.254.29", "peer_id":"7a5df967-21f6-4549-bfd4-cd69b11d081a", "peer_ip":"100.64.254.129", "type":"vxlan", "mtu":1500, "enabled":True}' http://localhost:8880/tunnel

