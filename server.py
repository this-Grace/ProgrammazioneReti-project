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
from datetime import datetime
from urllib.parse import unquote, urlparse
from typing import Optional, Tuple

class HTTPServer:
    """Simple HTTP server that serves static files"""
    def __init__(self, host: str = 'localhost', port: int = 8080, www_dir: str = 'www'):
        """Initialize the HTTP server with host, port and web directory"""
        self.host = host
        self.port = port
        self.www_dir = os.path.abspath(www_dir)
        self.socket: Optional[socket.socket] = None
        self.running = False

        self._initialize_mime_types()
        
    def _initialize_mime_types(self) -> None:
        """Initialize MIME type mappings"""
        mimetypes.init()
        mimetypes.add_type('text/css', '.css')
        
    def start(self) -> None:
        """Start the server and begin listening for connections"""
        self._setup_socket()
        
        try:
            self._bind_and_listen()
            print(f"Server started on http://{self.host}:{self.port}")
            self._run_server_loop()
            
        except Exception as e: 
            print(f"Server error: {e}") 
        finally: 
            self._cleanup()
    
    def _setup_socket(self) -> None:
        """Configure the server socket"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1)
    
    def _bind_and_listen(self) -> None:
        """Bind socket to address and start listening"""
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
    
    def _run_server_loop(self) -> None:
        """Main server loop to accept and handle connections"""
        self.running = True
        while self.running:
            try:
                client_socket, client_address = self.socket.accept()
                self._handle_client_in_thread(client_socket, client_address)
                
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
                break
    
    def _handle_client_in_thread(self, client_socket: socket.socket, 
                               client_address: Tuple[str, int]) -> None:
        """Handle client connection in a separate thread"""
        thread = threading.Thread(
            target=self.handle_client, 
            args=(client_socket, client_address)
        )
        thread.daemon = True
        thread.start()
    
    def stop(self) -> None:
        """Stop the server"""
        self.running = False
    
    def handle_client(self, client_socket: socket.socket, 
                     client_address: Tuple[str, int]) -> None:
        """Handle a single client request"""
        try:
            request_data = client_socket.recv(1024).decode('utf-8')
            if not request_data:
                return
                
            self.log_request(client_address, request_data)
            self._process_request(client_socket, request_data)
            
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
            self._send_error_safe(client_socket, 500, "Internal Server Error")
        finally:
            self._close_client_socket(client_socket)
    
    def _process_request(self, client_socket: socket.socket, request_data: str) -> None:
        """Parse and process the HTTP request"""
        request_line = request_data.split('\n')[0].strip()
        if not request_line:
            self.send_error(client_socket, 400, "Bad Request")
            return
            
        parts = request_line.split()
        if len(parts) < 2:
            self.send_error(client_socket, 400, "Bad Request")
            return
            
        method, path = parts[0], parts[1]

        if method != 'GET':
            self.send_error(client_socket, 405, "Method Not Allowed")
            return

        self.handle_get_request(client_socket, path)
    
    def handle_get_request(self, client_socket: socket.socket, path: str) -> None:
        """Handle GET requests by serving the appropriate file"""
        file_path = self._resolve_file_path(path)
        
        if file_path is None:
            self.send_error(client_socket, 403, "Forbidden")
            return
            
        if os.path.isdir(file_path):
            file_path = os.path.join(file_path, 'index.html')
            
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(client_socket, 404, "File Not Found")
            return

        self.serve_file(client_socket, file_path)
    
    def _resolve_file_path(self, url_path: str) -> Optional[str]:
        """Convert URL path to filesystem path with safety checks"""
        parsed_path = urlparse(url_path)
        path = unquote(parsed_path.path)

        # Default to index.html for root path
        if path == '/':
            path = '/index.html'

        # Remove leading slash for filesystem path
        if path.startswith('/'):
            path = path[1:]
            
        # Build full filesystem path
        file_path = os.path.join(self.www_dir, path)
        
        # Security check: prevent directory traversal
        if not self._is_safe_path(file_path):
            return None
            
        return file_path
    
    def _is_safe_path(self, path: str) -> bool:
        """Check if the requested path is within the allowed directory"""
        requested_path = os.path.abspath(path)
        return requested_path.startswith(self.www_dir)
    
    def serve_file(self, client_socket: socket.socket, file_path: str) -> None:
        """Serve a static file with appropriate headers"""
        try:
            content = self._read_file_content(file_path)
            mime_type = self._get_mime_type(file_path)
            
            headers = self._build_response_headers(200, "OK", mime_type, len(content))
            self._send_response(client_socket, headers, content)
            
        except IOError as e:
            print(f"Error reading file {file_path}: {e}")
            self.send_error(client_socket, 500, "Internal Server Error")
        except Exception as e:
            print(f"Error sending file {file_path}: {e}")
            self.send_error(client_socket, 500, "Internal Server Error")
    
    def _read_file_content(self, file_path: str) -> bytes:
        """Read file content as binary"""
        with open(file_path, 'rb') as f:
            return f.read()
    
    def _get_mime_type(self, file_path: str) -> str:
        """Determine MIME type for file"""
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'
    
    def _build_response_headers(self, status_code: int, status_text: str, 
                              content_type: str, content_length: int) -> list:
        """Build HTTP response headers"""
        return [
            f"HTTP/1.1 {status_code} {status_text}",
            f"Content-Type: {content_type}",
            f"Content-Length: {content_length}",
            "Connection: close",
            "\r\n"
        ]
    
    def _send_response(self, client_socket: socket.socket, headers: list, 
                      content: bytes) -> None:
        """Send HTTP response with headers and content"""
        header_data = "\r\n".join(headers).encode('utf-8')
        client_socket.send(header_data)
        client_socket.send(content)
    
    def send_error(self, client_socket: socket.socket, status_code: int, 
                  status_text: str) -> None:
        """Send an HTTP error response"""
        content = self._get_error_content(status_code).encode('utf-8')
        headers = self._build_response_headers(status_code, status_text, 
                                             "text/html; charset=utf-8", len(content))
        
        try:
            self._send_response(client_socket, headers, content)
        except:
            pass  # Client may have disconnected
    
    def _send_error_safe(self, client_socket: socket.socket, status_code: int,
                        status_text: str) -> None:
        """Safely send error response (handles client disconnection)"""
        try:
            self.send_error(client_socket, status_code, status_text)
        except:
            pass
    
    def _get_error_content(self, status_code: int) -> str:
        """Get error page content for given status code"""
        error_pages = {
            404: self._get_404_page(),
            403: "<h1>403 Forbidden</h1><p>Access denied.</p>",
            405: "<h1>405 Method Not Allowed</h1><p>Method not supported.</p>",
            500: "<h1>500 Internal Server Error</h1><p>Internal server error.</p>",
            400: "<h1>400 Bad Request</h1><p>Malformed request.</p>"
        }
        return error_pages.get(status_code, f"<h1>{status_code} Error</h1>")
    
    def _get_404_page(self) -> str:
        """Load custom 404 error page"""
        error_file = os.path.join(self.www_dir, "404.html")
        try:
            with open(error_file, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError:
            return self._get_default_404_page()
    
    def _get_default_404_page(self) -> str:
        """Get default 404 page content"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>404 Not Found</title></head>
        <body style="font-family: Arial; text-align: center; margin-top: 100px;">
            <h1>404 - Page Not Found</h1>
            <a href="/">Torna alla homepage</a>
        </body>
        </html>
        """
    
    def _close_client_socket(self, client_socket: socket.socket) -> None:
        """Safely close client socket"""
        try:
            client_socket.close()
        except:
            pass

    def log_request(self, client_address: Tuple[str, int], request: str) -> None:
        """Log incoming requests"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        request_line = request.split('\n')[0].strip() if request else "Invalid request"
        print(f"[{timestamp}] {client_address[0]}:{client_address[1]} - {request_line}")
    
    def _cleanup(self) -> None:
        """Clean up server resources"""
        if self.socket: 
            self.socket.close()
        print("Server stopped.")


def main() -> None:
    """Main function to start the HTTP server"""
    if not os.path.exists('www'):
        print("ERROR: 'www' directory does not exist!")
        return
    
    server = HTTPServer(host='localhost', port=8080, www_dir='www')
    
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

if __name__ == "__main__":
    main()
