import os
import shutil
import subprocess
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


@csrf_exempt
def video_upload(request):
    if request.method == "POST" and request.FILES.get("video"):
        video_file = request.FILES["video"]
        
        unique_id = uuid.uuid4().hex
        ext = os.path.splitext(video_file.name)[1]
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        save_path = os.path.join(upload_dir, f"{unique_id}{ext}")
        
        with open(save_path, 'wb+') as destination:
            for chunk in video_file.chunks():
                destination.write(chunk)
        
        frame_dir = os.path.join(settings.MEDIA_ROOT, 'frames', unique_id)
        os.makedirs(frame_dir, exist_ok=True)
        frame_pattern = os.path.join(frame_dir, 'frame_%03d.jpg')
        command = [
            'ffmpeg', '-i', save_path, '-vf', 'fps=1', '-q:v', '2', frame_pattern
        ]
        result = subprocess.run(command, capture_output=True)
        
        if result.returncode != 0:
            os.remove(save_path)
            shutil.rmtree(frame_dir, ignore_errors=True)
            return JsonResponse({'error': result.stderr.decode()}, status=500)
        
        frame_files = sorted(os.listdir(frame_dir))
        frame_urls = [f"{settings.MEDIA_URL}frames/{unique_id}/{f}" for f in frame_files]
        video_url = f"{settings.MEDIA_URL}uploads/{unique_id}{ext}"
        
        return JsonResponse({
            'message': 'Video uploaded',
            'video_url': video_url,
            'frames': frame_urls,
            'frame_count': len(frame_urls)
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def video_trim(request):
    if request.method == 'POST':
        video_url = request.POST.get('video_url')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        
        if not video_url.startswith(f"{settings.MEDIA_URL}uploads/"):
            return JsonResponse({'error': 'Invalid video URL'}, status=400)
        
        video_rel_path = video_url[len(settings.MEDIA_URL):]
        video_path = os.path.join(settings.MEDIA_ROOT, video_rel_path)
        if not os.path.isfile(video_path):
            return JsonResponse({'error': 'Video not found'}, status=404)
        
        unique_id = os.path.splitext(os.path.basename(video_path))[0]
        trimmed_dir = os.path.join(settings.MEDIA_ROOT, 'trimmed')
        os.makedirs(trimmed_dir, exist_ok=True)
        trimmed_path = os.path.join(trimmed_dir, f"{unique_id}_trimmed.mp4")
        
        command = [
    'ffmpeg', '-i', video_path, '-ss', start_time, '-to', end_time,
    '-c:v', 'libx264', '-c:a', 'aac', trimmed_path
]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            return JsonResponse({'error': result.stderr.decode()}, status=500)
        
        os.remove(video_path)
        frame_dir = os.path.join(settings.MEDIA_ROOT, 'frames', unique_id)
        if os.path.exists(frame_dir):
            shutil.rmtree(frame_dir)
        
        trimmed_url = f"{settings.MEDIA_URL}trimmed/{unique_id}_trimmed.mp4"
        return JsonResponse({
            'message': 'Video trimmed',
            'trimmed_url': trimmed_url
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)