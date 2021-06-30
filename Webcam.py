import cv2
import mediapipe as mp
import numpy as np

KERNEL = np.ones((9, 9), np.uint8)

def landmarks_to_np(landmarks, shape, dtype="int"):
    """
    Convert mediapipe face mesh into a numpy array

    Parameters:
        landmarks (mp.multi_face_landmarks): mediapipe detected object to convert

    Returns:
        coords (np.ndarray): coordinates of each facial landmark
    """
    # initialize the list of (x, y)-coordinates
    coords = np.zeros((468, 2), dtype=dtype)
    # iterate and convert facial landmarks to coordinates
    for i in range(0, 468):
        landmark = landmarks[i]
        relative_x = int(landmark.x * shape[1])
        relative_y = int(landmark.y * shape[0])
        coords[i] = (relative_x, relative_y)
    # return list of coordinates
    return coords

def eye_on_mask(mask, side, landmarks):
    """
    Create ROI on mask of the size of the eyes and also return the extreme points

    Parameters:
        mask (np.uint8): mask to draw eyes on
        side (list[int]): facial landmark numbers of eye
        landmarks (list[uiint32]): facial landmarks

    Returns:
        mask (np.uint8): mask with ROI drawn
        min_max (list[tuple]): top left and bottom right coordinates of ROI's AABB
    """
    # create mask for eye ROI
    points = [landmarks[i] for i in side]
    points = np.array(points, dtype=np.int32)
    mask = cv2.fillConvexPoly(mask, points, 255)

    # find minimum and maximum coordinate locations of eye
    min_x = np.min(points[:,0])
    min_y = np.min(points[:,1])
    max_x = np.max(points[:,0])
    max_y = np.max(points[:,1])
    min_max = [(min_x, min_y), (max_x, max_y)]

    return mask, min_max

def process_mask(img, left, right, landmarks):
    """
    Mask image such that only the detected eyes are visible, return bounding boxes of eyes

    Parameters:
        img (np.ndarray): original image
        left (list[int]): facial landmark numbers of left eye
        right (list[int]): facial landmark numbers of right eye
        landmarks (list[uint32]): facial landmarks

    Returns:
        gray (np.ndarray): processed masked image
        left_min_max (list[tuple]): top left and bottom right coorindates of left eye's AABB
        right_min_max (list[tuple]): top left and bottom right coorindates of right eye's AABB
    """
    # mask image such that only eye ROIs are visible
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    mask, left_min_max = eye_on_mask(mask, left, landmarks)
    mask, right_min_max = eye_on_mask(mask, right, landmarks)
    mask = cv2.dilate(mask, KERNEL, 5)
    eyes = cv2.bitwise_and(img, img, mask=mask)
    mask = (eyes == [0, 0, 0]).all(axis=2)
    eyes[mask] = [255, 255, 255]

    # convert image to grayscale
    gray = cv2.cvtColor(eyes, cv2.COLOR_RGB2GRAY)

    # use histogram equalization to improve contrast of eyes
    equal = cv2.equalizeHist(gray[gray != 255])
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    clahe = clahe.apply(equal)
    gray[gray != 255] = clahe.flatten()

    return gray, left_min_max, right_min_max


def process_thresh(thresh):
    """
    Preprocess threshold image

    Parameters:
        thresh (np.ndarray): thresholded image to preprocess

    Returns:
        thresh (np.ndarray): processed thresholded image
    """
    # apply erosion, dilation, median blur, and bitwise not
    thresh = cv2.erode(thresh, None, iterations=2)
    thresh = cv2.dilate(thresh, None, iterations=4)
    thresh = cv2.medianBlur(thresh, 3)
    thresh = cv2.bitwise_not(thresh)

    return thresh

def find_eyeball_position(min_max, cx, cy):
    """
    Find and return the position of the eyeball (normal, left, right, or top)

    Parameters:
        min_max (list[tuple]): top left and bottom right coordinates of ROI's AABB
        cx (int): detected x coordinate of pupil
        cy (int): detected y coordinate of pupil

    Returns:
        pos (int): the position of the eyeball
            normal = 0, left = -1, right = 1
    """
    x_ratio = (min_max[0][0] - cx) / (cx - min_max[1][0])

    # TODO: more testing on these thresholds to determine direction
    if x_ratio > 1.5:
        return -1
    elif x_ratio < 0.33:
        return 1
    else:
        return 0


def contouring(thresh, mid, img, min_max, right=False):
    """
    Find the largest contour of an image divided by a midpoint and find the eye position

    Parameters:
        thresh (np.ndarray): thresholded image of one side containing the eyeball
        mid (int): midpoint between the eyes
        img (np.ndarray): original image
        min_max (list[tuple]): top left and bottom right coordinates of ROI's AABB
        right (boolean, optional): whether calculating for the right eye or left eye.
            defaults to false

    Returns:
        pos (int): the position of the eyeball
    """
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    try:
        cnt = max(cnts, key=cv2.contourArea)
        M = cv2.moments(cnt)
        cx = int(M['m10']/M['m00'])
        cy = int(M['m01']/M['m00'])
        if right:
            cx += mid
        cv2.circle(img, (cx, cy), 4, (0, 0, 255), 2)
        pos = find_eyeball_position(min_max, cx, cy)
        return pos
    except:
        return 0

