"""
Custom exception handler for DRF to add logging and ensure CORS headers
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that logs errors and ensures CORS headers are added
    """
    # Get the standard exception response
    response = exception_handler(exc, context)
    
    # Only log actual errors (not 4xx client errors in production)
    if response is not None and response.status_code >= 500:
        logger.error(f"DRF Exception: {type(exc).__name__}: {exc}", exc_info=True)
        logger.error(f"Response: {response.status_code} - {response.data}")
    
    # Ensure CORS headers are added to error responses
    # The CORS middleware should handle this, but we ensure it here as a fallback
    if response is not None:
        request = context.get('request')
        if request:
            origin = request.META.get('HTTP_ORIGIN')
            if origin:
                # Add CORS headers if not already present
                if 'Access-Control-Allow-Origin' not in response:
                    # Check if origin is allowed
                    if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
                        response['Access-Control-Allow-Origin'] = origin
                    elif origin in getattr(settings, 'CORS_ALLOWED_ORIGINS', []):
                        response['Access-Control-Allow-Origin'] = origin
                
                # Add other CORS headers if credentials are allowed
                if getattr(settings, 'CORS_ALLOW_CREDENTIALS', False):
                    if 'Access-Control-Allow-Credentials' not in response:
                        response['Access-Control-Allow-Credentials'] = 'true'
                
                # Add allowed methods
                if 'Access-Control-Allow-Methods' not in response:
                    methods = getattr(settings, 'CORS_ALLOW_METHODS', ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
                    response['Access-Control-Allow-Methods'] = ', '.join(methods)
                
                # Add allowed headers
                if 'Access-Control-Allow-Headers' not in response:
                    headers = getattr(settings, 'CORS_ALLOWED_HEADERS', [])
                    if isinstance(headers, list):
                        response['Access-Control-Allow-Headers'] = ', '.join(headers)
    
    return response

