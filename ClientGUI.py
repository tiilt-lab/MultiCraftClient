import json
import os
import socket
import tkinter as tk
import tkinter.font
import urllib.request
import uuid
from queue import Queue, Full
from threading import Thread

import pyaudio
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson import SpeechToTextV1
from ibm_watson.websocket import RecognizeCallback, AudioSource

from EyeTracker import EyeTracker

# PyAudio Configuration
CHUNK = 1024
BUF_MAX_SIZE = CHUNK * 10
q = Queue(maxsize=int(round(BUF_MAX_SIZE / CHUNK)))
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

# Create an instance of AudioSource
audio_source = AudioSource(q, True, True)

# File with environment variables
with open("ENV") as f:
    ENV = json.load(f)

# MultiCraftTextServer Endpoint
MCTS_URL = ENV.get("MCTS_URL", "")

# EyeTracker Setup
EYE_TRACKER = EyeTracker()

SERVER = ''

using_voice = False

def get_uuid(mc_username):
    global CLIENT_NAME
    try:
        with urllib.request.urlopen(f'https://api.mojang.com/users/profiles/minecraft/{mc_username}') as response:
            mc_profile = response.read().decode('utf-8')
        mc_username = json.loads(mc_profile)['name'] # ensures username is case-corrected
        CLIENT_NAME = str(uuid.UUID(json.loads(mc_profile)['id']))
        return f'Connected as {mc_username}\n({CLIENT_NAME})'
    except:
        return 'Unable to retrieve UUID: invalid username or API is down'

def connect_to_server(server_ip):
    global CLIENT_SOCKET
    global SERVER
    socket.setdefaulttimeout(5.0)
    CLIENT_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    SERVER = server_ip
    server_s = server_ip.split(':')
    if len(server_s) < 2:
        server_s.append(5003)

    try:
        CLIENT_SOCKET.connect((server_s[0], int(server_s[1])))
        CLIENT_SOCKET.close()
        return f'Connected to {SERVER}'
    except (socket.timeout, socket.gaierror, TimeoutError, ConnectionRefusedError):
        return f'Unable to connect: IP may be incorrect'

def connect_to_voice():
    global SPEECH_TO_TEXT, CUSTOMIZATION_ID
    API_KEY = ENV.get("API_KEY", "")
    SERVICE_URL = ENV.get("SERVICE_URL", "")
    CUSTOMIZATION_ID = ENV.get("CUSTOMIZATION_ID", "")
    authenticator = IAMAuthenticator(API_KEY)
    SPEECH_TO_TEXT = SpeechToTextV1(authenticator=authenticator)
    SPEECH_TO_TEXT.set_service_url(SERVICE_URL)

# Define callback for the Speech to Text service
class MyRecognizeCallback(RecognizeCallback):
    def __init__(self):
        RecognizeCallback.__init__(self)

    def on_transcription(self, transcript):
        print(transcript)

    def on_connected(self):
        print('Connection was successful')

    def on_error(self, error):
        print(f'Error received: {error}')

    def on_inactivity_timeout(self, error):
        print(f'Inactivity timeout: {error}')

    def on_listening(self):
        print('Service is listening\nEnter CTRL+C to end recording...')

    def on_hypothesis(self, hypothesis):
        pass

    def on_data(self, data):
        # Once received a command, print and send the command string to the server
        if(data['results'][0]['final']):
            transcript = data['results'][0]['alternatives'][0]['transcript'].lower()
            voice_frame.voice_command(transcript)
            EYE_TRACKER.process_transcript(transcript)
            try:
                urllib.request.urlopen(
                    f"{MCTS_URL}?uuid={CLIENT_NAME}&transcript={transcript.strip().replace(' ', '+')}&server={SERVER}",
                    timeout=5
                )
            except (urllib.error.HTTPError, socket.timeout):
                pass

    def on_close(self):
        CLIENT_SOCKET.close()
        print('Connection closed')

# Initiate the recognize service and pass in the AudioSource
def recognize_using_websocket(*args):
    mycallback = MyRecognizeCallback()

    SPEECH_TO_TEXT.recognize_using_websocket(audio=audio_source,
                                             content_type='audio/l16; rate=44100',
                                             recognize_callback=mycallback,
                                             language_customization_id=CUSTOMIZATION_ID,
                                             customization_weight=0.9,
                                             interim_results=True)

# Define callback for PyAudio to store the recording in queue
def pyaudio_callback(in_data, frame_count, time_info, status):
    try:
        q.put(in_data)
    except Full:
        pass # discard
    return (None, pyaudio.paContinue)



# Tkinter GUI
class Frame():
    def __init__(self, parent):
        self.parent = parent
        self.frame = tk.Frame(self.parent)

    def close_frame(self):
        self.frame.destroy()

class UsernameFrame(Frame):
    def __init__(self, parent):
        super().__init__(parent)

        EYE_TRACKER.start_eye_tracking()

        self.label = tk.Label(master=self.frame, text='What is your Minecraft username?', font=label_font1)
        self.entry = tk.Entry(master=self.frame)
        self.entry.bind('<Return>', lambda _: self.get_username())
        self.button = tk.Button(master=self.frame, text='OK', command=self.get_username, font=button_font)
        self.counter = 0
        self.error_label = tk.Label(master=self.frame, text='', font=label_font2)
        self.label.pack()
        self.entry.pack()
        self.button.pack()
        self.error_label.pack()
        self.frame.pack()

    def get_username(self):
        username = self.entry.get()
        message = get_uuid(username)
        if 'Connected' in message:
            self.close_frame()
            username_label = tk.Label(text=message, font=label_font2)
            username_label.pack() # outside of frame
            server_frame = ServerFrame(root)
        else:
            self.counter += 1
            self.error_label.config(text=f'[{self.counter}] {message}')

