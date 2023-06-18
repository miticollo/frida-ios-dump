#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author : AloneMonkey
# blog: www.alonemonkey.com

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import codecs
import os
import re
import shutil
import subprocess
import zipfile
import sys
import tempfile
import threading
import traceback

import frida
import paramiko
from scp import SCPClient
from tqdm import tqdm

IS_PY2 = sys.version_info[0] < 3
if IS_PY2:
    reload(sys)
    sys.setdefaultencoding('utf8')

script_dir = os.path.dirname(os.path.realpath(__file__))

DUMP_JS = os.path.join(script_dir, 'dump.js')

User = 'root'
Password = 'alpine'
Host = 'localhost'
Port = 2222
KeyFileName = None

TEMP_DIR = tempfile.gettempdir()
PAYLOAD_DIR = 'Payload'
PAYLOAD_PATH = os.path.join(TEMP_DIR, PAYLOAD_DIR)
file_dict = {}

finished = threading.Event()


def get_usb_iphone():
    Type = 'usb'
    if int(frida.__version__.split('.')[0]) < 12:
        Type = 'tether'
    device_manager = frida.get_device_manager()
    changed = threading.Event()

    def on_changed():
        changed.set()

    device_manager.on('changed', on_changed)

    device = None
    while device is None:
        devices = [dev for dev in device_manager.enumerate_devices() if dev.type == Type]
        if len(devices) == 0:
            print('Waiting for USB device...')
            changed.wait()
        else:
            device = devices[0]

    device_manager.off('changed', on_changed)

    return device


def generate_ipa(path, display_name):
    ipa_filename = display_name + '.ipa'

    try:
        app_name = file_dict['app']
        for key, value in file_dict.items():
            from_dir = os.path.join(path, key)
            to_dir = os.path.join(path, app_name, value)
            if key != 'app':
                shutil.move(from_dir, to_dir)
        if os.path.exists(ipa_filename):
            os.remove(ipa_filename)
        with zipfile.ZipFile(ipa_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipdir(path, zipf)
        shutil.rmtree(PAYLOAD_PATH)
    except Exception as e:
        print(e)
        finished.set()


def on_message(message, data):
    t = tqdm(unit='B', unit_scale=True, unit_divisor=1024, miniters=1)
    last_sent = [0]

    def progress(filename, size, sent):
        baseName = os.path.basename(filename)
        if IS_PY2 or isinstance(baseName, bytes):
            t.desc = baseName.decode("utf-8")
        else:
            t.desc = baseName
        t.total = size
        t.update(sent - last_sent[0])
        last_sent[0] = 0 if size == sent else sent

    if 'payload' in message:
        payload = message['payload']
        if 'dump' in payload:
            origin_path = payload['path']
            dump_path = payload['dump']

            scp_from = dump_path
            scp_to = PAYLOAD_PATH + '/'

            with SCPClient(ssh.get_transport(), progress=progress, socket_timeout=60) as scp:
                scp.get(scp_from, scp_to)

            chmod_dir = os.path.join(PAYLOAD_PATH, os.path.basename(dump_path))
            chmod_args = ('chmod', '655', chmod_dir)
            try:
                subprocess.check_call(chmod_args)
            except subprocess.CalledProcessError as err:
                print(err)

            index = origin_path.find('.app/')
            file_dict[os.path.basename(dump_path)] = origin_path[index + 5:]

        if 'app' in payload:
            app_path = payload['app']

            scp_from = app_path
            scp_to = PAYLOAD_PATH + '/'
            with SCPClient(ssh.get_transport(), progress=progress, socket_timeout=60) as scp:
                scp.get(scp_from, scp_to, recursive=True)

            chmod_dir = os.path.join(PAYLOAD_PATH, os.path.basename(app_path))
            chmod_args = ('chmod', '755', chmod_dir)
            try:
                subprocess.check_call(chmod_args)
            except subprocess.CalledProcessError as err:
                print(err)

            file_dict['app'] = os.path.basename(app_path)

        if 'done' in payload:
            finished.set()
    t.close()


def compare_applications(a, b):
    a_is_running = a.pid != 0
    b_is_running = b.pid != 0
    if a_is_running == b_is_running:
        if a.name > b.name:
            return 1
        elif a.name < b.name:
            return -1
        else:
            return 0
    elif a_is_running:
        return -1
    else:
        return 1


def cmp_to_key(mycmp):
    """Convert a cmp= function into a key= function"""

    class K:
        def __init__(self, obj):
            self.obj = obj

        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0

        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0

        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0

        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0

        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0

        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0

    return K


def load_js_file(session, filename):
    source = ''
    with codecs.open(filename, 'r', 'utf-8') as f:
        source = source + f.read()
    script = session.create_script(source)
    script.on('message', on_message)
    script.load()

    return script


def create_dir(path):
    path = path.strip()
    path = path.rstrip('\\')
    if os.path.exists(path):
        shutil.rmtree(path)
    try:
        os.makedirs(path)
    except os.error as err:
        print(err)


def open_target_app(device, name):
    print('Start the target app {}'.format(name))

    pid = device.get_process(name).pid
    session = None
    display_name = name
    bundle_identifier = ''

    try:
        if not pid:
            pid = device.spawn([bundle_identifier])
            session = device.attach(pid)
            device.resume(pid)
        else:
            session = device.attach(pid, realm="native")
    except Exception as e:
        print(e)

    return session, display_name, bundle_identifier


# https://stackoverflow.com/a/1855118
def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file),
                       os.path.relpath(os.path.join(root, file),
                                       os.path.join(path, '..')))


