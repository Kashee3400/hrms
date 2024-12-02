# myapp/context_processors.py
from django.conf import settings
from datetime import datetime

def logo_settings(request):
    current_hour = datetime.now().hour

    if current_hour < 12:
        greeting = "Good Morning"
    elif 12 <= current_hour < 18:
        greeting = "Good Afternoon"
    elif 18 <= current_hour <21:
        greeting = "Good Evening"
    else:
        greeting = "Good Night"

    return {
        'LOGO_URL': settings.LOGO_URL,
        'LOGO_MINI_URL': settings.LOGO_MINI_URL,
        'GREETING': greeting,
    }