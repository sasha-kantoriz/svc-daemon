import socket
import json
import subprocess
import multiprocessing
import sys
import time
import re
from datetime import datetime
from optparse import OptionParser
from random import randrange

import config
import utilities


def parse_cli_args():
    parser = OptionParser()
    parser.add_option('-a', '--socket_addr', dest='socket_addr')
    parser.add_option('-p', '--socket_port', dest='socket_port')
    options, args = parser.parse_args()
    return {
        'server_addr': options.socket_addr,
        'server_port': options.socket_port
    }


def handle_payload(cmd, *args, **kwargs):
    command_payload = [cmd] + list(args)
    # try:
    #     result = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE)
    # except subprocess.CalledProcessError as e:
    #     result = f'STDOUT: {e.stdout}, STDERR: {e.stderr}'
    # return result
    pipes = subprocess.Popen(command_payload, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = pipes.communicate()
    if pipes.returncode == 0:
        return std_out
    else:
        print(std_err)
        return std_err


def cluster_fs_worker(sock_addr, port):
    fs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # fs_socket.settimeout(0.01)
    fs_port = int(port)
    fs_socket.connect((sock_addr, fs_port))
    while True:
        try:
            time.sleep(config.CLUSTER_FS_RELICATION_INTERVAL)
            # FS updates watcher
            fs_state = utilities.init_fs_state(
                config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME)
            fs_state_json = json.dumps(fs_state).encode('utf-8')
            fs_socket.send(fs_state_json)

            time.sleep(1)
            latest_fs_data = json.loads(fs_socket.recv(config.MAX_TRANSMIT_BYTES))
            # update JSON fs_state
            utilities.update_fs_state(
                config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME, latest_fs_data)
            # write changes to directory
            utilities._update_fs(config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME)
        except socket.timeout:
            print('FS timeout')
        except socket.error as e:
            print(e)
            print('Cluster FS: socket connecion aborted...')
            fs_socket.close()
            return
        except Exception as e:
            traceback = f'Exception: {e}, Line number: {e.__traceback__.tb_lineno}'
            print(traceback)

def main(sock_addr, sock_port):
    """
        Main program entrypoint,
        handles error in try/catch block and 
        reestablishes connection on unhandled exceptions
    """

    opts = parse_cli_args()
    server_addr = sock_addr, int(sock_port)

    ip_addr = utilities.get_ip()

    while 1:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # sock.settimeout(5)
            sock.connect(server_addr)

            connected_msg = f'Slave {ip_addr} initiated at {datetime.now()}'.encode('utf-8')
            sock.sendall(connected_msg)
            print(connected_msg)

            while True:
                try:
                    data = sock.recv(config.MAX_TRANSMIT_BYTES).decode('utf-8')
                    # connection HEATHCHECK 
                    if data == 'Ping':
                        print(f'HEALTHCHECK {datetime.now()} <<< Ping')
                        sock.sendall(b'Pong')
                        continue
                    # cluster FS initial connection
                    elif re.match('\d+', data):
                        try:
                            cluster_fs_process = multiprocessing.Process(target=cluster_fs_worker, args=(sock_addr, data))
                            cluster_fs_process.start()
                        except Exception as e:
                            print(e)
                    # worker
                    elif data:
                        print(f'Received at : {datetime.now()} << {data}')
                        # handle payload
                        capture = handle_payload(cmd=data)
                        sock.sendall(capture)
                    # server is off
                    else:
                        break
                except socket.timeout:
                    # capture traceback
                    print('Timeout receiving command data from Command&Control')
                    time.sleep(1)
        except socket.error as e:
            sock.close()
            ttr = randrange(0, 100)
            print(e)
            print(f'Waiting {ttr} to retry connection attempt.')
            time.sleep(ttr)
        # finally:
        #     sock.close()
            # main(sock_addr, sock_port)


if __name__ == '__main__':
    opts = parse_cli_args()
    main(
        opts['server_addr'], 
        opts['server_port']
    )
