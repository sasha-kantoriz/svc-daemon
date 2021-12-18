from datetime import datetime
import socket
import json
import jsonpatch
import time
import base64
import jinja2
from urllib.parse import unquote_plus
from optparse import OptionParser
import multiprocessing

import config
import utilities


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

templateLoader = jinja2.FileSystemLoader(searchpath="templates")
templateEnv = jinja2.Environment(loader=templateLoader)

class Client(object):
    """
        :thread
        :connection/socket
        :cluster_fs_socket
    """
    def __init__(self, ip, port, connection, socket_thread, cluster_fs_thread):
        self.ip = ip
        self.port = port
        self.address = base64.b64encode(f'{ip}:{port}'.encode('utf-8')).decode('utf-8')  #addr
        self.connection = connection
        self.socket_thread = socket_thread
        self.cluster_fs_thread = cluster_fs_thread


def _worker_process(worker_connection, client=None):
    """
        Process for worker's cluster FS socket communication
    """
    # cluster fs thread per client
    process_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    process_socket.bind(('0.0.0.0', 0))
    # process_socket.settimeout(0.1)
    port = process_socket.getsockname()[1]
    worker_connection.sendall(bytes(str(port).encode('utf-8')))
    process_socket.listen(1)
    process_connection, process_client_addr = process_socket.accept()
    while True:
        try:
            time.sleep(config.CLUSTER_FS_RELICATION_INTERVAL)
            # FS updates watcher: _traverse?
            fs_state = utilities.init_fs_state(
                config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME)

            worker_fs_data = json.loads(
                process_connection.recv(config.MAX_TRANSMIT_BYTES))

            # update/merge JSON
            # apply patches from worker state
            patch = jsonpatch.make_patch(fs_state, worker_fs_data)
            latest_fs_state = patch.apply(fs_state) #, in_place=True)
            # add from server all missing files by ['url']
            client_files_urls = [f['url'] for f in latest_fs_state]
            for f in fs_state:
                if not f['url'] in client_files_urls:
                    latest_fs_state.append(f)

            utilities.update_fs_state(
                config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME, latest_fs_state)
            utilities._update_fs(
                config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME)
            
            # send updated JSON
            fs_state_json = json.dumps(latest_fs_state).encode('utf-8')
            process_connection.sendall(fs_state_json)
            # cluster fs watcher
            # updates handler
            # write changes
            # pass process_socket in
        except socket.error as e:
            print(e)
            print('Remote worker closed/breaked connection. Terminating.')
            process_connection.close()
            return
        except Exception as e:
            traceback = f'Exception: {e}, Line number: {e.__traceback__.tb_lineno}'
            print(traceback)
            return


# utilities.init_fs(config.CLUSTER_FS_DIR_NAME)
# form or read FS JSON
utilities.init_fs_state(config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME)


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_address = opts['socket_host'], int(opts['socket_port'])
sock.bind(server_address)
sock.listen(config.MAX_WORKERS)

