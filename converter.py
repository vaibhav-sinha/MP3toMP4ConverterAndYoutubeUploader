from moviepy.editor import *


def convert_to_mp4(audio_file, name, image_file=None):
    if image_file:
        clip = ImageClip(image_file)
    else:
        clip = ColorClip(size=(1920, 1080))

    audio_clip = AudioFileClip(audio_file)
    clip = clip.set_audio(audio_clip)
    clip = clip.set_duration(audio_clip.duration)
    clip.write_videofile(name, fps=60)
    return name