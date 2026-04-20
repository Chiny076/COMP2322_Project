#!/usr/bin/env python3
# MultiThreadedWebServer.py
# A multi-threaded web server supporting HTTP/1.1 features

import socket
import threading
import os
import time
import mimetypes
from datetime import datetime, timezone
from email.utils import formatdate, parsedate_to_datetime
import logging

# -------------------- Configuration --------------------
SERVER_HOST = '127.0.0.1'   # Listen on localhost
SERVER_PORT = 1145          # Port to listen on
DOCUMENT_ROOT = './htdocs'  # Root directory for web files
LOG_FILE = 'server.log'     # Log file name
MAX_REQUEST_SIZE = 8192     # Max bytes to read per request
KEEP_ALIVE_TIMEOUT = 10     # Seconds to wait for next request on persistent connection
# -------------------------------------------------------

# Set up logging to both file and console according to the specified format
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
# Create WebServer.log for recording
logger = logging.getLogger('WebServer')

class HTTPRequest:
    """Parse and store HTTP request components."""
    def __init__(self, raw_data):
        self.raw = raw_data
        self.method = None
        self.path = None
        self.version = None
        self.headers = {}
        self.body = None
        self._parse()

    def _parse(self):
        # Split raw request into lines
        lines = self.raw.split('\r\n')
        if not lines:
            return
        # Parse request line (first line)
        request_line = lines[0].split()
        if len(request_line) >= 3:
            self.method = request_line[0]
            self.path = request_line[1]
            self.version = request_line[2]
        # Parse headers (lines after first line)
        for line in lines[1:]:
            if line == '':
                break
            if ':' in line:
                key, value = line.split(':', 1)
                self.headers[key.strip().lower()] = value.strip()

class HTTPResponse:
    """Build HTTP response."""
    # Default messages for common status codes
    def __init__(self, status_code=200, status_message='OK'):
        self.status_code = status_code
        self.status_message = status_message
        self.headers = {
            'Server': 'Comp2322-WebServer/1.0',
            'Date': formatdate(time.time(), usegmt=True),
            'Connection': 'close'   # default non-persistent
        }
        self.body = b''

    def set_body(self, data):
        # Set response body and update Content-Length header
        if isinstance(data, str):
            self.body = data.encode()
        else:
            self.body = data
        self.headers['Content-Length'] = str(len(self.body))

    def set_connection(self, keep_alive):
        # Set Connection header based on keep-alive preference
        self.headers['Connection'] = 'keep-alive' if keep_alive else 'close'

    def to_bytes(self):
        # Construct the full response as bytes according to HTTP format
        response_line = f"HTTP/1.1 {self.status_code} {self.status_message}\r\n"
        header_lines = "\r\n".join([f"{k}: {v}" for k, v in self.headers.items()])
        return response_line.encode() + header_lines.encode() + b'\r\n\r\n' + self.body

# Associated utility functions
def get_mime_type(filepath):
    """Guess MIME type based on file extension."""
    mime_type, _ = mimetypes.guess_type(filepath)
    return mime_type or 'application/octet-stream'

def get_file_last_modified(filepath):
    """Return Last-Modified header value for a file."""
    try:
        mtime = os.path.getmtime(filepath)
        return formatdate(mtime, usegmt=True)
    except OSError:
        return None