def print_eye_pos(eye_pos):
    """
    Print where the eyes are looking and display on the image

    Parameters:
        img (np.ndarray): image to display on
        left (int): position obtained from left eye
        right (int): position obtained from right eye

    Returns:
        None
    """
    directions = {
        -1: 'Left',
        1: 'Right',
    }
    left, right = eye_pos

    if left != 0:
        print("Left:", directions[left])
    if right != 0:
        print("Right:", directions[right])


class Webcam:
    def __init__(self, debug=False):
        self._cap = cv2.VideoCapture(0) # initialize video capture
        self._face_mesh = mp.solutions.face_mesh
        self._left = [7, 33, 133, 144, 145, 153, 154, 155, 157, 158, 159, 160, 161, 163, 173, 246]
        self._right = [249, 263, 362, 373, 374, 380, 381, 382, 384, 385, 386, 387, 388, 390, 398, 466]

        self.running = False
        self.debug   = debug
        self.eye_pos = (0, 0)

    def run(self):
        self.running = True
        with self._face_mesh.FaceMesh(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5) as face_mesh:

            while self.running and self._cap.isOpened():
                success, img = self._cap.read()
                if not success:
                    continue

                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(img)
                if not results.multi_face_landmarks:
                    continue

                # get masked grayscale image and bounding boxes for each eye
                landmarks = landmarks_to_np(results.multi_face_landmarks[0].landmark, img.shape)
                mask, left_min_max, right_min_max = process_mask(img, self._left, self._right, landmarks)

                # convert the equalized grayscale image to binary image
                _, thresh = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
                thresh = process_thresh(thresh)

                # get midpoint between eyes and get left and right eye position
                mid = landmarks[6][0]
                left_pos = contouring(thresh[:, 0:mid], mid, img, left_min_max)
                right_pos = contouring(thresh[:, mid:], mid, img, right_min_max, True)

                self.eye_pos = (left_pos, right_pos)

                if self.debug:
                    print_eye_pos(self.eye_pos)

            self._cap.release()

    def get_eye_pos(self):
        return self.eye_pos

    def terminate(self):
        self.running = False


import time

class Timer:

    def __init__(self):
        self.init = time.time()
        self.start = time.time()
        self.running = False

    def run(self):
        self.start = time.time()
        self.running = True

    def stop(self):
        self.running = False

    def log(self):
        return f"{time.time() - self.init},"

    def elapsed(self):
        return time.time() - self.start if self.running else 0


import pyautogui

DIMENSIONS = pyautogui.size()
MOVE_SPEED = int(DIMENSIONS[0]/30)
DWELL_NOOP = 0
DWELL_STOP = 1
DWELL_MOVE = 2
WKEY_UP = False

class GazerBeam:
    def __init__(self, args):
        self.args = args

    def handle_args(self):
        log_mode = "log" in self.args

        if self.args:
            arg = self.args[0]
            if arg == "stop":
                return DWELL_STOP, log_mode
            elif arg == "move":
                return DWELL_MOVE, log_mode

        return DWELL_NOOP, log_mode

    def handle_eye_pos(self, pos, prev_pos, dt, config):
        global WKEY_UP
        dwell_action, log_mode = config

        print(dt.log(), f"{pos[0]}, {pos[1]}")

        # check if eye position has changed
        displace_left, displace_right = (pos[0] - prev_pos[0], pos[1] - prev_pos[1])
        moved = (displace_left != 0 and displace_right != 0)

        if not moved and not dt.running:
            dt.run()
        elif moved and dt.running:
            dt.stop()
            if dwell_action == DWELL_MOVE and not WKEY_UP:
                WKEY_UP = True
                pyautogui.keyUp('w')

        if dt.running and dt.elapsed() > 3:
            if dwell_action == DWELL_STOP:
                self.terminate()
                return
            elif dwell_action == DWELL_MOVE and WKEY_UP:
                WKEY_UP = False
                pyautogui.keyDown('w')

        if not log_mode and pos[0] == pos[1]:
            pyautogui.move(pos[0] * MOVE_SPEED, 0)


    def run(self):
        from threading import Thread

        config = self.handle_args()

        # initialize collection timer
        ct = Timer()
        ct.run()

        # initialize dwelling timer
        dt = Timer()
        dt.run()

        # initialize webcam and run thread
        wc = Webcam()
        th = Thread(target=wc.run, name='webcam')
        th.start()

        self.running = True
        prev_pos = (0, 0)

        while self.running:
            if ct.elapsed() > 1/60:
                pos = wc.get_eye_pos()
                self.handle_eye_pos(pos, prev_pos, dt, config)
                prev_pos = pos
                ct.run()

        wc.terminate()

        # wait for webcam to shut down
        th.join()

    def terminate(self):
        self.running = False
