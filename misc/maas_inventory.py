#!/usr/bin/env python

"""
A dynamic inventory script for MAAS that can be used as an inventory for ansible.

This script fetches hosts data for ansible from MAAS, using tags in order to
identify groups and roles.
The script should be copied to AWX/Tower within the inventory script dialog interface.
Using the `--list` argument to invoke the dynamic inventory process.

It is also possible to run the script as a standalone script or as a replacement for the
Ansible `hosts` file.

See https://docs.maas.io/2.4/en/api for API details
"""

import argparse
import json
import oauth.oauth as oauth
import os
import pickle
import re
import requests
import sys
import uuid
import urllib.parse


#import urllib.parse as urlparse


class Call_inventory:
    """Provides methods to retrieve information from MAAS API."""

    def __init__(self):
        """Check for precense of mandatory environment variables and route commands."""
        self.supported = '2.0'
        self.apikeydocs = 'https://docs.maas.io/2.4/en/manage-cli#log-in-(required)'

        self.maas = os.environ.get("MAAS_API_URL", None)
        if not self.maas:
            sys.exit("API_MAAS_URL environment variable not found. Set this to http<s>://<HOSTNAME or IP>/MAAS/api/{}".format(self.supported))
        self.token = os.environ.get("MAAS_API_KEY", None)
        if not self.token:
            sys.exit("API_MAAS_KEY environment variable not found. See {} for getting a MAAS API KEY".format(self.apikeydocs))
        self.args = None

        # Parse command line arguments
        self.cli_handler()

        if self.args.list:
            print( json.dumps(self.inventory(), sort_keys=True, indent=2) )
        elif self.args.host:
            print( json.dumps(self.host(), sort_keys=True, indent=2) )
        elif self.args.nodes:
            print( json.dumps(self.nodes(), sort_keys=True, indent=2) )
        elif self.args.tags:
            print( json.dumps(self.tags(), sort_keys=True, indent=2) )
        elif self.args.tag:
            print( json.dumps(self.tag(), sort_keys=True, indent=2) )
        elif self.args.supported:
            print( self.supported() )
        else:
            sys.exit(1)

    def supported(self):
        """Display MAAS API version supported by this tool."""
        return self.supported

    def auth(self):
        """Split the user's API key from MAAS into its component parts (Maas UI > Account > MAAS Keys)."""
        (consumer_key, key, secret) = self.token.split(':')
        # Format an OAuth header
        resource_token_string = "oauth_token_secret={}&oauth_token={}".format(secret, key)
        resource_token = oauth.OAuthToken.from_string(resource_token_string)
        consumer_token = oauth.OAuthConsumer(consumer_key, "")
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            consumer_token, token=resource_token, http_url=self.maas,
            parameters={'auth_nonce': uuid.uuid4().get_hex()})
        oauth_request.sign_request(
            oauth.OAuthSignatureMethod_PLAINTEXT(), consumer_token, resource_token)
        headers = oauth_request.to_header()
        headers['Accept'] = 'application/json'
        return headers

    def host(self):
        """Return data on a single host/node."""
        host = {}
        headers = self.auth()

        url = "{}/nodes/{}/".format(self.maas.rstrip(), self.args.host)
        request = requests.get(url, headers=headers)
        return json.loads(request.text)

    def tags(self):
        """Fetch a simple list of available tags from MAAS."""
        headers = self.auth()

        url = "{}/tags/".format(self.maas.rstrip())
        request = requests.get(url, headers=headers)
        response = json.loads(request.text)
        tag_list = [item["name"] for item in response]
        return tag_list

    def tag(self):
        """Fetch detailed information on a particular tag from MAAS."""
        headers = self.auth()

        url = "{}/tags/{}/?op=machines".format(self.maas.rstrip(), self.args.tag)
        request = requests.get(url, headers=headers)
        return json.loads(request.text)

    def inventory(self):
        """Look up hosts by tag(s) and zone(s) and return a dict that Ansible will understand as an inventory."""
        tags = self.tags()
        ansible = {}
        host_seen = []  # book keeping to ensure hosts are only listed once
        for tag in tags:
            headers = self.auth()
            url = "{}/tags/{}/?op=machines".format(self.maas.rstrip(), tag)
            request = requests.get(url, headers=headers)
            response = json.loads(request.text)
            group_name = tag
            hosts = []
            for server in response:
                if server['status_name'] == 'Deployed' and server['zone']['name'] == 'MGRAST':
                            hosts.append(server['fqdn'])
                            host_seen.append(server['fqdn']) # book keeping
                            ansible[group_name] = {
                                "hosts": hosts,
                                "vars": {}
                    }

        nodes = self.nodes()
        hosts = []
        for node in nodes:
           zone = node['zone']['name']
           if node['node_type_name'] != 'Machine' or node['status_name'] != 'Deployed' or zone != 'MGRAST' or node['fqdn'] in host_seen:
             continue
           hosts.append(node['fqdn'])
           ansible[zone] = {
                "hosts": hosts,
                "vars": {}
           }
        # PS 2018-05-24: Create metadata block for ansible (dynamic inventory)
        # The below code gets a dump of all nodes provisioned by MAAS and then builds out a _meta JSON formated attribute.
        # node_dump = self.nodes()
        # nodes = {
        #     '_meta': {
        #         'hostvars': {}
        #     }
        # }
        #
        # for node in node_dump:
        #     if not node['tag_names']:
        #         pass
        #     else:
        #         nodes['_meta']['hostvars'][node['hostname']] = {
        #             'mac_address': node['macaddress_set'][0]['mac_address'],
        #             'system_id': node['system_id'],
        #             'power_type': node['power_type'],
        #             'os': node['osystem'],
        #             'os_release': node['distro_series']
        #         }

        # Need to merge ansible and nodes dict()s as a shallow copy, or Ansible shits itself and throws an error
        result = ansible.copy()
        # result.update(nodes)
        return result

    def nodes(self):
        """Return a list of nodes from the MAAS API."""
        headers = self.auth()
        url = "%s/nodes/" % self.maas.rstrip()
        request = requests.get(url, headers=headers)
        response = json.loads(request.text)
        return response

    def cli_handler(self):
        """Manage command line options and arguments."""
        parser = argparse.ArgumentParser(description='Dynamically produce an Ansible inventory from MAAS.', add_help=False)
        parser.add_argument('-l', '--list', action='store_true', help='List instances by tag. (default)')
        parser.add_argument('-h', '--host', action='store', help='Get variables relating to a specific instance.')
        parser.add_argument('-n', '--nodes', action='store_true', help='List all nodes registered under MAAS.')
        parser.add_argument('-t', '--tags', action='store_true', help='List all tags registered under MAAS.')
        parser.add_argument('--tag', action='store', help='Get details for a specific tag registered under MAAS.')
        parser.add_argument('-s', '--supported', action='store_true', help='List which MAAS API version are supported.')
        parser.add_argument('--help', action='help', help='Show this help message and exit.')

        # print help when no arguments are given.
        if len(sys.argv)==1:
            parser.print_help()
            sys.exit(1)

        self.args = parser.parse_args()

if __name__ == "__main__":
    Call_inventory()