def start_dump(session, ipa_name):
    print('Dumping {} to {}'.format(display_name, TEMP_DIR))

    script = load_js_file(session, DUMP_JS)
    script.post('dump')
    finished.wait()

    generate_ipa(PAYLOAD_PATH, ipa_name)

    if session:
        session.detach()


def trim_icon(icon):
    result = dict(icon)
    result["image"] = result["image"][0:16] + b"..."
    return result


PREFIXES = ("/var/containers/Bundle/Application/",
            "/private/var/containers/Bundle/Application/")


def list_processes(device):
    processes = device.enumerate_processes(scope="full")
    for proc in processes:
        params = dict(proc.parameters)
        if "icons" in params:
            params["icons"] = [trim_icon(icon) for icon in params["icons"]]
        if any(proc.parameters['path'].startswith(prefix) for prefix in PREFIXES) and 'appex' not in proc.parameters[
            'path']:
            print(
                f'Process(\n'
                f'  pid={proc.pid},\n'
                f'  name="{proc.name}",\n'
                f'  parameters={{\n'
                f'    "path": "{params["path"]}",\n'
                f'    "user": "{params["user"]}",\n'
                f'    "ppid": {params["ppid"]},\n'
                f'    "started": {params["started"]}\n'
                f'  }}\n'
                f')'
            )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='frida-ios-dump (by AloneMonkey v2.1)')
    parser.add_argument('-l', '--list', dest='list_processes', action='store_true', help='List running apps')
    parser.add_argument('-o', '--output', dest='output_ipa', help='Specify name of the decrypted IPA')
    parser.add_argument('-H', '--host', dest='ssh_host', help='Specify SSH hostname')
    parser.add_argument('-p', '--port', dest='ssh_port', help='Specify SSH port')
    parser.add_argument('-u', '--user', dest='ssh_user', help='Specify SSH username')
    parser.add_argument('-P', '--password', dest='ssh_password', help='Specify SSH password')
    parser.add_argument('-K', '--key_filename', dest='ssh_key_filename', help='Specify SSH private key file path')
    parser.add_argument('target', nargs='?', help='Display name of the target app')

    args = parser.parse_args()

    exit_code = 0
    ssh = None

    if not len(sys.argv[1:]):
        parser.print_help()
        sys.exit(exit_code)

    device = get_usb_iphone()

    if args.list_processes:
        list_processes(device)
    else:
        name_or_bundleid = args.target
        output_ipa = args.output_ipa
        # update ssh args
        if args.ssh_host:
            Host = args.ssh_host
        if args.ssh_port:
            Port = int(args.ssh_port)
        if args.ssh_user:
            User = args.ssh_user
        if args.ssh_password:
            Password = args.ssh_password
        if args.ssh_key_filename:
            KeyFileName = args.ssh_key_filename

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(Host, port=Port, username=User, password=Password, key_filename=KeyFileName)

            create_dir(PAYLOAD_PATH)
            (session, display_name, bundle_identifier) = open_target_app(device, name_or_bundleid)
            if output_ipa is None:
                output_ipa = display_name
            output_ipa = re.sub('\.ipa$', '', output_ipa)
            if session:
                start_dump(session, output_ipa)
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            print(e)
            print('Try specifying -H/--hostname and/or -p/--port')
            exit_code = 1
        except paramiko.AuthenticationException as e:
            print(e)
            print('Try specifying -u/--username and/or -P/--password')
            exit_code = 1
        except Exception as e:
            print('*** Caught exception: %s: %s' % (e.__class__, e))
            traceback.print_exc()
            exit_code = 1

    if ssh:
        ssh.close()

    if os.path.exists(PAYLOAD_PATH):
        shutil.rmtree(PAYLOAD_PATH)

    sys.exit(exit_code)
