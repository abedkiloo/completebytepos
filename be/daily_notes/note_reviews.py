"""
Ask a colleague to review a finished daily note.

A note holds 0–5 reviewer rows. Tagging the same person again leaves one
row. The reviewer can leave a comment of 0–500 characters.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from daily_notes.models import DailyNote, DailyNoteReview


def _display(user) -> str:
    """Staff label for a review row. Never includes a phone number."""
    if user is None:
        return ''
    full = ''
    get_full_name = getattr(user, 'get_full_name', None)
    if callable(get_full_name):
        full = (get_full_name() or '').strip()
    return (full or getattr(user, 'username', '') or 'Staff')[:120]


@transaction.atomic
def request_note_reviews(*, note: DailyNote, reviewer_ids, requested_by) -> list[DailyNoteReview]:
    """
    Tag 1–5 colleagues to look at a finished note.

    Args:
        note: Completed ``DailyNote``. An open note is rejected.
        reviewer_ids: Active user ids, 1–5 unique values, each 1–2^31-1.
            The person who finished the note cannot tag themselves.
        requested_by: User asking for the review.

    Returns:
        The note's review rows after the request, 1–5, oldest first.

    Raises:
        ValidationError: Note is not done, the list is empty or longer
            than 5, a user is missing or inactive, or the author tagged
            themselves.
    """
    if not note.is_done:
        raise ValidationError('Mark the note done before asking someone to review it.')
    if requested_by is None:
        raise ValidationError('Choose who is asking for the review.')

    raw_ids = []
    for value in list(reviewer_ids or []):
        try:
            raw_ids.append(int(value))
        except (TypeError, ValueError):
            raise ValidationError('Choose a staff member to review this note.')
    unique_ids = []
    for pk in raw_ids:
        if pk < 1:
            raise ValidationError('Choose a staff member to review this note.')
        if pk not in unique_ids:
            unique_ids.append(pk)
    if not unique_ids:
        raise ValidationError('Choose someone to review this note.')
    if len(unique_ids) > 5:
        raise ValidationError('You can ask up to 5 people to review one note.')
    if int(requested_by.pk) in unique_ids:
        raise ValidationError('Choose someone else to review this note.')

    existing = {
        row.reviewer_id: row
        for row in DailyNoteReview.objects.select_for_update().filter(daily_note=note)
    }
    newcomers = [pk for pk in unique_ids if pk not in existing]
    if len(existing) + len(newcomers) > 5:
        raise ValidationError('This note already has 5 people asked to review it.')

    users = {
        user.pk: user
        for user in User.objects.filter(pk__in=unique_ids, is_active=True)
    }
    if len(users) != len(unique_ids):
        raise ValidationError('Choose an active staff member.')

    for pk in unique_ids:
        row = existing.get(pk)
        if row is None:
            DailyNoteReview.objects.create(
                daily_note=note,
                reviewer=users[pk],
                requested_by=requested_by,
                status=DailyNoteReview.STATUS_PENDING,
            )
        elif row.status != DailyNoteReview.STATUS_PENDING:
            row.status = DailyNoteReview.STATUS_PENDING
            row.comment = ''
            row.reviewed_at = None
            row.requested_by = requested_by
            row.save(update_fields=['status', 'comment', 'reviewed_at', 'requested_by'])

    return list(note.reviews.select_related('reviewer', 'requested_by').order_by('id'))


@transaction.atomic
def complete_note_review(*, review: DailyNoteReview, comment: str = '') -> DailyNoteReview:
    """
    Mark one review done and store the reviewer's feedback.

    Args:
        review: Pending ``DailyNoteReview`` row.
        comment: Optional feedback, 0–500 characters. Blank is allowed.

    Returns:
        The same row, now ``reviewed``.

    Raises:
        ValidationError: The review was already finished, or the comment
            is longer than 500 characters.
    """
    if review.status == DailyNoteReview.STATUS_REVIEWED:
        raise ValidationError('This review is already finished.')
    text = (comment or '').strip()
    if len(text) > 500:
        raise ValidationError('Keep the feedback to 500 characters.')
    review.status = DailyNoteReview.STATUS_REVIEWED
    review.comment = text
    review.reviewed_at = timezone.now()
    review.save(update_fields=['status', 'comment', 'reviewed_at'])
    return review


def review_payload(review: DailyNoteReview) -> dict:
    """
    JSON-ready review row without phone numbers.

    Args:
        review: Saved row. Reviewer and requester should be loaded.

    Returns:
        Dict with ids, names, status, comment (0–500), and timestamps.
    """
    return {
        'id': review.id,
        'reviewer_id': review.reviewer_id,
        'reviewer_name': _display(review.reviewer),
        'requested_by_id': review.requested_by_id,
        'requested_by_name': _display(review.requested_by),
        'status': review.status,
        'comment': review.comment or '',
        'requested_at': review.requested_at.isoformat() if review.requested_at else None,
        'reviewed_at': review.reviewed_at.isoformat() if review.reviewed_at else None,
    }
