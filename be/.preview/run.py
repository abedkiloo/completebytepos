import os, sys
import dotenv
dotenv.load_dotenv = lambda *a, **k: False
here = os.path.dirname(os.path.abspath(__file__))
os.environ.update({
    'USE_SQLITE': 'true', 'DEBUG': 'true',
    'DB_PATH': os.path.join(here, 'preview.sqlite3'),
    'MEDIA_ROOT': os.path.join(here, 'media'),
    'LOG_DIR': os.path.join(here, 'logs'),
    'DJANGO_SETTINGS_MODULE': 'config.settings',
})
sys.path.insert(0, os.path.dirname(here))
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py'] + sys.argv[1:])
