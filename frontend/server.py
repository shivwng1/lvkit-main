#!/usr/bin/env python3
"""
Simple HTTP server for the Voice AI Assistant frontend
Provides token generation and configuration endpoints for LiveKit integration
"""

import os
import sys
import json
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import time
from datetime import datetime, timedelta

# Add UV virtual environment to Python path
venv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.venv', 'lib', 'python3.13', 'site-packages')
if os.path.exists(venv_path):
    sys.path.insert(0, venv_path)

import jwt
from livekit import api

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceAssistantHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for the Voice AI Assistant frontend"""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        super().__init__(*args, directory=".", **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/config':
            self.send_config()
        elif parsed_path.path == '/health':
            self.send_health()
        else:
            # Serve static files
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/token':
            self.generate_token()
        else:
            self.send_error(404, "Not Found")
    
    def send_config(self):
        """Send configuration data to the frontend"""
        config = {
            'livekit_url': os.getenv('LIVEKIT_URL', 'ws://localhost:7880'),
            'room_name': os.getenv('ROOM_NAME', 'debt-collection-room'),
            'participant_name': 'web-client'
        }
        
        self.send_json_response(config)
        logger.info("Configuration sent to client")
    
    def send_health(self):
        """Health check endpoint"""
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'voice-assistant-frontend'
        }
        
        self.send_json_response(health)
    
    def generate_token(self):
        """Generate LiveKit access token"""
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            room_name = request_data.get('room_name', 'debt-collection-room')
            participant_name = request_data.get('participant_name', 'web-client')
            
            # Get LiveKit credentials from environment
            api_key = os.getenv('LIVEKIT_API_KEY')
            api_secret = os.getenv('LIVEKIT_API_SECRET')
            
            if not api_key or not api_secret:
                logger.error("LiveKit credentials not found in environment")
                self.send_error(500, "LiveKit credentials not configured")
                return
            
            # Generate JWT token
            token = self.create_livekit_token(
                api_key=api_key,
                api_secret=api_secret,
                room_name=room_name,
                participant_name=participant_name
            )
            
            response = {'token': token}
            self.send_json_response(response)
            
            logger.info(f"Token generated for room '{room_name}', participant '{participant_name}'")
            
        except Exception as e:
            logger.error(f"Token generation failed: {e}")
            self.send_error(500, f"Token generation failed: {str(e)}")
    
    def create_livekit_token(self, api_key: str, api_secret: str, room_name: str, participant_name: str) -> str:
        """Create a LiveKit access token using official SDK"""
        try:
            # Use LiveKit's official AccessToken class
            token = api.AccessToken(api_key, api_secret) \
                .with_identity(participant_name) \
                .with_name(participant_name) \
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    room_create=True,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                    can_update_own_metadata=True
                ))
            
            jwt_token = token.to_jwt()
            logger.info(f"Generated token for room '{room_name}', participant '{participant_name}'")
            return jwt_token
            
        except Exception as e:
            logger.error(f"Failed to create token with LiveKit SDK: {e}")
            # Fallback to manual JWT creation
            now = int(time.time())
            exp = now + (24 * 60 * 60)  # 24 hours
            
            payload = {
                'iss': api_key,
                'sub': participant_name,
                'iat': now,
                'exp': exp,
                'jti': f"{participant_name}-{now}",
                'room': room_name,
                'grants': {
                    'room': room_name,
                    'roomJoin': True,
                    'roomList': True,
                    'roomRecord': False,
                    'roomAdmin': True,
                    'roomCreate': True,
                    'ingress': False,
                    'hidden': False,
                    'recorder': False,
                    'canPublish': True,
                    'canSubscribe': True,
                    'canPublishData': True,
                    'canUpdateOwnMetadata': True
                }
            }
            
            token = jwt.encode(payload, api_secret, algorithm='HS256')
            return token
    
    def send_json_response(self, data):
        """Send JSON response"""
        response_body = json.dumps(data).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response_body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        self.wfile.write(response_body)
    
    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

def main():
    """Start the web server"""
    port = int(os.getenv('PORT', 8080))
    server_address = ('', port)
    
    # Change to frontend directory
    frontend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(frontend_dir)
    
    httpd = HTTPServer(server_address, VoiceAssistantHandler)
    
    logger.info(f"Voice AI Assistant frontend server starting on port {port}")
    logger.info(f"Serving files from: {frontend_dir}")
    logger.info(f"Access the application at: http://localhost:{port}")
    
    # Check for required environment variables
    required_vars = ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.warning("Token generation will fail without proper credentials")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        httpd.server_close()

if __name__ == '__main__':
    main()