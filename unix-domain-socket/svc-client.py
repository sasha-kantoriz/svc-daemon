import socket
import sys
from optparse import OptionParser
import time
import pdb


def parse_cli_args():
    argparser = OptionParser()
    argparser.add_option('-s', '--socket', dest='socket_addr')
    options, args = argparser.parse_args()
    return {
        'socket_addr': options.socket_addr or '/opt/svc-daemon/uds_socket.sock'
    }
cli_args = parse_cli_args()


# Create a UDS socket
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(5)

# Connect the socket to the port where the server is listening
server_address = cli_args['socket_addr']
print('connecting to {}'.format(server_address))
try:
    sock.connect(server_address)
except socket.error as msg:
    print(msg)
    sys.exit(1)

try:

    # Send data
    message = b'This is the message.  It will be repeated.'
    print('sending {!r}'.format(message))
    sock.sendall(message)

    # amount_received = 0
    # amount_expected = len(message)

    # while amount_received < amount_expected:
    #     data = sock.recv(1024)
    #     amount_received += len(data)
    #     print('received {!r}'.format(data))

    while True:
        try:
            data = sock.recv(1024)
            # pdb.set_trace()
            if data:
                print(f'received {data}')
        except socket.timeout:
            print('Timeout receiving the data from server')
            time.sleep(1)

finally:
    print('closing socket')
    sock.close()