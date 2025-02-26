# views.py
import os
import shutil
import subprocess
import uuid
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url

# Cloudinary yapılandırması
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
)

@csrf_exempt
def video_upload(request):
    if request.method == "POST" and request.FILES.get("video"):
        try:
            video_file = request.FILES["video"]
            unique_id = uuid.uuid4().hex

            # Geçici dizin oluştur
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', unique_id)
            os.makedirs(temp_dir, exist_ok=True)
            temp_video_path = os.path.join(temp_dir, video_file.name)

            # Videoyu geçici olarak kaydet
            with open(temp_video_path, 'wb+') as f:
                for chunk in video_file.chunks():
                    f.write(chunk)

            # Kareleri çıkar
            frame_dir = os.path.join(temp_dir, 'frames')
            os.makedirs(frame_dir, exist_ok=True)
            frame_pattern = os.path.join(frame_dir, 'frame_%03d.jpg')
            cmd_extract = [
                'ffmpeg', '-i', temp_video_path,
                '-vf', 'fps=1', '-q:v', '2', frame_pattern
            ]
            subprocess.run(cmd_extract, check=True, capture_output=True)

            # Cloudinary'ye video yükle
            upload_result = cloudinary.uploader.upload(
                temp_video_path,
                resource_type="video",
                public_id=f"videos/{unique_id}",
                overwrite=True
            )
            video_url = upload_result['secure_url']

            # Kareleri Cloudinary'ye yükle
            frame_urls = []
            for frame_name in sorted(os.listdir(frame_dir)):
                frame_path = os.path.join(frame_dir, frame_name)
                frame_upload = cloudinary.uploader.upload(
                    frame_path,
                    folder=f"frames/{unique_id}",
                    use_filename=True,
                    unique_filename=False
                )
                frame_urls.append(frame_upload['secure_url'])

            # Geçici dosyaları sil
            shutil.rmtree(temp_dir)

            return JsonResponse({
                'video_url': video_url,
                'frames': frame_urls,
                'frame_count': len(frame_urls)
            })

        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Geçersiz istek'}, status=400)

@csrf_exempt
def video_trim(request):
    if request.method == 'POST':
        try:
            video_url = request.POST.get('video_url')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')

            # Public ID'yi URL'den al
            public_id, _ = cloudinary_url(video_url)
            if 'videos/' not in public_id:
                raise ValueError("Geçersiz video URL")

            # Geçici dizin oluştur
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', public_id.replace('/', '_'))
            os.makedirs(temp_dir, exist_ok=True)
            temp_video_path = os.path.join(temp_dir, 'original.mp4')

            # Cloudinary'den videoyu indir
            download_url = cloudinary.utils.cloudinary_url(public_id, resource_type="video")[0]
            response = requests.get(download_url)
            response.raise_for_status()
            with open(temp_video_path, 'wb') as f:
                f.write(response.content)

            # Videoyu kırp
            trimmed_path = os.path.join(temp_dir, 'trimmed.mp4')
            cmd_trim = [
    'ffmpeg', '-i', temp_video_path,
    '-ss', start_time, '-to', end_time,
    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
    '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
    trimmed_path
]

            subprocess.run(cmd_trim, check=True, capture_output=True)

            # Kırpılmışı yükle
            trimmed_public_id = f"trimmed/{public_id}"
            upload_result = cloudinary.uploader.upload(
                trimmed_path,
                resource_type="video",
                public_id=trimmed_public_id,
                overwrite=True
            )
            trimmed_url = upload_result['secure_url']

            # Orijinali ve kareleri sil
            cloudinary.uploader.destroy(public_id, resource_type="video")
            cloudinary.api.delete_resources_by_prefix(f"frames/{public_id}")

            # Temizlik
            shutil.rmtree(temp_dir)

            return JsonResponse({'trimmed_url': trimmed_url})

        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Geçersiz istek'}, status=400)