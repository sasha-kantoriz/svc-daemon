import socket
import os
import json
import base64
import hashlib
import datetime
from urllib import parse


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
        client['conn'].sendall(b'Ping')
        if client['conn'].recv(1024):
            return True
        else:
            client['conn'].close()
            return False
    except socket.error as e:
        print(e)
        client['conn'].close()
        return False


"""
Cluster FS functional:

        file = {
            :name,
            :type,
            :path,
            :url,
            :hash,
            :content,
            :modified_at,
            :checked_at
        }

"""


def init_fs(dir_path):
    os.makedirs(dir_path, exist_ok=True)


def init_fs_state(fs_state_file, fs_directory):
    try:
        with open(fs_state_file) as f:
            fs_state = json.load(f)
    except (json.decoder.JSONDecodeError, FileNotFoundError):        
        fs_state = traverse_fs_files(fs_directory)
        with open(fs_state_file, 'w') as f:
            json.dump(fs_state, f)
    return fs_state


def traverse_fs_files(dir_path):
    _files = []
    for root, subdirs, files in os.walk(dir_path):
        for dir_ in subdirs:
            dir_path = os.path.join(root, dir_)
            subdir = {
                "name": dir_,
                "type": "directory",
                "path": dir_path,
                "parent_dir": root,
                "url": f'{get_directory_url(dir_path)}',
                "hash": None,
                "content": None, # list of nested files?
                "modified_at": None,
                "checked_at": datetime.datetime.now().isoformat()
            }
            _files.append(subdir)
        for file_ in files:
            file_path = os.path.join(root, file_)
            file_content = open(file_path).read()
            f = {
                "name": file_,
                "type": "file",
                "path": file_path,
                "parent_dir": root,
                "url": f"{get_file_url(file_path)}",
                "hash": hashlib.md5(file_content.encode('utf-8')).hexdigest(),
                "content": file_content,
                "modified_at": None,
                "checked_at": datetime.datetime.now().isoformat()
            }
            _files.append(f)
    return _files


def get_directory_url(dir_path):
    return f'/directory_{base64.b64encode(dir_path.encode("utf-8")).decode("utf-8")}'

def get_file_url(file_path):
    return f'/file_{base64.b64encode(file_path.encode("utf-8")).decode("utf-8")}'


def traverse_directory(fs_state_file, fs_directory, dir_path):
    fs_state = get_fs_state(fs_state_file, fs_directory)

    _directory_url = get_directory_url(dir_path)
    _directory, _files = fs_get_by_url(fs_state_file, fs_directory, _directory_url), []

    if _directory.get('parent_dir'):
        parent_directory = _directory.get('parent_dir')
        _files.append(
            {
                "name": '..',
                "type": "directory",
                "path": parent_directory,
                "url": f'{get_directory_url(parent_directory)}',
                "hash": None,
                "content": None, # list of nested files?
                "modified_at": None,
                "checked_at": datetime.datetime.now().isoformat()
            }
        )

    for _file in fs_state:
        if _file['parent_dir'] == dir_path:
            _files.append(_file)
    return _files


def get_fs_state(fs_state_file, fs_directory):
    with open(fs_state_file) as f:
        return json.load(f)


def fs_get_by_url(fs_state_file, fs_directory, file_url):
    fs_state = get_fs_state(fs_state_file, fs_directory)
    for _file in fs_state:
        if _file['url'] == file_url:
            return _file
    return {}