from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePerm

from . import services

MESSAGING_CREATE = RequirePerm('messaging', 'create')


@api_view(['POST'])
@permission_classes([IsAuthenticated, MESSAGING_CREATE])
def debt_reminders(request):
    queued = services.queue_debt_reminders(created_by=request.user)
    return Response({
        'queued': len(queued),
        'ids': [m.id for m in queued],
    }, status=status.HTTP_201_CREATED)
