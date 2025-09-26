#!/usr/bin/env python3
"""
IAG Dynamic Inventory Script - With optional YAML output for debugging
./iag_inventory.py --list --yaml       
"""

import json
import sys
import os
import argparse
import requests

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Configuration
IAG_HOST = os.getenv("IAG_HOST", "localhost")
IAG_PORT = int(os.getenv("IAG_PORT", "8083"))
IAG_USERNAME = os.getenv("IAG_USERNAME", "admin@itential")
IAG_PASSWORD = os.getenv("IAG_PASSWORD", "admin")
IAG_PROTOCOL = os.getenv("IAG_PROTOCOL", "http")

# API endpoints
LOGIN_ENDPOINT = f"{IAG_PROTOCOL}://{IAG_HOST}:{IAG_PORT}/api/v2.0/login"
DEVICES_ENDPOINT = f"{IAG_PROTOCOL}://{IAG_HOST}:{IAG_PORT}/api/v2.0/devices"


def get_inventory():
    """Get the full inventory from IAG"""
    try:
        # Step 1: Login
        login_data = {
            "username": IAG_USERNAME,
            "password": IAG_PASSWORD
        }
        
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.post(LOGIN_ENDPOINT, json=login_data, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()
        token = token_data.get("token")
        
        if not token:
            return {"all": {"hosts": []}, "_meta": {"hostvars": {}}}
        
        # Step 2: Get devices
        headers = {
            "accept": "application/json",
            "Authorization": token
        }
        
        params = {"order": "ascending"}
        
        response = requests.get(DEVICES_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        
        devices_data = response.json()
        
        # Step 3: Build inventory in correct Ansible format
        inventory = {
            "all": {
                "hosts": [],  # Must be a list!
                "children": ["iag_devices"]
            },
            "iag_devices": {
                "hosts": []  # Must be a list!
            },
            "_meta": {
                "hostvars": {}
            }
        }
        
        devices = devices_data.get("data", [])
        
        for device in devices:
            device_name = device.get("name", "unknown")
            variables = device.get("variables", {})
            ansible_host = variables.get("ansible_host", "")
            
            # Format host name
            host_name = device_name
            if device_name == "device1" and ansible_host:
                hostname_parts = ansible_host.split(".")
                if hostname_parts:
                    base_name = hostname_parts[0]
                    for prefix in ["sandbox-", "lab-", "test-"]:
                        if base_name.startswith(prefix):
                            base_name = base_name[len(prefix):]
                            break
                    host_name = base_name
            
            if variables:
                inventory["all"]["hosts"].append(host_name)
                inventory["iag_devices"]["hosts"].append(host_name)
                inventory["_meta"]["hostvars"][host_name] = variables
        
        return inventory
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return {"all": {"hosts": []}, "_meta": {"hostvars": {}}}


def main():
    # Check if this is being called for debugging with --yaml
    if "--yaml" in sys.argv:
        # Remove --yaml from args for normal processing
        sys.argv.remove("--yaml")
        use_yaml = True
    else:
        use_yaml = False
    
    # Standard Ansible dynamic inventory arguments
    if len(sys.argv) == 2 and sys.argv[1] == '--list':
        inventory = get_inventory()
        if use_yaml and YAML_AVAILABLE:
            print("---")
            print(yaml.dump(inventory, default_flow_style=False))
        else:
            print(json.dumps(inventory))
    elif len(sys.argv) == 3 and sys.argv[1] == '--host':
        inventory = get_inventory()
        hostname = sys.argv[2]
        host_vars = inventory.get("_meta", {}).get("hostvars", {}).get(hostname, {})
        if use_yaml and YAML_AVAILABLE:
            print("---")
            print(yaml.dump(host_vars, default_flow_style=False))
        else:
            print(json.dumps(host_vars))
    else:
        # Default - Ansible calling without arguments
        inventory = get_inventory()
        print(json.dumps(inventory))


if __name__ == "__main__":
    main()