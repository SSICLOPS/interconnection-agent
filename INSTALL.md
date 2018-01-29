# Installation notes

## Ubuntu

```sh
apt install python3-pip git strongswan openvswitch-switch
pip3 install -r requirements
git submodule update --init
```

Create a folder */etc/interco* and copy the files from the *conf* folder there

```sh
mkdir /etc/interco
cp conf/agent.conf /etc/interco/
cp conf/controller.conf /etc/interco
cp conf/log.cfg /etc/interco
cp conf/path.conf /etc/interco
```

Install the service and create the required files

```sh
cp intercoagt.service /etc/systemd/system
cp intercoctl.service /etc/systemd/system
systemctl daemon-reload
touch /etc/ipsec.d/vpn.conf
touch /etc/ipsec.d/vpn.secrets
```

The controller and the agents can either be run using systemctl:

```sh
systemctl start intercoctl
systemctl start intercoagt
```

or in command line :

```sh
python3 controller/controller.py -c /etc/interco/controller.conf
python3 agent/agent.py -c /etc/interco/agent.conf

Then edit /etc/interco/* to make it fit for your case. Absolute path for files
are recommended.

