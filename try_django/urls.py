from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from .view import video_upload, video_trim


urlpatterns = [
    path('', video_upload),
    path('trim/', video_trim),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)