"""
Custom exception handler for DRF to add logging
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that logs errors
    """
    # Get the standard exception response
    response = exception_handler(exc, context)
    
    # Only log actual errors (not 4xx client errors in production)
    if response is not None and response.status_code >= 500:
        logger.error(f"DRF Exception: {type(exc).__name__}: {exc}", exc_info=True)
        logger.error(f"Response: {response.status_code} - {response.data}")
    
    return response