# Main function to handle client connections in a separate thread
def handle_client(conn_socket, client_addr):
    """Thread target: handle one or more requests on a connection."""
    keep_alive = True
    conn_socket.settimeout(KEEP_ALIVE_TIMEOUT)

    while keep_alive:
        try:
            # Receive request data
            request_data = b''
            while True:
                part = conn_socket.recv(MAX_REQUEST_SIZE)
                if not part:
                    break
                request_data += part
                if b'\r\n\r\n' in request_data:
                    break
            if not request_data:
                break

            # Parse request
            try:
                req = HTTPRequest(request_data.decode('utf-8', errors='replace'))
            except Exception as e:
                logger.error(f"Failed to parse request: {e}")
                break

            # Build response to handle long-term connection requests
            response = HTTPResponse()
            keep_alive_requested = req.headers.get('connection', '').lower() == 'keep-alive'
            response.set_connection(keep_alive_requested)

            # Validate method
            if req.method not in ('GET', 'HEAD'):
                response.status_code = 400
                response.status_message = 'Bad Request'
                response.set_body('<h1>400 Bad Request</h1><p>Method not supported.</p>')
                response.headers['Content-Type'] = 'text/html'
                conn_socket.sendall(response.to_bytes())
                logger.info(f"{client_addr[0]} - - [{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')}] {req.method} {req.path} {req.version} {response.status_code}")
                keep_alive = False
                break

            # Construct file path (prevent directory traversal)
            requested_path = req.path.split('?')[0]  # ignore query string
            if requested_path == '/':
                requested_path = '/index.html'
            filepath = os.path.normpath(DOCUMENT_ROOT + requested_path)
            # Ensure the requested file is within the document root
            abs_root = os.path.abspath(DOCUMENT_ROOT)
            abs_filepath = os.path.abspath(filepath)
            if not abs_filepath.startswith(abs_root + os.sep):
                response.status_code = 403
                response.status_message = 'Forbidden'
                response.set_body('<h1>403 Forbidden</h1><p>Access denied.</p>')
                response.headers['Content-Type'] = 'text/html'
                conn_socket.sendall(response.to_bytes())
                logger.info(f"{client_addr[0]} - - [{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')}] {req.method} {req.path} {req.version} {response.status_code}")
                keep_alive = False
                break

            # Check if file exists
            if not os.path.exists(filepath):
                response.status_code = 404
                response.status_message = 'Not Found'
                response.set_body('<h1>404 Not Found</h1><p>The requested file was not found on this server.</p>')
                response.headers['Content-Type'] = 'text/html'
                conn_socket.sendall(response.to_bytes())
                logger.info(f"{client_addr[0]} - - [{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')}] {req.method} {req.path} {req.version} {response.status_code}")
                # Continue with keep-alive if client requested
                continue

            # Try to open file (handles PermissionError -> 403)
            try:
                with open(filepath, 'rb') as f:
                    file_content = f.read()
            except PermissionError:
                response.status_code = 403
                response.status_message = 'Forbidden'
                response.set_body('<h1>403 Forbidden</h1><p>You don\'t have permission to access this resource.</p>')
                response.headers['Content-Type'] = 'text/html'
                conn_socket.sendall(response.to_bytes())
                logger.info(f"{client_addr[0]} - - [{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')}] {req.method} {req.path} {req.version} {response.status_code}")
                continue

            # Handle Last-Modified and If-Modified-Since
            last_modified = get_file_last_modified(filepath)
            if last_modified:
                response.headers['Last-Modified'] = last_modified
                if_modified_since = req.headers.get('if-modified-since')
                if if_modified_since:
                    try:
                        ims_time = parsedate_to_datetime(if_modified_since)
                        lm_time = parsedate_to_datetime(last_modified)
                        if lm_time <= ims_time:
                            response.status_code = 304
                            response.status_message = 'Not Modified'
                            response.set_body('')
                            conn_socket.sendall(response.to_bytes())
                            logger.info(f"{client_addr[0]} - - [{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')}] {req.method} {req.path} {req.version} {response.status_code}")
                            continue
                    except Exception:
                        pass  # Invalid date header, ignore

            # Success response
            response.status_code = 200
            response.status_message = 'OK'
            response.headers['Content-Type'] = get_mime_type(filepath)

            if req.method == 'GET':
                response.set_body(file_content)
            else:  # HEAD
                response.headers['Content-Length'] = str(len(file_content))
                response.body = b''

            conn_socket.sendall(response.to_bytes())
            logger.info(f"{client_addr[0]} - - [{datetime.now().strftime('%d/%b/%Y:%H:%M:%S %z')}] {req.method} {req.path} {req.version} {response.status_code}")

            # If non-persistent, break after one request
            if not keep_alive_requested:
                keep_alive = False

        except socket.timeout:
            # Timeout waiting for next request, close connection
            break
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            break

    conn_socket.close()

# Start function to initialize and run the multi-threaded server
def start_server():
    """Initialize and run the multi-threaded server."""
    # Ensure document root exists
    if not os.path.exists(DOCUMENT_ROOT):
        os.makedirs(DOCUMENT_ROOT)
        print(f"Created document root directory: {os.path.abspath(DOCUMENT_ROOT)}")
        print("Please place your web files (index.html, etc.) into this folder.")
    else:
        print(f"Document root directory already exists: {os.path.abspath(DOCUMENT_ROOT)}")

    # Create server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(10)  # queue up to 10 connections
    server_socket.settimeout(1.0)  # Timeout per second to allow graceful shutdown

    # Print server startup information
    print(f"Multi-threaded Web Server started on {SERVER_HOST}:{SERVER_PORT}")
    print(f"Serving files from: {os.path.abspath(DOCUMENT_ROOT)}")
    print(f"Log file: {LOG_FILE}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                conn_socket, client_addr = server_socket.accept()
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                break
            
            # Create a new thread for each client connection
            client_thread = threading.Thread(target=handle_client, args=(conn_socket, client_addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server_socket.close()
        print("Server stopped.")

if __name__ == '__main__':
    start_server()