connections = list()
while True:
    try:
        connection, client_addr = sock.accept()

        print(f'New conn from {client_addr}')
        if not client_addr[0] in (utilities.get_ip(), 'localhost', '127.0.0.1'):
            conn = {
                'conn': connection,  #connection
                'ip': client_addr[0],  #ip
                'port': client_addr[1],  #port
                'url': base64.b64encode(f'{client_addr[0]}:{client_addr[1]}'.encode('utf-8')).decode('utf-8'),  #addr
                'history': [],
                'connected_at': datetime.now(),
                'uptime': 0
            }

        payload = b'whoami'

        connections = [conn for conn in connections if utilities._check_conn(conn)]
        utilities.init_fs_state(config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME)

        data = connection.recv(config.MAX_TRANSMIT_BYTES).decode('utf-8')
        # slave connected
        if data.startswith('Slave'):
            connections.append(conn)
            worker_process = multiprocessing.Process(target=_worker_process, args=(connection,))
            worker_process.start()
        elif data.startswith('GET / '):
            # payload URLs: POST /b64<payload>?b64<host:port>
            # add payload input field
            print(f'Web interface Request data: << GET /index.html')

            files = utilities.traverse_directory(config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME, config.CLUSTER_FS_DIR_NAME)

            template = templateEnv.get_template('index.html')
            response = template.render(connections=connections, directory=config.CLUSTER_FS_DIR_NAME, files=files)
            
            connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
            connection.send(response.encode('utf-8'))
            connection.close()
        elif data.startswith('GET /worker_'):
            try:
                host = data.split()[1][8:] #b64decode after /worker_
                print(f'Web interface Request data: << GET /worker_{host}')
                worker_connection = None
                for conn in connections:
                    if conn['url'] == host:
                        worker_connection = conn
                        break
                template = templateEnv.get_template('worker.html')
                response = template.render(connections=connections, conn=worker_connection, history=worker_connection['history'])
                connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
                connection.send(response.encode('utf-8'))
                connection.close()
            except Exception as e:
                template = templateEnv.get_template('error.html')
                traceback = f'Exception: {e}, Line number: {e.__traceback__.tb_lineno}'
                response = template.render(traceback=traceback)
                connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
                connection.send(response.encode('utf-8'))
                connection.close()
        elif data.startswith('POST /payload_'):
            # encode payload b64
            # payload: POST /b64<host:port>
            # payload from textarea form input
            # maintain commands history
            host = data.split()[1][9:] #b64decode split(':')
            payload = unquote_plus(data.split()[-1].split('payload=')[1])
            #host, port = base64.b64decode(host).decode('utf-8').split(':')
            worker_connection = None
            for conn in connections:
                if conn['url'] == host:
                    worker_connection = conn
                    break
            print(f'sending payload to {host}: >> {payload}')
            worker_connection['conn'].sendall(payload.encode('utf-8'))
            # render payload result
            try:
                worker_connection['conn'].settimeout(config.COMMAND_TIMEOUT)
                response_data = worker_connection['conn'].recv(config.MAX_TRANSMIT_BYTES).decode('utf-8')
            except socket.timeout:
                response_data = ''
                worker_connection['conn'].settimeout(None)
            worker_connection['history'].append(f'>>> {payload}\n<<< {response_data}')
            print(f'Slave {host} reply: << {response_data}')
            template = templateEnv.get_template('worker.html')
            response = template.render(connections=connections, conn=worker_connection, response=response_data, history=worker_connection['history'])
            connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
            connection.send(response.encode('utf-8'))
            connection.close()
        elif data.startswith('GET /file_'):
            file_url = data.split()[1]
            response = utilities.fs_get_by_url(config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME, file_url)['content']

            connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
            connection.send(response.encode('utf-8'))
            connection.close()
        elif data.startswith('GET /directory_'):
            # TODO: read from cluster FS JSON //.DS_Store.json
            directory = base64.b64decode(data.split()[1][11:]).decode('utf-8')

            files = utilities.traverse_directory(config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME, directory)

            template = templateEnv.get_template('index.html')
            response = template.render(connections=connections, directory=directory, files=files)

            connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
            connection.send(response.encode('utf-8'))
            connection.close()
        elif data.startswith('POST /new_file'):
            file_path, file_content = data.split()[-1].split('&')
            file_path = unquote_plus(file_path.split('path=')[1])
            file_content = unquote_plus(file_content.split('content=')[1])
            try:
                with open(file_path, 'w') as _file:
                    _file.write(file_content)
            except Exception as e:
                template = templateEnv.get_template('error.html')
                traceback = f'Exception: {e}, Line number: {e.__traceback__.tb_lineno}'
                response = template.render(traceback=traceback)
                connection.sendall(b'HTTP/1.1 200 OK\r\n\r\n')
                connection.send(response.encode('utf-8'))
                connection.close()
            files = utilities.traverse_directory(config.CLUSTER_FS_STORAGE_FILE, config.CLUSTER_FS_DIR_NAME, config.CLUSTER_FS_DIR_NAME)

            template = templateEnv.get_template('index.html')
            response = template.render(connections=connections, directory=config.CLUSTER_FS_DIR_NAME, files=files)
            
            connection.sendall(b'HTTP/1.1 201 CREATED\r\n\r\n')
            connection.send(response.encode('utf-8'))
            connection.close()
        elif data.startswith('GET /favicon'):
            connection.sendall(b'HTTP/1.1 404 Not Found\r\n\r\n')
            connection.close()
        elif data.startswith('GET'):
            print(f'Request data: << {data}')
            connection.sendall(b'HTTP/1.1 404 Not Found\r\n\r\n')
            connection.close()
            # _worker_process(connection)
        elif not data: #break  # else?
            pass
        else:
            print(f'{client_addr}: << {data}')
    except Exception as e:
        traceback = f'Exception: {e}, Line number: {e.__traceback__.tb_lineno}'
        print(e)
        print(traceback)
        # sock.close()
