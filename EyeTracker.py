import os
import platform
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
        self.eye_tracking_process = subprocess.Popen(
            l_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def process_transcript(self, transcript):
        if not self.executable: return

        tokens = transcript.split()
        command_words = []
        for index, word in enumerate(tokens):
            if word in self.supported_commands:
                command_words.append(word)
    
        if command_words[0] == 'track':
            t_command = self.command.copy()
            if 'move' in command_words:
                t_command += ['-m']
            elif 'build' in command_words or 'place' in command_words:
                t_command += ['-d']
            
            self.terminate_eye_tracking()
            stdout = subprocess.check_output(t_command)
            with open(self.csv, 'a') as csv:
                csv.write('\n'.join(stdout.decode().split('\r\n')))

            self.start_eye_tracking()

    def terminate_eye_tracking(self):
        if self.eye_tracking_process:
            stdout = self.eye_tracking_process.communicate(input=b'.')[0]
            
            with open(self.csv, 'a') as csv:
                csv.write('\n'.join(stdout.decode().split('\r\n')))

            self.eye_tracking_process = None