class ServerFrame(Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.label = tk.Label(master=self.frame, text='Server IP:', font=label_font1)
        self.entry = tk.Entry(master=self.frame)
        self.entry.bind('<Return>', lambda _: self.get_ip())
        self.button = tk.Button(master=self.frame, text='OK', command=self.get_ip, font=button_font)
        self.counter = 0
        self.error_label = tk.Label(master=self.frame, text='', font=label_font2)
        self.label.pack()
        self.entry.pack()
        self.button.pack()
        self.error_label.pack()
        self.frame.pack()

    def get_ip(self):
        ip = self.entry.get()
        message = connect_to_server(ip)
        if 'Connected' in message:
            self.close_frame()
            msg_label = tk.Label(text=message, font=label_font2)
            msg_label.pack() # outside of frame
            InputFrame(root)
        else:
            self.counter += 1
            self.error_label.config(text=f'[{self.counter}] {message}')

class InputFrame(Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.label = tk.Label(master=self.frame, text='Connect to Voice?', font=label_font1)
        self.button1 = tk.Button(master=self.frame, text='Yes', command=self.use_voice, font=button_font)
        self.button2 = tk.Button(master=self.frame, text='No', command=self.use_text, font=button_font)
        self.label.pack()
        self.button1.pack(side=tk.LEFT)
        self.button2.pack(side=tk.RIGHT)
        self.frame.pack()

    def use_text(self):
        self.close_frame()
        text_label = tk.Label(text='Using text commands', font=label_font2)
        text_label.pack()
        TextFrame(root)

    def use_voice(self):
        self.close_frame()
        voice_label = tk.Label(text='Using voice commands', font=label_font2)
        voice_label.pack()
        global voice_frame
        voice_frame = VoiceFrame(root)

class TextFrame(Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.label = tk.Label(master=self.frame, text='Message:', font=label_font1)
        self.entry = tk.Entry(master=self.frame)
        self.entry.bind('<Return>', lambda _: self.send_command())
        self.button = tk.Button(master=self.frame, text='Send', command=self.send_command, font=button_font)
        self.counter = 0
        self.msg_label = tk.Label(master=self.frame, text=f'[{self.counter}] Ready', font=label_font2)
        self.label.pack()
        self.entry.pack()
        self.button.pack()
        self.msg_label.pack()
        self.frame.pack()

    def send_command(self):
        message = self.entry.get().lower()
        EYE_TRACKER.process_transcript(message)
        try:
            urllib.request.urlopen(
                f"{MCTS_URL}?uuid={CLIENT_NAME}&transcript={message.strip().replace(' ', '+')}&server={SERVER}",
                timeout=5
            )
        except (urllib.error.HTTPError, socket.timeout):
            pass

        self.counter += 1
        self.msg_label.config(text=f'[{self.counter}] Command sent')
        self.entry.delete(0, tk.END)

class VoiceFrame(Frame):
    def __init__(self, parent):
        super().__init__(parent)
        global using_voice
        using_voice = True

        connect_to_voice()
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=pyaudio_callback,
            start=False
        )
        self.stream.start_stream()

        self.recognize_thread = Thread(target=recognize_using_websocket, args=())
        self.recognize_thread.start()

        self.prompt_lbl = tk.Label(master=self.frame, text='Transcript:', font=label_font1)
        self.transcript_lbl = tk.Label(master=self.frame, text='__________')
        self.counter = 0
        self.msg_label = tk.Label(master=self.frame, text=f'[{self.counter}] Ready', font=label_font2)
        self.prompt_lbl.pack()
        self.transcript_lbl.pack()
        self.msg_label.pack()
        self.frame.pack()

    def voice_command(self, transcript):
        self.transcript_lbl.config(text=transcript)
        self.counter += 1
        self.msg_label.config(text=f'[{self.counter}] Command sent')

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()
        audio_source.completed_recording()


root = tk.Tk()
root.title('Multicraft')

# Set window size
width  = root.winfo_screenwidth() // 3
height = root.winfo_screenheight() // 3
root.geometry(f'{width}x{height}')

# Fonts
label_font1 = tk.font.Font(font=None, size=20)
label_font2 = tk.font.Font(font=None, size=16)
button_font = tk.font.Font(font=None, size=16)

def on_close():
    if using_voice:
        voice_frame.stop()
    EYE_TRACKER.terminate_eye_tracking()
    send_gaze_data()
    root.destroy()

def send_gaze_data():
    if not os.path.exists(EYE_TRACKER.csv) or not SERVER: return

    try:
        with open(EYE_TRACKER.csv, "rb") as f:
            data = f.read(1024)
            if not data: return

            file_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            file_socket.connect((SERVER, 5004))
            while(data):
                file_socket.send(data)
                data = f.read(1024)
            file_socket.close()
    except (socket.timeout, TimeoutError):
        pass

username_frame = UsernameFrame(root)
quit_button = tk.Button(text='Quit', command=on_close, font=button_font)
quit_button.pack(side=tk.BOTTOM, pady=(0, 40))
root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
