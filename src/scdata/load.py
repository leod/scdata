import os

def get_audio_path(audio_dir, track_id):
    return os.path.join(audio_dir, str(track_id)[:3], str(track_id) + '.mp3')
