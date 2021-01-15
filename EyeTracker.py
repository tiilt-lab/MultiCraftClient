import os
import platform
import signal
import subprocess

class EyeTrackerClass:

    def __init__(self):  
        self.system = platform.system()
        self.command = [
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'Tobii', 
                'Interaction_Streams_101.exe',
            )
        ]
        self.exists = os.path.exists(self.command[0])
        self.executable = self.system == 'Windows' and self.exists

        self.eye_tracking_process = None
        self.supported_commands = [
            'build',
            'place',
            'move',
            'track',
            'turn',
            'tilt',
            'undo',
            'redo',
            'store',
            'clone',
            'give'
        ]
        self.csv = 'gaze.csv'

    def start_eye_tracking(self):
        if not self.executable or self.eye_tracking_process: return

        l_command = self.command + ['-l']
        with open(self.csv, 'a') as csv:
            self.eye_tracking_process = subprocess.Popen(
                l_command,
                stdin=subprocess.PIPE,
                stdout=csv,
            )

    def process_transcript(self, transcript):
        if not self.executable: return

        tokens = transcript.split()
        command_words = [word for word in tokens if word in self.supported_commands]
        if not command_words or command_words[0] != 'track': return 

        t_command = self.command.copy()
        if 'move' in command_words:
            t_command += ['-m']
        elif 'build' in command_words or 'place' in command_words:
            t_command += ['-d']
        
        stdout = subprocess.check_output(t_command)

    def terminate_eye_tracking(self):
        if self.eye_tracking_process:
            self.eye_tracking_process.send_signal(signal.CTRL_C_EVENT)
            self.eye_tracking_process = None