import os

EXEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Tobii', 'Interaction_Streams_101.exe'))
USE_TOBII = os.name == 'nt' and os.path.exists(EXEC_PATH)
CMD_WORDS = ['build', 'place', 'move', 'track', 'turn', 'tilt', 'undo', 'redo', 'store', 'clone', 'give']

if USE_TOBII:
    import signal
    import subprocess
else:
    from Webcam import GazerBeam
    from threading import Thread


class EyeTracker:
    def __init__(self):
        import random
        import sys

        if not USE_TOBII:
            # setup webcam
            pass

        self.eye_tracking_process = None

        self.csv = f'gaze{random.randint(1, 1000000)}.csv'

    def start_eye_tracking(self):
        if USE_TOBII:
            l_command = self.command + ['-l']
            with open(self.csv, 'w') as csv:
                self.eye_tracking_process = subprocess.Popen(
                    l_command,
                    stdin=subprocess.PIPE,
                    stdout=csv,
                )
        else:
            self.eye_tracking_process = GazerBeam(['log'])
            self.eye_tracking_process = (self.eye_tracking_process, 
                                         Thread(target=self.eye_tracking_process.run))
            self.eye_tracking_process[1].start()

    def process_transcript(self, transcript):
        tokens = transcript.split()
        command_words = [word for word in tokens if word in CMD_WORDS]
        if not command_words or command_words[0] != 'track':
            return

        if USE_TOBII:
            t_command = self.command.copy()
            if 'move' in command_words:
                t_command += ['-m']
            elif 'build' in command_words or 'place' in command_words:
                t_command += ['-d']

            stdout = subprocess.check_output(t_command)
        else:
            # run webcam process
            pass

    def terminate_eye_tracking(self):
        if self.eye_tracking_process:
            if USE_TOBII:
                self.eye_tracking_process.send_signal(signal.CTRL_C_EVENT)
                self.eye_tracking_process.wait()
            else:
                self.eye_tracking_process[0].terminate()
                self.eye_tracking_process[1].join()

        self.eye_tracking_process = None
