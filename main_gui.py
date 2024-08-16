import pyaudio
import numpy as np
from pydub import AudioSegment
import threading
import time
import tkinter as tk
import os


class AudioMixerGUI:
    def __init__(self, master):
        self.master = master
        master.title("Audio Mixer")

        self.mp3_files = [f for f in os.listdir('.') if f.endswith('.mp3')]
        self.buttons = []

        columns = 5

        for i, file in enumerate(self.mp3_files):
            btn = tk.Button(master, text=file, command=lambda f=file: self.play_sound(f))
            btn.grid(row=i // columns, column=i % columns, padx=1, pady=1)
            self.buttons.append(btn)

        btn = tk.Button(master, text="stop", command=lambda: self.stop_sound())
        btn.grid(row=(i+1) // columns, column=(i+1) % columns, padx=1, pady=1)
        self.buttons.append(btn)

    def play_sound(self, file):
        global current_mp3, play_once, mp3_samples, mp3_index
        current_mp3 = AudioSegment.from_mp3(file).set_channels(CHANNELS).set_frame_rate(RATE)
        mp3_samples = np.array(current_mp3.get_array_of_samples()).astype(np.float32) / 2 ** 15
        play_once = True
        mp3_index = 0

    def stop_sound(self):
        global current_mp3, play_once, mp3_samples, mp3_index
        current_mp3 = None
        mp3_samples = None
        play_once = False
        mp3_index = 0


def list_audio_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')

    for i in range(0, numdevices):
        dev_info = p.get_device_info_by_host_api_device_index(0, i)
        print(
            f"Device id {i} - {dev_info.get('name')} (Max Input Ch: {dev_info.get('maxInputChannels')}, Max Output Ch: {dev_info.get('maxOutputChannels')})")

    p.terminate()


# List available devices
list_audio_devices()

# Get user input for the device IDs
mic_device_id = int(input("Enter the ID of your microphone: "))
virtual_device_id = int(input("Enter the ID of the virtual cable device: "))

# Initialize PyAudio
p = pyaudio.PyAudio()

# Audio parameters
CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 2
RATE = 44100

print(f"Processing with {CHANNELS} channels")

# Open stream for microphone input
mic_stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=mic_device_id,
                    frames_per_buffer=CHUNK)

# Open stream for virtual device output
virtual_output_stream = p.open(format=FORMAT,
                               channels=CHANNELS,
                               rate=RATE,
                               output=True,
                               output_device_index=virtual_device_id,
                               frames_per_buffer=CHUNK)

# Open stream for default output device
default_output_stream = p.open(format=FORMAT,
                               channels=CHANNELS,
                               rate=RATE,
                               output=True,
                               output_device_index=p.get_default_output_device_info()['index'],
                               frames_per_buffer=CHUNK)

# Global variables for control
running = True
mp3_volume = 0.15
mic_volume = 0.8
current_mp3 = None
play_once = False
mp3_index = 0
mp3_samples = None

def audio_callback():
    global running, mp3_volume, mic_volume, current_mp3, play_once, mp3_index, mp3_samples
    while running:
        # Read from microphone
        mic_data = np.frombuffer(mic_stream.read(CHUNK), dtype=np.float32)

        if current_mp3 is not None and play_once:
            mp3_chunk = mp3_samples[mp3_index:mp3_index + CHUNK * CHANNELS]
            mp3_index += CHUNK * CHANNELS

            if mp3_index >= len(mp3_samples):
                current_mp3 = None
                play_once = False
                mp3_index = 0

            if len(mp3_chunk) < CHUNK * CHANNELS:
                mp3_chunk = np.pad(mp3_chunk, (0, CHUNK * CHANNELS - len(mp3_chunk)), 'constant')

            mixed_audio = (mic_data * mic_volume + mp3_chunk * mp3_volume).astype(np.float32)

            default_output_stream.write((mp3_chunk * mp3_volume).astype(np.float32).tobytes())
        else:
            mixed_audio = (mic_data * mic_volume).astype(np.float32)

        # Write to virtual device output
        virtual_output_stream.write(mixed_audio.tobytes())


# Start audio processing in a separate thread
audio_thread = threading.Thread(target=audio_callback)
audio_thread.start()

# Create and run GUI
root = tk.Tk()
gui = AudioMixerGUI(root)

# Main loop
try:
    root.mainloop()
except KeyboardInterrupt:
    pass

running = False

# Wait for audio thread to finish
audio_thread.join()

# Clean up
mic_stream.stop_stream()
mic_stream.close()
virtual_output_stream.stop_stream()
virtual_output_stream.close()
default_output_stream.stop_stream()
default_output_stream.close()
p.terminate()

print("Audio mixing stopped.")