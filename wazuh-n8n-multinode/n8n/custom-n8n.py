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

    options_file = next((args[i] for i in range(4, len(args)) if args[i].endswith('options')), '')
    json_options = get_json_safe(options_file, is_alert=False)
    json_alert = get_json_safe(alert_file, is_alert=True)

    debug(f"# Loaded alert file '{alert_file}'")
    debug(f"# Loaded options file '{options_file}'")

    msg = generate_msg(json_alert, json_options)
    if msg:
        debug(f'# Sending payload to {webhook}')
        send_msg(msg, webhook)
    else:
        debug('# Message generation returned empty. Skipping send.')

def get_json_safe(file_path, is_alert=False):
    if not file_path:
        return {}

    try:
        with open(file_path) as f:
            return json.load(f)
    except FileNotFoundError:
        log(f"# File not found: {file_path}")
        sys.exit(ERR_FILE_NOT_FOUND)
    except json.JSONDecodeError as e:
        log(f"# Invalid JSON in {'alert' if is_alert else 'options'} file: {file_path}")
        log(f"# JSON error: {e}")
        with open(file_path, 'r', errors='ignore') as f:
            log(f"# File content:\n{f.read()}")
        sys.exit(ERR_INVALID_JSON)

def generate_msg(alert, options):
    if not alert or not isinstance(alert, dict):
        return ''

    level = alert.get('rule', {}).get('level', 1)

    # Severity: matches TheHive 1-4 scale
    # Low=1 (1-6), Medium=2 (7-11), High=3 (12-14), Critical=4 (15)
    severity = 4 if level >= 15 else 3 if level >= 12 else 2 if level >= 7 else 1

    data = alert.get('data', {})
    rule = alert.get('rule', {})
    agent = alert.get('agent', {})

    msg = {
        'source': 'wazuh',
        'event_type': 'security_alert',
        'severity': severity,
        'severity_label': get_severity_label(severity),
        'alert_title': rule.get('description', 'N/A'),
        'alert_text': alert.get('full_log', 'N/A'),
        'rule_id': rule.get('id', 'N/A'),
        'rule_level': level,
        'rule_groups': rule.get('groups', []),
        'mitre_technique': rule.get('mitre', {}).get('technique', []),
        'mitre_tactic': rule.get('mitre', {}).get('tactic', []),
        'timestamp': alert.get('timestamp'),
        'alert_id': alert.get('id'),
        'agent': {
            'id': agent.get('id', 'N/A'),
            'name': agent.get('name', 'N/A'),
            'ip': agent.get('ip', 'N/A')
        },
        'src_ip': data.get('srcip') or data.get('win.eventdata.ipAddress', ''),
        'dst_ip': data.get('dstip', ''),
        'src_user': data.get('srcuser') or data.get('win.eventdata.targetUserName', ''),
        'src_port': data.get('srcport', ''),
        'location': alert.get('location', 'N/A'),
        'decoder': alert.get('decoder', {}).get('name', 'N/A'),
        'all_fields': alert
    }

    if options:
        msg.update(options)

    return json.dumps(msg)

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

def get_severity_label(severity):
    return {1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical'}.get(severity, 'Unknown')

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


