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


class HTTPServer:
    """Simple HTTP server that serves static files"""
    
    def __init__(self, host='localhost', port=8080, www_dir='www'):
        """Initialize the HTTP server with host, port and web directory"""
        self.host = host
        self.port = port
        self.www_dir = os.path.abspath(www_dir)
        self.socket = None
        self.running = False

        mimetypes.init()
        mimetypes.add_type('text/css', '.css')
        
    def start(self):
        """Start the server and begin listening for connections"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # Bind to the specified host and port
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            print(f"Server started on http://{self.host}:{self.port}")

            # Set timeout to allow for graceful shutdown
            self.socket.settimeout(1)

            # Main server loop
            self.running = True
            while self.running:
                try:
                    # Accept incoming connection
                    client_socket, client_address = self.socket.accept()
                    
                    # Handle client in a separate thread
                    thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, client_address)
                    )
                    thread.daemon = True
                    thread.start()
                    
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    self.running = False
                    break
                except Exception as e:
                    if self.running:
                        print(f"Error accepting connection: {e}")
                    break

        except Exception as e: 
            print(f"Server error: {e}") 
        finally: 
            # Clean up socket
            if self.socket: 
                self.socket.close()
            print("Server stopped.")
    
    def stop(self):
        """Stop the server"""
        self.running = False
    
    def handle_client(self, client_socket, client_address):
        """Handle a single client request"""
        try:
            # Receive and decode request data
            request_data = client_socket.recv(1024).decode('utf-8')
            if not request_data:
                return
                
            # Log the request
            self.log_request(client_address, request_data)
            
            # Parse request line
            lines = request_data.split('\n')
            if not lines:
                return
                
            request_line = lines[0].strip()
            if not request_line:
                return
                
            # Split request into method, path, and protocol version
            parts = request_line.split()
            if len(parts) < 2:
                self.send_error(client_socket, 400, "Bad Request")
                return
                
            method, path = parts[0], parts[1]

            if method != 'GET':
                self.send_error(client_socket, 405, "Method Not Allowed")
                return

            self.handle_get_request(client_socket, path)
            
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
            try:
                self.send_error(client_socket, 500, "Internal Server Error")
            except:
                pass  # Client may have disconnected
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def handle_get_request(self, client_socket, path):
        """Handle GET requests by serving the appropriate file"""
        # Parse and decode URL path
        parsed_path = urlparse(path)
        path = unquote(parsed_path.path)

        # Default to index.html for root path
        if path == '/':
            path = '/index.html'

        # Remove leading slash for filesystem path
        if path.startswith('/'):
            path = path[1:]
            
        # Build full filesystem path
        file_path = os.path.join(self.www_dir, path)

        if not self.is_safe_path(file_path):
            self.send_error(client_socket, 403, "Forbidden")
            return

        if os.path.isdir(file_path):
            file_path = os.path.join(file_path, 'index.html')

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(client_socket, 404, "File Not Found")
            return

        self.serve_file(client_socket, file_path)
    
    def is_safe_path(self, path):
        """Check if the requested path is within the allowed directory"""
        requested_path = os.path.abspath(path)
        return requested_path.startswith(self.www_dir)
    
    def serve_file(self, client_socket, file_path):
        """Serve a static file with appropriate headers"""
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            with open(file_path, 'rb') as f:
                content = f.read()

            # Build response headers
            response_headers = [
                "HTTP/1.1 200 OK",
                f"Content-Type: {mime_type}",
                f"Content-Length: {len(content)}",
                "Connection: close",
                "\r\n"
            ]
            
            # Send headers and content
            client_socket.send("\r\n".join(response_headers).encode('utf-8'))
            client_socket.send(content)
            
        except IOError as e:
            print(f"Error reading file {file_path}: {e}")
            self.send_error(client_socket, 500, "Internal Server Error")
        except Exception as e:
            print(f"Error sending file {file_path}: {e}")
            self.send_error(client_socket, 500, "Internal Server Error")
    
    def send_error(self, client_socket, status_code, status_text):
        """Send an HTTP error response"""
        # Predefined error pages
        error_pages = {
            404: self.get_404_page(),
            403: "<h1>403 Forbidden</h1><p>Access denied.</p>",
            405: "<h1>405 Method Not Allowed</h1><p>Method not supported.</p>",
            500: "<h1>500 Internal Server Error</h1><p>Internal server error.</p>",
            400: "<h1>400 Bad Request</h1><p>Malformed request.</p>"
        }
        
        # Get error page content or default
        content = error_pages.get(status_code, f"<h1>{status_code} {status_text}</h1>")
        content = content.encode('utf-8')
        
        # Build error response headers
        response_headers = [
            f"HTTP/1.1 {status_code} {status_text}",
            "Content-Type: text/html; charset=utf-8",
            f"Content-Length: {len(content)}",
            "Connection: close",
            "\r\n"
        ]
        
        try:
            # Send error response
            client_socket.send("\r\n".join(response_headers).encode('utf-8'))
            client_socket.send(content)
        except:
            pass  # Client may have disconnected
    
    def get_404_page(self):
        """Load custom 404 error page from www/404.html"""
        error_file = os.path.join(self.www_dir, "404.html")
        with open(error_file, 'r', encoding='utf-8') as f:
            return f.read()

    def log_request(self, client_address, request):
        """Log incoming requests"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        request_line = request.split('\n')[0].strip() if request else "Invalid request"
        print(f"[{timestamp}] {client_address[0]}:{client_address[1]} - {request_line}")


def main():
    """Main function to start the HTTP server"""
    if not os.path.exists('www'):
        print("ERROR: 'www' directory does not exist!")
        print("Create the 'www' directory and add HTML/CSS files")
        return
    
    # Create and start server
    server = HTTPServer(host='localhost', port=8080, www_dir='www')
    
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

if __name__ == "__main__":
    main()
