"""
Middleware to log CORS requests for debugging
"""
import logging
import sys

# Force logger to use console handler
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add console handler if not present
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[CORS] %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class CORSLoggingMiddleware:
    """
    Middleware to log CORS-related requests and responses
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Always log to ensure middleware is being called
        origin = request.META.get('HTTP_ORIGIN', 'No Origin')
        method = request.META.get('REQUEST_METHOD', 'Unknown')
        path = request.path
        
        # Log ALL requests to /api/accounts/auth/login/ for debugging
        if '/api/accounts/auth/login' in path:
            print("=" * 80, file=sys.stdout)
            print(f"[CORS MIDDLEWARE] Request to login endpoint", file=sys.stdout)
            print(f"Method: {method}", file=sys.stdout)
            print(f"Path: {path}", file=sys.stdout)
            print(f"Origin: {origin}", file=sys.stdout)
            print("=" * 80, file=sys.stdout)
            sys.stdout.flush()
        
        # Check if it's a CORS preflight request
        is_preflight = (
            method == 'OPTIONS' and
            'HTTP_ACCESS_CONTROL_REQUEST_METHOD' in request.META
        )
        
        # Log CORS-related requests
        if is_preflight or origin != 'No Origin' or '/api/accounts/auth/login' in path:
            print("=" * 80, file=sys.stdout)
            print("CORS REQUEST DETECTED", file=sys.stdout)
            print(f"Method: {method}", file=sys.stdout)
            print(f"Path: {path}", file=sys.stdout)
            print(f"Origin: {origin}", file=sys.stdout)
            print(f"Is Preflight: {is_preflight}", file=sys.stdout)
            
            if is_preflight:
                print(f"Access-Control-Request-Method: {request.META.get('HTTP_ACCESS_CONTROL_REQUEST_METHOD', 'N/A')}", file=sys.stdout)
                print(f"Access-Control-Request-Headers: {request.META.get('HTTP_ACCESS_CONTROL_REQUEST_HEADERS', 'N/A')}", file=sys.stdout)
            
            print(f"Query String: {request.META.get('QUERY_STRING', '')}", file=sys.stdout)
            print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'N/A')[:100]}", file=sys.stdout)
            sys.stdout.flush()
        
        response = self.get_response(request)
        
        # Log response details for CORS requests
        if is_preflight or origin != 'No Origin' or '/api/accounts/auth/login' in path:
            print("CORS RESPONSE", file=sys.stdout)
            print(f"Status Code: {response.status_code}", file=sys.stdout)
            
            # Log CORS headers in response
            cors_headers = {
                'Access-Control-Allow-Origin': response.get('Access-Control-Allow-Origin', 'Not Set'),
                'Access-Control-Allow-Methods': response.get('Access-Control-Allow-Methods', 'Not Set'),
                'Access-Control-Allow-Headers': response.get('Access-Control-Allow-Headers', 'Not Set'),
                'Access-Control-Allow-Credentials': response.get('Access-Control-Allow-Credentials', 'Not Set'),
                'Access-Control-Max-Age': response.get('Access-Control-Max-Age', 'Not Set'),
            }
            
            for header, value in cors_headers.items():
                print(f"  {header}: {value}", file=sys.stdout)
            
            print("=" * 80, file=sys.stdout)
            sys.stdout.flush()
        
        return response

