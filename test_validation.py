import json
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.competition.serializers import RegistrationCreateSerializer
from django.core.files.uploadedfile import SimpleUploadedFile

serializer = RegistrationCreateSerializer(data={})
serializer.is_valid()
res = json.dumps(serializer.errors)
print(f"Len: {len(res)} -> {res}")
