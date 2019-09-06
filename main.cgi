#!/usr/bin/env python3
import os

def print_e(e):
    print("Content-type:text/html\r\n\r\n")
    print('<html>')
    print('<head>')
    print('</head>')
    print('<body>')
    
    print(f"<p> {e} </p>")
    
    print('</body>')
    print('</html>')
    print('</html>')
    exit()
try:
    from main import app
except Exception as e:
    print_e(e)

try:
    from wsgiref.handlers import CGIHandler
except Exception as e:
    print_e(e)
try:
    CGIHandler().run(app)
except Exception as e:
    print_e(e)
