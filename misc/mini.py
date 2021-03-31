#!/usr/bin/env python3
from apiclient import maas_client
import configparser
config = configparser.ConfigParser()
config.read('./maasinv.ini')
APIKEY = config['maas']['apikey']
MAAS_URL = config['maas']['url']
auth = maas_client.MAASOAuth(*APIKEY.split(":"))
client = maas_client.MAASClient(auth, maas_client.MAASDispatcher(), MAAS_URL)
data = client.get("nodes",op=list).read()

print (data)
