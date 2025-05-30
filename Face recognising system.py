import sys
import cv2
import dlib
import logging
import sqlite3
import numpy as np
from PyQt6.QtCore import Qt, QThread, Signal, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget, QMessageBox

# Setup logging
logging.basicConfig(filename='face_protection.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Dlib face detector and shape predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# Database setup
conn = sqlite3.connect('users.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (name TEXT, embedding BLOB, lockout_time INTEGER)''')
conn.commit()

class VideoCaptureThread(QThread):
    update_frame = Signal(QImage)

    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)
        self.running = True

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                self.update_frame.emit(q_img)
        self.cap.release()

    def stop(self):
        self.running = False
        self.wait()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Face Recognition File Protector")
        self.setGeometry(100, 100, 800, 600)

        # UI elements
        self.camera_label = QLabel(self)
        self.camera_label.setFixedSize(640, 480)
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Enter username")
        self.file_input = QLineEdit(self)
        self.file_input.setPlaceholderText("Enter file path to protect")
        self.register_button = QPushButton("Register User", self)
        self.authenticate_button = QPushButton("Authenticate & Protect File", self)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.camera_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.file_input)
        layout.addWidget(self.register_button)
        layout.addWidget(self.authenticate_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Connect buttons
        self.register_button.clicked.connect(self.register_user)
        self.authenticate_button.clicked.connect(self.authenticate_user)

        # Start video capture thread
        self.video_thread = VideoCaptureThread()
        self.video_thread.update_frame.connect(self.update_camera_feed)
        self.video_thread.start()

        # Timer for face capture
        self.face_capture_timer = QTimer(self)
        self.face_capture_timer.timeout.connect(self.capture_face)
        self.face_capture_timer.start(1000)

        self.current_frame = None
        self.face_descriptor = None

    def update_camera_feed(self, q_img):
        self.camera_label.setPixmap(QPixmap.fromImage(q_img))

    def capture_face(self):
        if self.current_frame is not None:
            gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
            faces = detector(gray)
            if faces:
                shape = predictor(gray, faces[0])
                face_chip = dlib.get_face_chip(self.current_frame, shape)
                self.face_descriptor = np.array(face_chip).flatten()

    def register_user(self):
        username = self.username_input.text()
        if not username:
            QMessageBox.warning(self, "Input Error", "Please enter a username.")
            return
        if self.face_descriptor is None:
            QMessageBox.warning(self, "Face Error", "No face detected. Please look at the camera.")
            return

        # Save user data to database
        cursor.execute("INSERT INTO users (name, embedding, lockout_time) VALUES (?, ?, ?)",
                       (username, self.face_descriptor.tobytes(), 0))
        conn.commit()
        logging.info(f"User '{username}' registered successfully.")
        QMessageBox.information(self, "Registration", f"User '{username}' registered successfully.")

    def authenticate_user(self):
        username = self.username_input.text()
        file_path = self.file_input.text()
        if not username or not file_path:
            QMessageBox.warning(self, "Input Error", "Please enter both username and file path.")
            return

        cursor.execute("SELECT embedding, lockout_time FROM users WHERE name = ?", (username,))
        user = cursor.fetchone()
        if user is None:
            QMessageBox.warning(self, "Authentication Error", "User not found.")
            return

        embedding = np.frombuffer(user[0], dtype=np.float64)
        lockout_time = user[1]
        if lockout_time > 0:
            QMessageBox.warning(self, "Account Locked", f"Account is locked until {lockout_time}.")
            return

        # Compare face embeddings
        if self.face_descriptor is None:
            QMessageBox.warning(self, "Face Error", "No face detected. Please look at the camera.")
            return

        distance = np.linalg.norm(embedding - self.face_descriptor)
        if distance < 0.6:
            QMessageBox.information(self, "Access Granted", f"Access granted to {username}.")
            logging.info(f"User '{username}' authenticated successfully.")
            # Protect file logic here
        else:
            QMessageBox.warning(self, "Authentication Failed", "Face recognition failed.")
            logging.warning(f"Authentication failed for user '{username}'.")

    def closeEvent(self, event):
        self.video_thread.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
