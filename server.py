#!/usr/bin/env python3
"""
Simple HTTP Server implementation
@author: Grazia Bochdanovits de Kavna
@email: grazia.bochdanovits@studio.unibo.it
@studentID: 0001117082
"""
import socket
import os
import mimetypes
import threading
import logging
from datetime import datetime
from urllib.parse import unquote, urlparse
from typing import Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('server.log'), logging.StreamHandler()]
)

class HTTPServer:
    """Simple HTTP server that serves static files"""
    
    STATUS_CODES = {
        200: "OK", 400: "Bad Request", 403: "Forbidden", 
        404: "Not Found", 405: "Method Not Allowed", 
        500: "Internal Server Error", 501: "Not Implemented"
    }
    
    def __init__(self, host='localhost', port=8080, www_dir='www'):
        self.host, self.port, self.www_dir = host, port, os.path.abspath(www_dir)
        self.socket, self.running = None, False
        self.logger = logging.getLogger(__name__)
        
        if not os.path.isdir(self.www_dir):
            raise ValueError(f"Web directory '{www_dir}' does not exist")
        
        mimetypes.init()
        mimetypes.add_type('text/css', '.css')
        
    def start(self):
        """Start the server"""
        try:
            self._setup_socket()
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.logger.info(f"Server started on http://{self.host}:{self.port}")
            self._run_server_loop()
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise
        finally:
            self._cleanup()
    
    def _setup_socket(self):
        """Configure the server socket"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1.0)
    
    def _run_server_loop(self):
        """Main server loop"""
        self.running = True
        while self.running:
            try:
                client_socket, client_address = self.socket.accept()
                thread = threading.Thread(
                    target=self._handle_client, 
                    args=(client_socket, client_address),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                self.logger.info("Shutting down...")
                break
            except Exception as e:
                if self.running:
                    self.logger.error(f"Accept error: {e}")
                break
    
    def _handle_client(self, client_socket, client_address):
        """Handle client connection"""
        try:
            client_socket.settimeout(10.0)
            request_data = client_socket.recv(4096).decode('utf-8')
            
            if request_data:
                self._log_request(client_address, request_data)
                self._process_request(client_socket, request_data)
                
        except Exception as e:
            self.logger.error(f"Client {client_address} error: {e}")
            self._send_error(client_socket, 500)
        finally:
            self._close_socket(client_socket)
    
    def _process_request(self, client_socket, request_data):
        """Parse and process HTTP request"""
        lines = request_data.split('\n')
        if not lines or not lines[0].strip():
            return self._send_error(client_socket, 400)
            
        parts = lines[0].strip().split()
        if len(parts) != 3:
            return self._send_error(client_socket, 400)
            
        method, path, version = parts
        
        if method != 'GET':
            return self._send_error(client_socket, 405)
        if not version.startswith('HTTP/1.'):
            return self._send_error(client_socket, 400)
            
        self._handle_get(client_socket, path)
    
    def _handle_get(self, client_socket, path):
        """Handle GET request"""
        file_path = self._resolve_path(path)
        
        if not file_path:
            return self._send_error(client_socket, 403)
            
        if os.path.isdir(file_path):
            index_path = os.path.join(file_path, 'index.html')
            if os.path.isfile(index_path):
                file_path = index_path
            else:
                return self._send_error(client_socket, 403)
        
        if not os.path.isfile(file_path):
            return self._send_error(client_socket, 404)
            
        # Check for unsupported file types (501 example)
        if file_path.lower().endswith(('.php', '.jsp', '.asp')):
            return self._send_error(client_socket, 501)
            
        self._serve_file(client_socket, file_path)
    
    def _resolve_path(self, url_path):
        """Convert URL path to safe filesystem path"""
        try:
            path = unquote(urlparse(url_path).path)
            path = os.path.normpath(path)
            
            if path in ('/', '.'):
                path = '/index.html'
            if path.startswith('/'):
                path = path[1:]
                
            full_path = os.path.join(self.www_dir, path)
            
            # Security check
            if os.path.abspath(full_path).startswith(self.www_dir):
                return full_path
                
        except Exception as e:
            self.logger.warning(f"Path resolution error: {e}")
        return None
    
    def _serve_file(self, client_socket, file_path):
        """Serve a static file"""
        try:
            file_size = os.path.getsize(file_path)
            mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

            headers = (
                f"HTTP/1.1 200 OK\r\n"
                f"Date: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
                f"Server: SimpleHTTPServer/1.0\r\n"
                f"Content-Type: {mime_type}\r\n"
                f"Content-Length: {file_size}\r\n"
                f"Connection: close\r\n\r\n"
            )
            client_socket.send(headers.encode('utf-8'))

            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    client_socket.send(chunk)
                
        except FileNotFoundError:
            self._send_error(client_socket, 404)
        except PermissionError:
            self._send_error(client_socket, 403)
        except Exception as e:
            self.logger.error(f"File serve error: {e}")
            self._send_error(client_socket, 500)
    
    def _send_response(self, client_socket, status_code, content, content_type):
        """Send HTTP response"""
        status_text = self.STATUS_CODES[status_code]
        headers = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Date: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
            f"Server: SimpleHTTPServer/1.0\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(content)}\r\n"
            f"Connection: close\r\n\r\n"
        )
        
        client_socket.send(headers.encode('utf-8'))
        client_socket.send(content)
    
    def _send_error(self, client_socket, status_code):
        """Send error response"""
        try:
            content = self._get_error_content(status_code)
            self._send_response(client_socket, status_code, content.encode('utf-8'), 'text/html; charset=utf-8')
        except Exception:
            pass  # Client disconnected
    
    def _get_error_content(self, status_code):
        """Get error page content"""
        # Try custom error page first
        error_file = os.path.join(self.www_dir, f"{status_code}.html")
        if os.path.isfile(error_file):
            try:
                with open(error_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                pass
        
        # Default error page
        status_text = self.STATUS_CODES.get(status_code, "Error")
        return f"""<!DOCTYPE html>
            <html><head><title>{status_code} {status_text}</title></head>
            <body style="font-family:Arial;text-align:center;margin-top:100px;">
            <h1 style="color:#e74c3c;">{status_code}</h1>
            <h2>{status_text}</h2>
            <a href="/" style="color:#3498db;">Return to homepage</a>
            </body></html>"""
    
    def _log_request(self, client_address, request):
        """Log client request"""
        try:
            request_line = request.split('\n')[0].strip()
            self.logger.info(f"{client_address[0]}:{client_address[1]} - {request_line}")
        except Exception:
            pass
    
    def _close_socket(self, sock):
        """Safely close socket"""
        try:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except Exception:
            pass
    
    def _cleanup(self):
        """Cleanup server resources"""
        self.running = False
        if self.socket:
            self._close_socket(self.socket)
        self.logger.info("Server stopped")
    
    def stop(self):
        """Stop the server"""
        self.running = False


def main():
    """Start the HTTP server"""
    if not os.path.exists('www'):
        print("ERROR: 'www' directory does not exist!")
        return
    
    server = HTTPServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

if __name__ == "__main__":
    main()
