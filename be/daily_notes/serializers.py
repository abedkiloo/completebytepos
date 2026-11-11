import json
import os

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Role
from .access import user_may_view_all_daily_notes
from .models import DailyNote, DailyNoteChecklistItem, DailyTask
from .services import (
    active_staff_users,
    carried_over_days,
    create_notes_for_assignees,
    users_with_role,
)
from utils.field_types import date_error_messages, raise_field_error, required_text_error


def attach_note_images(notes, uploaded_file) -> None:
    """
    Copy an optional uploaded image onto each created daily note.

    Fan-out creates many rows; each gets its own media file so deleting one
    note does not break siblings. Images are JPEG-compressed to ≤ 1.5 MiB.

    Args:
        notes: Iterable of saved ``DailyNote`` instances (1–500).
        uploaded_file: Django ``UploadedFile`` / file-like, or ``None``.

    Returns:
        None.

    Raises:
        ValidationError: When the upload is oversize, empty, or not an image.
    """
    if not uploaded_file or not notes:
        return
    from utils.image_upload import (
        GENERAL_MAX_INPUT_BYTES,
        TARGET_STORED_BYTES,
        prepare_uploaded_image,
    )

    prepared = prepare_uploaded_image(
        uploaded_file,
        field_name='image',
        max_input_bytes=GENERAL_MAX_INPUT_BYTES,
        target_bytes=TARGET_STORED_BYTES,
        label='Note photo',
        preferred_name=os.path.basename(getattr(uploaded_file, 'name', '') or 'note.jpg'),
    )
    if prepared is None:
        return
    raw = prepared.read()
    name = prepared.name or 'note.jpg'
    for note in notes:
        note.image.save(name, ContentFile(raw), save=True)


def _parse_multipart_payload(data):
    """
    Normalize multipart/form-data into a plain dict for ModelSerializer.

    Checklist rows may arrive as a JSON string; file fields stay as uploads.

    Args:
        data: Request data (``QueryDict`` or mapping).

    Returns:
        dict suitable for ``super().to_internal_value``.

    Raises:
        serializers.ValidationError: When ``checklist_items`` JSON is invalid.
    """
    if hasattr(data, 'lists'):
        mutable = {}
        for key, values in data.lists():
            if key == 'checklist_items' and len(values) == 1 and isinstance(values[0], str):
                raw = values[0].strip()
                if not raw:
                    mutable[key] = []
                    continue
                try:
                    mutable[key] = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise serializers.ValidationError(
                        {'checklist_items': 'Invalid checklist JSON.'}
                    ) from exc
            elif len(values) == 1:
                mutable[key] = values[0]
            else:
                mutable[key] = values
        return _nullify_empty_fk(mutable)

    mutable = dict(data)
    items = mutable.get('checklist_items')
    if isinstance(items, str):
        raw = items.strip()
        if not raw:
            mutable['checklist_items'] = []
        else:
            try:
                mutable['checklist_items'] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError(
                    {'checklist_items': 'Invalid checklist JSON.'}
                ) from exc
    return _nullify_empty_fk(mutable)


def _nullify_empty_fk(mutable: dict) -> dict:
    """Turn empty multipart FK strings into ``None`` for nullable relations."""
    for key in ('assigned_to', 'assigned_role'):
        if mutable.get(key) == '':
            mutable[key] = None
    return mutable


def _author_display(user) -> str:
    if user is None:
        return ''
    first = user.first_name or ''
    last = user.last_name or ''
    name = f'{first} {last}'.strip()
    return name or user.username


def replace_note_checklist(note: DailyNote, items: list | None) -> None:
    """Replace checklist rows for a note. Empty/None clears optional checklist."""
    note.checklist_items.all().delete()
    if not items:
        return
    rows = []
    for index, raw in enumerate(items):
        if isinstance(raw, DailyNoteChecklistItem):
            label = (raw.label or '').strip()
            is_done = bool(raw.is_done)
            sort_order = raw.sort_order if raw.sort_order is not None else index
        else:
            label = (raw.get('label') or '').strip()
            is_done = bool(raw.get('is_done'))
            sort_order = raw.get('sort_order')
            if sort_order is None:
                sort_order = index
        if not label:
            continue
        item = DailyNoteChecklistItem(
            daily_note=note,
            label=label[:200],
            sort_order=int(sort_order),
        )
        if is_done:
            item.mark_done(done=True, at=timezone.now())
        rows.append(item)
    if rows:
        DailyNoteChecklistItem.objects.bulk_create(rows)


class DailyNoteChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyNoteChecklistItem
        fields = [
            'id',
            'label',
            'is_done',
            'completed_at',
            'sort_order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['completed_at', 'created_at', 'updated_at']

    def validate_label(self, value):
        raise_field_error(
            required_text_error(
                value, label='checklist item', example='Count till at close', min_length=1
            )
        )
        return value.strip()


class DailyNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='author.username', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_username = serializers.SerializerMethodField()
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    assigned_role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    assigned_role_name = serializers.SerializerMethodField()
    created_count = serializers.SerializerMethodField()
    days_carried_over = serializers.SerializerMethodField()
    assign_to_all = serializers.BooleanField(write_only=True, required=False, default=False)
    board_column = serializers.ChoiceField(
        choices=['todo', 'doing', 'past'],
        required=False,
        write_only=True,
    )
    checklist_items = DailyNoteChecklistItemSerializer(many=True, required=False)
    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = DailyNote
        fields = [
            'id',
            'note_date',
            'title',
            'content',
            'priority',
            'is_sticky',
            'in_progress',
            'board_column',
            'is_done',
            'completed_at',
            'author',
            'author_name',
            'author_username',
            'assigned_to',
            'assigned_to_name',
            'assigned_to_username',
            'assigned_role',
            'assigned_role_name',
            'assign_to_all',
            'assignment_group',
            'created_count',
            'days_carried_over',
            'checklist_items',
            'image',
            'image_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'author',
            'completed_at',
            'assignment_group',
            'days_carried_over',
            'image_url',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'note_date': {'error_messages': date_error_messages(label='note date')},
        }

    def to_internal_value(self, data):
        return super().to_internal_value(_parse_multipart_payload(data))

    def get_image_url(self, obj):
        """
        Absolute media URL for the optional note photo.

        Args:
            obj: ``DailyNote`` instance.

        Returns:
            str URL or ``None`` when no image is attached.
        """
        image = getattr(obj, 'image', None)
        if not image:
            return None
        try:
            relative = image.url
        except (ValueError, AttributeError, OSError):
            return None
        from config.media_urls import absolute_media_url

        return absolute_media_url(self.context.get('request'), relative)

    def validate_content(self, value):
        raise_field_error(
            required_text_error(
                value, label='note', example='Stock count completed at close of day', min_length=1
            )
        )
        return value.strip()

    def get_author_name(self, obj):
        return _author_display(obj.author)

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to_id:
            return ''
        return _author_display(obj.assigned_to)

    def get_assigned_to_username(self, obj):
        if not obj.assigned_to_id:
            return ''
        return obj.assigned_to.username

    def get_assigned_role_name(self, obj):
        role = getattr(obj, 'assigned_role', None)
        return role.name if role is not None else ''

    def get_created_count(self, obj):
        return getattr(self, '_created_count', 1)

    def get_days_carried_over(self, obj):
        return carried_over_days(
            origin=getattr(obj, 'note_date', None),
            as_of=self.context.get('as_of_date'),
            is_done=bool(getattr(obj, 'is_done', False)),
        )

    def validate(self, attrs):
        request = self.context.get('request')
        is_sticky = attrs.get('is_sticky')
        if is_sticky is None and self.instance:
            is_sticky = self.instance.is_sticky
        is_sticky = bool(is_sticky)

        assigned_to = attrs.get('assigned_to', serializers.empty)
        if assigned_to is serializers.empty:
            assigned_to = self.instance.assigned_to if self.instance else None

        assigned_role = attrs.get('assigned_role', serializers.empty)
        if assigned_role is serializers.empty:
            assigned_role = self.instance.assigned_role if self.instance else None

        assign_to_all = bool(attrs.get('assign_to_all'))
        if assign_to_all and self.instance:
            attrs.pop('assign_to_all', None)
            assign_to_all = False

        if assigned_to and assigned_role and not self.instance:
            raise serializers.ValidationError(
                {'assigned_role': 'Choose a person or a role, not both.'}
            )

        may_assign_others = bool(
            request and user_may_view_all_daily_notes(getattr(request, 'user', None))
        )

        if assign_to_all:
            if assigned_to or assigned_role:
                raise serializers.ValidationError(
                    {
                        'assign_to_all': (
                            'Choose everyone, a person, or a role — not more than one.'
                        )
                    }
                )
            if not may_assign_others:
                raise serializers.ValidationError(
                    {'assign_to_all': 'You can only assign notes to yourself.'}
                )
            if not active_staff_users():
                raise serializers.ValidationError(
                    {'assign_to_all': 'No active staff to send this note to.'}
                )

        if assigned_role and not may_assign_others:
            raise serializers.ValidationError(
                {'assigned_role': 'You can only assign notes to yourself.'}
            )

        if assigned_role and assigned_to is None and not self.instance:
            if not users_with_role(assigned_role):
                raise serializers.ValidationError(
                    {'assigned_role': 'No active staff have that role.'}
                )

        if (
            is_sticky
            and assigned_to is None
            and assigned_role is None
            and not assign_to_all
            and request
            and getattr(request, 'user', None)
            and not may_assign_others
        ):
            assigned_to = request.user
            attrs['assigned_to'] = assigned_to

        if is_sticky and assigned_to is None and assigned_role is None and not assign_to_all:
            raise serializers.ValidationError(
                {
                    'assigned_to': (
                        'Assign this note to a person, a role, or everyone.'
                        if may_assign_others
                        else 'Assign this note to the person who must resolve it.'
                    )
                }
            )

        if request and assigned_to and assigned_to.id != request.user.id:
            if not may_assign_others:
                raise serializers.ValidationError(
                    {'assigned_to': 'You can only assign notes to yourself.'}
                )

        is_done = attrs.get('is_done')
        if is_done is None and self.instance:
            is_done = self.instance.is_done
        if is_done and not (attrs.get('content') or (self.instance and self.instance.content)):
            raise serializers.ValidationError({'content': 'Write the note before ticking it.'})
        return attrs

    def _apply_completion(self, instance, is_done: bool):
        if is_done and not instance.is_done:
            instance.mark_done(done=True, at=timezone.now())
        elif not is_done and instance.is_done:
            instance.mark_done(done=False)
        else:
            instance.is_done = is_done

    def create(self, validated_data):
        from daily_notes.models import PRIORITY_MEDIUM
        from daily_notes.module_settings import (
            daily_notes_checklists_enabled,
            daily_notes_priority_enabled,
            daily_notes_sticky_enabled,
        )

        is_done = validated_data.pop('is_done', False)
        board_column = validated_data.pop('board_column', None)
        in_progress = validated_data.pop('in_progress', False)
        assigned_to = validated_data.pop('assigned_to', None)
        assigned_role = validated_data.pop('assigned_role', None)
        assign_to_all = validated_data.pop('assign_to_all', False)
        checklist_items = validated_data.pop('checklist_items', None)
        image = validated_data.pop('image', None)
        if not daily_notes_priority_enabled():
            validated_data['priority'] = PRIORITY_MEDIUM
        if not daily_notes_sticky_enabled():
            validated_data['is_sticky'] = False
        if not daily_notes_checklists_enabled():
            checklist_items = None
        notes = create_notes_for_assignees(
            author=validated_data['author'],
            note_date=validated_data['note_date'],
            content=validated_data['content'],
            title=validated_data.get('title', ''),
            is_sticky=validated_data.get('is_sticky', False),
            is_done=is_done,
            in_progress=in_progress,
            priority=validated_data.get('priority'),
            assigned_to=assigned_to,
            assigned_role=assigned_role,
            assign_to_all=assign_to_all,
        )
        if not notes:
            raise serializers.ValidationError(
                {
                    'assign_to_all' if assign_to_all else 'assigned_role': (
                        'No active staff to send this note to.'
                        if assign_to_all
                        else 'No active staff have that role.'
                    )
                }
            )
        self._created_count = len(notes)
        note = notes[0]
        if board_column:
            note.move_to_board(board_column)
            note.save()
        if checklist_items is not None:
            for created_note in notes:
                replace_note_checklist(created_note, checklist_items)
        attach_note_images(notes, image)
        return note

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not getattr(self, '_created_count', None):
            data.pop('created_count', None)
        data['board_column'] = instance.board_column
        data['in_progress'] = bool(instance.in_progress)
        return data

    def update(self, instance, validated_data):
        from daily_notes.models import PRIORITY_MEDIUM
        from daily_notes.module_settings import (
            daily_notes_checklists_enabled,
            daily_notes_priority_enabled,
            daily_notes_sticky_enabled,
        )

        validated_data.pop('assign_to_all', None)
        board_column = validated_data.pop('board_column', None)
        is_done = validated_data.pop('is_done', None)
        assigned_to = validated_data.pop('assigned_to', serializers.empty)
        checklist_items = validated_data.pop('checklist_items', serializers.empty)
        if not daily_notes_priority_enabled():
            validated_data.pop('priority', None)
            instance.priority = PRIORITY_MEDIUM
        if not daily_notes_sticky_enabled() and 'is_sticky' in validated_data:
            validated_data['is_sticky'] = False
        if not daily_notes_checklists_enabled():
            checklist_items = serializers.empty
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if assigned_to is not serializers.empty:
            instance.assigned_to = assigned_to
        assigned_role = validated_data.get('assigned_role', serializers.empty)
        if assigned_role is not serializers.empty:
            instance.assigned_role = assigned_role
        if instance.is_sticky and instance.assigned_to_id is None and instance.assigned_role_id is None:
            instance.assigned_to = instance.author
        if board_column:
            instance.move_to_board(board_column)
        elif is_done is not None:
            self._apply_completion(instance, is_done)
        instance.save()
        if checklist_items is not serializers.empty:
            replace_note_checklist(instance, checklist_items)
        return instance


class DailyTaskSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='author.username', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    days_carried_over = serializers.SerializerMethodField()

    class Meta:
        model = DailyTask
        fields = [
            'id',
            'task_date',
            'title',
            'description',
            'priority',
            'is_done',
            'completed_at',
            'author',
            'author_name',
            'author_username',
            'assigned_to',
            'assigned_to_name',
            'assigned_to_username',
            'days_carried_over',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'author',
            'completed_at',
            'days_carried_over',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'task_date': {'error_messages': date_error_messages(label='task date')},
        }

    def validate_title(self, value):
        raise_field_error(
            required_text_error(
                value, label='task title', example='Restock sugar 2kg', min_length=1
            )
        )
        return value.strip()

    def get_author_name(self, obj):
        return _author_display(obj.author)

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to_id:
            return ''
        return _author_display(obj.assigned_to)

    def get_days_carried_over(self, obj):
        return carried_over_days(
            origin=getattr(obj, 'task_date', None),
            as_of=self.context.get('as_of_date'),
            is_done=bool(getattr(obj, 'is_done', False)),
        )

    def validate(self, attrs):
        is_done = attrs.get('is_done')
        if is_done is None and self.instance:
            is_done = self.instance.is_done
        if is_done and not (attrs.get('title') or (self.instance and self.instance.title)):
            raise serializers.ValidationError({'title': 'Title is required.'})

        request = self.context.get('request')
        assigned_to = attrs.get('assigned_to')
        if assigned_to is None and self.instance:
            assigned_to = self.instance.assigned_to

        if request and assigned_to and assigned_to.id != request.user.id:
            if not user_may_view_all_daily_notes(request.user):
                raise serializers.ValidationError(
                    {'assigned_to': 'You can only assign tasks to yourself.'}
                )

        return attrs

    def _apply_completion(self, instance, is_done: bool):
        if is_done and not instance.is_done:
            instance.mark_done(done=True, at=timezone.now())
        elif not is_done and instance.is_done:
            instance.mark_done(done=False)
        else:
            instance.is_done = is_done

    def create(self, validated_data):
        from daily_notes.models import PRIORITY_MEDIUM
        from daily_notes.module_settings import daily_notes_priority_enabled

        is_done = validated_data.pop('is_done', False)
        assigned_to = validated_data.pop('assigned_to', None)
        author = validated_data['author']
        if assigned_to is None:
            assigned_to = author
        if not daily_notes_priority_enabled():
            validated_data['priority'] = PRIORITY_MEDIUM
        instance = DailyTask(**validated_data, assigned_to=assigned_to)
        if is_done:
            instance.mark_done(done=True, at=timezone.now())
        else:
            instance.is_done = False
            instance.completed_at = None
        instance.save()
        return instance

    def update(self, instance, validated_data):
        from daily_notes.models import PRIORITY_MEDIUM
        from daily_notes.module_settings import daily_notes_priority_enabled

        is_done = validated_data.pop('is_done', None)
        assigned_to = validated_data.pop('assigned_to', None)
        if not daily_notes_priority_enabled():
            validated_data.pop('priority', None)
            instance.priority = PRIORITY_MEDIUM
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if assigned_to is not None:
            instance.assigned_to = assigned_to
        if is_done is not None:
            self._apply_completion(instance, is_done)
        instance.save()
        return instance
