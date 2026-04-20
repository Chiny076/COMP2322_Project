# Comp2322 Multi-threaded Web Server

## Notice
- Please change secret.html access permission attributes to test `403 Forbidden` through permission error.

## Overview
This project implements a multi-threaded HTTP/1.1 web server in Python using low-level socket programming. It fulfills all requirements of the Comp2322 Computer Networking project.

## Features
- **Multi-threading**: Each client connection is handled in a separate thread.
- **HTTP Methods**: Supports `GET` and `HEAD`.
- **File Types**: Serves both text (HTML, TXT) and image (JPEG, PNG, GIF) files with correct MIME types.
- **Status Codes**: Returns exactly five status codes:
  - `200 OK`
  - `400 Bad Request`
  - `403 Forbidden`
  - `404 Not Found`
  - `304 Not Modified`
- **Caching Headers**:
  - Sends `Last-Modified` header.
  - Honors `If-Modified-Since` to return `304 Not Modified` when appropriate.
- **Connection Handling**:
  - Supports `Connection: close` (non-persistent).
  - Supports `Connection: keep-alive` (persistent) with a timeout.
- **Logging**: Writes a standard Apache-style log to `server.log` and also outputs to console.
- **Security**: Prevents directory traversal attacks (403 response).

## Requirements
- Python 3.6 or higher.
- No external libraries needed (uses only standard library modules).

## How to Run
1. Place the server script `MultiThreadedWebServer.py` in your project directory.
2. Ensure a subdirectory named `htdocs` exists (or it will be created automatically with sample files).
3. Run the server:
   ```bash
   python MultiThreadedWebServer.py
