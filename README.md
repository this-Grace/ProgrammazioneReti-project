# ProgrammazioneReti-project
This project consists of a multithreaded HTTP server written in Python that serves static files (HTML, CSS) from a local directory. The server includes error handling, request logging, and support for various MIME types.

### HTTP Server
- **Multithreading**: Concurrent connection handling
- **MIME Types Support**: HTML, CSS
- **Error Handling**: Custom error pages for 404, 501.
- **Logging**: Detailed request logging
- **Security**: Prevents directory traversal attacks

## Features

- **Python 3.x**: Socket programming, threading, os module
- **HTML5**: Semantic page structure
- **CSS3**: CSS variables, Flexbox, Media Queries, Gradients
- **Responsive Design**: Mobile-first approach

## How to Run the Server
1. **Clone the Repository**
```bash
git clone https://github.com/this-Grace/ProgrammazioneReti-project.git
```

2. **Run the server:**
```bash
python3 server.py
```

3. **Access the server** in your browser:
```bash
http://localhost:8080/www/index.html
```