#!/usr/bin/env python3

import json
import os
import sys

# Exit error codes
ERR_NO_REQUEST_MODULE = 1
ERR_BAD_ARGUMENTS = 2
ERR_FILE_NOT_FOUND = 6
ERR_INVALID_JSON = 7

try:
    import requests
except ModuleNotFoundError:
    print("No module 'requests' found. Install: pip install requests")
    sys.exit(ERR_NO_REQUEST_MODULE)

# Global vars
debug_enabled = False
pwd = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LOG_FILE = f'{pwd}/logs/integrations.log'

# Constants
ALERT_INDEX = 1
WEBHOOK_INDEX = 3


def main(args):
    global debug_enabled
    try:
        if len(args) >= 4:
            msg = ' '.join(args[1:6])
            debug_enabled = 'debug' in args
        else:
            msg = '# ERROR: Wrong arguments'
            log(msg)
            sys.exit(ERR_BAD_ARGUMENTS)

        log(msg)
        process_args(args)

    except Exception as e:
        log(f'# Unexpected error: {e}')
        sys.exit(ERR_INVALID_JSON)


def process_args(args):
    debug('# Running n8n integration script')

    alert_file = args[ALERT_INDEX]
    webhook = args[WEBHOOK_INDEX]

    json_alert = get_json_safe(alert_file)
    debug(f"# Loaded alert file '{alert_file}'")

    if json_alert:
        debug(f'# Sending alert to {webhook}')
        send_msg(json.dumps(json_alert), webhook)
    else:
        debug('# Empty alert, skipping.')


def get_json_safe(file_path):
    try:
        with open(file_path) as f:
            return json.load(f)
    except FileNotFoundError:
        log(f'# File not found: {file_path}')
        sys.exit(ERR_FILE_NOT_FOUND)
    except json.JSONDecodeError as e:
        log(f'# Invalid JSON: {e}')
        sys.exit(ERR_INVALID_JSON)


def send_msg(msg, url):
    headers = {'Content-Type': 'application/json', 'Accept-Charset': 'UTF-8'}
    try:
        res = requests.post(url, data=msg, headers=headers, timeout=10)
        debug(f'# Response code: {res.status_code}')
        debug(f'# Response body: {res.text}')
    except requests.exceptions.Timeout:
        log('# ERROR: Webhook request timed out')
    except requests.exceptions.ConnectionError:
        log('# ERROR: Connection error (check webhook URL)')
    except Exception as e:
        log(f'# ERROR sending request: {e}')


def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(msg + '\n')
    if debug_enabled:
        print(msg)


def debug(msg):
    if debug_enabled:
        log(msg)


if __name__ == '__main__':
    main(sys.argv)
