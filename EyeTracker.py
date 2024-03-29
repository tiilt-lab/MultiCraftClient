import os

EXEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Tobii', 'Interaction_Streams_101.exe')
USE_TOBII = os.name == 'nt' and os.path.exists(EXEC_PATH)
CMD_WORDS = ['build', 'place', 'move', 'track', 'turn', 'tilt', 'undo', 'redo', 'store', 'clone', 'give']

if USE_TOBII:
    import signal
    import subprocess
else:
    from Webcam import GazerBeam

class EyeTracker:
    def __init__(self):
        import random

        self.eye_tracking_process = None
        self.csv = f'gaze{random.randint(1, 999999):06d}.csv'
        self.csv_handle = None

    def start_eye_tracking(self):
        self.csv_handle = open(self.csv, 'w')

        if USE_TOBII:
            l_command = [EXEC_PATH, '-l']
            self.eye_tracking_process = subprocess.Popen(
                l_command,
                stdin=subprocess.PIPE,
                stdout=self.csv_handle,
            )

    def process_transcript(self, transcript):
        tokens = transcript.split()
        command_words = [word for word in tokens if word in CMD_WORDS]
        if not command_words or command_words[0] != 'track':
            return

        if USE_TOBII:
            t_command = [EXEC_PATH]
            if 'move' in command_words:
                t_command += ['-m']
            elif 'build' in command_words or 'place' in command_words:
                t_command += ['-d']

            _ = subprocess.check_output(t_command)
        else:
            command = []
            if 'move' in command_words:
                command = ['move']
            elif 'build' in command_words or 'place' in command_words:
                command = ['stop']

            GazerBeam(command, self.csv_handle).run()

    def terminate_eye_tracking(self):
        if self.eye_tracking_process:
            self.eye_tracking_process.send_signal(signal.CTRL_C_EVENT)

        self.csv_handle.close()

        self.csv_handle = None
        self.eye_tracking_process = None
