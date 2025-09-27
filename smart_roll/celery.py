import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_roll.settings')
app = Celery('smartroll')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
