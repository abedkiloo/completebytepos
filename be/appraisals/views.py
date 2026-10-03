from datetime import datetime

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import RequireAny, RequireModuleEnabled, RequirePerm

from .policy import PolicyError, load_template, public_policy, save_template
from .services import (
    decide_salary_increment,
    list_salary_increments,
    staff_snapshot,
    team_snapshots,
)


def _year_param(request) -> int | None:
    raw = request.query_params.get('year')
    if not raw:
        return None
    try:
        year = int(raw)
    except (TypeError, ValueError):
        return None
    if year < 2000 or year > 2100:
        return None
    return year


class AppraisalPolicyView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireModuleEnabled('appraisals'),
        RequirePerm('appraisals', 'view'),
    ]

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH'):
            return [
                IsAuthenticated(),
                RequireModuleEnabled('appraisals')(),
                RequirePerm('appraisals', 'manage')(),
            ]
        return [
            IsAuthenticated(),
            RequireModuleEnabled('appraisals')(),
            RequirePerm('appraisals', 'view')(),
        ]

    def get(self, request):
        return Response(public_policy())

    def put(self, request):
        return self._save(request)

    def patch(self, request):
        return self._save(request)

    def _save(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        current = load_template()
        current.update(payload)
        try:
            saved = save_template(current, user=request.user, request=request)
        except PolicyError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(saved)


class AppraisalMeView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireModuleEnabled('appraisals'),
        RequirePerm('appraisals', 'view'),
    ]

    def get(self, request):
        return Response(staff_snapshot(request.user, year=_year_param(request)))


class AppraisalTeamView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireModuleEnabled('appraisals'),
        RequireAny(
            RequirePerm('appraisals', 'view_all'),
            RequirePerm('appraisals', 'manage'),
        ),
    ]

    def get(self, request):
        return Response(team_snapshots(year=_year_param(request)))


class AppraisalIncrementListView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireModuleEnabled('appraisals'),
        RequireAny(
            RequirePerm('appraisals', 'view_all'),
            RequirePerm('appraisals', 'manage'),
        ),
    ]

    def get(self, request):
        return Response({'results': list_salary_increments(year=_year_param(request))})


class AppraisalIncrementDecideView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireModuleEnabled('appraisals'),
        RequirePerm('appraisals', 'manage'),
    ]

    def post(self, request, pk):
        payload = request.data if isinstance(request.data, dict) else {}
        approve = str(payload.get('decision') or 'approve').lower() != 'reject'
        reason = str(payload.get('reason') or '')[:500]
        raw_date = str(payload.get('effective_date') or '')[:10]
        effective = None
        if raw_date:
            try:
                effective = datetime.strptime(raw_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Effective date must be YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            saved = decide_salary_increment(
                pk,
                user=request.user,
                request=request,
                approve=approve,
                reason=reason,
                effective_date=effective,
            )
        except PolicyError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(saved)
