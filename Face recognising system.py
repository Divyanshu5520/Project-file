import sys
import cv2
import dlib
import mysql.connector
import logging
import sqlite3
import numpy as np
import time
import os
import pyttsx3
from cryptography.fernet import Fernet
from PyQt6.QtCore import Qt, QThread, Signal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QHBoxLayout, QProgressBar, QFileDialog, QInputDialog, QTextEdit
)

# Logging setup
logging.basicConfig(filename='face_protection.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Dlib models (ensure these files exist in the folder)
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
face_rec_model = dlib.face_recognition_model_v1("dlib_face_recognition_resnet_model_v1.dat")



conn = mysql.connector.connect(
    host="localhost",
    user="your_mysql_username",
    password="your_mysql_password",
    database="face_protection"
)
cursor = conn.cursor()

# SQLite DB setup
conn = sqlite3.connect('users.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        name TEXT PRIMARY KEY,
        embedding BLOB,
        lockout_time INTEGER,
        role TEXT DEFAULT 'user'
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS file_keys (
        username TEXT,
        file_path TEXT,
        key BLOB,
        PRIMARY KEY(username, file_path)
    )
''')

conn.commit()

# Text-to-speech
engine = pyttsx3.init()
def speak(text):
    engine.say(text)
    engine.runAndWait()

# --- Video Capture Thread ---
class VideoCaptureThread(QThread):
    update_frame = Signal(np.ndarray)  # emit raw frame (numpy array) for more control

    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)
        self.running = True

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.update_frame.emit(frame)
        self.cap.release()

    def stop(self):
        self.running = False
        self.wait()

# --- Admin Panel ---
class AdminWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Panel")
        self.setGeometry(200, 200, 500, 400)

        # User management widgets
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Enter username")
        self.role_input = QLineEdit(self)
        self.role_input.setPlaceholderText("Enter role (user/admin)")

        self.add_button = QPushButton("Add User")
        self.remove_button = QPushButton("Remove User")
        self.view_logs_button = QPushButton("View Logs")

        self.logs_display = QTextEdit(self)
        self.logs_display.setReadOnly(True)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Manage Users"))
        layout.addWidget(self.username_input)
        layout.addWidget(self.role_input)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.add_button)
        btn_layout.addWidget(self.remove_button)
        btn_layout.addWidget(self.view_logs_button)

        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("Logs"))
        layout.addWidget(self.logs_display)

        self.setLayout(layout)

        # Connect
        self.add_button.clicked.connect(self.add_user)
        self.remove_button.clicked.connect(self.remove_user)
        self.view_logs_button.clicked.connect(self.view_logs)

    def add_user(self):
        username = self.username_input.text().strip()
        role = self.role_input.text().strip().lower()
        if role not in ('user', 'admin'):
            QMessageBox.warning(self, "Role Error", "Role must be 'user' or 'admin'.")
            return
        if not username:
            QMessageBox.warning(self, "Input Error", "Please enter a username.")
            return
        cursor.execute("SELECT name FROM users WHERE name = ?", (username,))
        if cursor.fetchone():
            QMessageBox.warning(self, "Error", f"User '{username}' already exists.")
            return
        cursor.execute("INSERT INTO users (name, embedding, lockout_time, role) VALUES (?, ?, ?, ?)",
                       (username, None, 0, role))
        conn.commit()
        QMessageBox.information(self, "Success", f"User '{username}' added with role '{role}'.")

    def remove_user(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Input Error", "Please enter a username.")
            return
        cursor.execute("SELECT name FROM users WHERE name = ?", (username,))
        if not cursor.fetchone():
            QMessageBox.warning(self, "Error", f"User '{username}' not found.")
            return
        cursor.execute("DELETE FROM users WHERE name = ?", (username,))
        cursor.execute("DELETE FROM file_keys WHERE username = ?", (username,))
        conn.commit()
        QMessageBox.information(self, "Success", f"User '{username}' removed.")

    def view_logs(self):
        try:
            with open('face_protection.log', 'r') as f:
                logs = f.read()
            self.logs_display.setPlainText(logs)
        except FileNotFoundError:
            self.logs_display.setPlainText("No logs found.")


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Face Recognition File Protector")
        self.setGeometry(100, 100, 900, 700)

        # UI
        self.camera_label = QLabel(self)
        self.camera_label.setFixedSize(640, 480)

        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Enter username")

        self.file_input = QLineEdit(self)
        self.file_input.setPlaceholderText("File path")

        self.register_button = QPushButton("Register User Face")
        self.authenticate_button = QPushButton("Authenticate & Protect File")
        self.decrypt_button = QPushButton("Decrypt File")
        self.admin_login_button = QPushButton("Admin Login")

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.camera_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.file_input)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.register_button)
        btn_layout.addWidget(self.authenticate_button)
        btn_layout.addWidget(self.decrypt_button)
        btn_layout.addWidget(self.admin_login_button)

        layout.addLayout(btn_layout)
        layout.addWidget(self.progress_bar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Connections
        self.register_button.clicked.connect(self.register_user)
        self.authenticate_button.clicked.connect(self.authenticate_user)
        self.decrypt_button.clicked.connect(self.decrypt_file)
        self.admin_login_button.clicked.connect(self.admin_login)

        # Video thread
        self.video_thread = VideoCaptureThread()
        self.video_thread.update_frame.connect(self.update_camera_feed)
        self.video_thread.start()

        # Timer for face capture
        self.face_capture_timer = QTimer(self)
        self.face_capture_timer.timeout.connect(self.capture_face)
        self.face_capture_timer.start(500)  # faster capture for responsiveness

        self.current_frame = None
        self.face_descriptor = None
        self.failed_attempts = {}

    def update_camera_feed(self, frame):
        # Draw landmarks on frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector(gray)

        # Draw rectangle & landmarks
        for face in faces:
            x1, y1, x2, y2 = face.left(), face.top(), face.right(), face.bottom()
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            shape = predictor(gray, face)
            for i in range(68):
                part = shape.part(i)
                cv2.circle(frame, (part.x, part.y), 2, (0, 0, 255), -1)

        self.current_frame = frame

        # Convert to QImage
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.camera_label.setPixmap(QPixmap.fromImage(q_img))

    def capture_face(self):
        if self.current_frame is not None:
            gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
            faces = detector(gray)
            if faces:
                shape = predictor(gray, faces[0])
                face_chip = dlib.get_face_chip(self.current_frame, shape)
                descriptor = np.array(face_rec_model.compute_face_descriptor(face_chip), dtype=np.float64)
                self.face_descriptor = descriptor / np.linalg.norm(descriptor)
            else:
                self.face_descriptor = None

    def register_user(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Input Error", "Please enter a username.")
            return
        if self.face_descriptor is None:
            QMessageBox.warning(self, "Face Error", "No face detected. Please look at the camera.")
            return

        self.progress_bar.setValue(0)
        QApplication.processEvents()

        cursor.execute("SELECT embedding FROM users WHERE name = ?", (username,))
        user = cursor.fetchone()
        if user is None:
            cursor.execute("INSERT INTO users (name, embedding, lockout_time, role) VALUES (?, ?, ?, ?)",
                           (username, self.face_descriptor.tobytes(), 0, 'user'))
        else:
            cursor.execute("UPDATE users SET embedding = ?, lockout_time = 0 WHERE name = ?",
                           (self.face_descriptor.tobytes(), username))
        conn.commit()
        logging.info(f"User '{username}' registered successfully.")
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "Registration", f"User '{username}' registered successfully.")

    def authenticate_user(self):
        username = self.username_input.text().strip()
        file_path = self.file_input.text().strip()
        if not username or not file_path:
            QMessageBox.warning(self, "Input Error", "Please enter both username and file path.")
            return

        cursor.execute("SELECT embedding, lockout_time FROM users WHERE name = ?", (username,))
        user = cursor.fetchone()
        if user is None:
            QMessageBox.warning(self, "Authentication Error", "User not found.")
            speak("Access denied")
            return

        embedding_bytes, lockout_time = user
        current_time = int(time.time())
        if lockout_time and lockout_time > current_time:
            QMessageBox.warning(self, "Account Locked", f"Account is locked until {time.ctime(lockout_time)}.")
            speak("Access denied")
            return

        if self.face_descriptor is None:
            QMessageBox.warning(self, "Face Error", "No face detected. Please look at the camera.")
            speak("Access denied")
            return

        stored_embedding = np.frombuffer(embedding_bytes, dtype=np.float64)
        stored_embedding /= np.linalg.norm(stored_embedding)

        dist = np.linalg.norm(stored_embedding - self.face_descriptor)
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        MAX_ATTEMPTS = 3
        LOCKOUT_DURATION = 60  # seconds

        if dist < 0.6:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Access Granted", f"Access granted to {username}.")
            logging.info(f"User '{username}' authenticated successfully.")
            self.failed_attempts[username] = 0
            speak("Access granted")
            self.protect_file(username, file_path)
        else:
            self.failed_attempts[username] = self.failed_attempts.get(username, 0) + 1
            logging.warning(f"Authentication failed for user '{username}'. Attempt {self.failed_attempts[username]}")
            if self.failed_attempts[username] >= MAX_ATTEMPTS:
                lockout_until = current_time + LOCKOUT_DURATION
                cursor.execute("UPDATE users SET lockout_time = ? WHERE name = ?", (lockout_until, username))
                conn.commit()
                QMessageBox.warning(self, "Locked Out", f"Too many failed attempts. Locked for {LOCKOUT_DURATION} seconds.")
            else:
                QMessageBox.warning(self, "Authentication Failed", "Face recognition failed.")
            speak("Access denied")
            self.progress_bar.setValue(0)

    def protect_file(self, username, file_path):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Error", "File does not exist.")
            return

        # Check if key already exists for this user-file pair
        cursor.execute("SELECT key FROM file_keys WHERE username = ? AND file_path = ?", (username, file_path))
        key_row = cursor.fetchone()

        if key_row is None:
            key = Fernet.generate_key()
            cursor.execute("INSERT INTO file_keys (username, file_path, key) VALUES (?, ?, ?)", (username, file_path, key))
            conn.commit()
        else:
            key = key_row[0]

        cipher = Fernet(key)

        with open(file_path, 'rb') as f:
            data = f.read()

        encrypted_data = cipher.encrypt(data)

        enc_path = file_path + ".enc"
        with open(enc_path, 'wb') as f:
            f.write(encrypted_data)

        QMessageBox.information(self, "File Protected", f"File encrypted at:\n{enc_path}")
        logging.info(f"File '{file_path}' encrypted for user '{username}'.")

    def decrypt_file(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Input Error", "Please enter your username to decrypt.")
            return

        # Pick file to decrypt
        enc_file_path, _ = QFileDialog.getOpenFileName(self, "Select Encrypted File", "", "Encrypted Files (*.enc)")
        if not enc_file_path:
            return

        cursor.execute("SELECT key FROM file_keys WHERE username = ? AND file_path = ?", (username, enc_file_path[:-4]))
        key_row = cursor.fetchone()
        if key_row is None:
            QMessageBox.warning(self, "Error", "No encryption key found for this file and user.")
            return

        key = key_row[0]
        cipher = Fernet(key)

        try:
            with open(enc_file_path, 'rb') as f:
                encrypted_data = f.read()

            decrypted_data = cipher.decrypt(encrypted_data)

            save_path, _ = QFileDialog.getSaveFileName(self, "Save Decrypted File As", enc_file_path[:-4])
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(decrypted_data)
                QMessageBox.information(self, "Success", f"File decrypted and saved to {save_path}.")
                logging.info(f"File '{enc_file_path}' decrypted by user '{username}'.")
        except Exception as e:
            QMessageBox.warning(self, "Decryption Failed", f"Failed to decrypt file: {str(e)}")

    def admin_login(self):
        password, ok = QInputDialog.getText(self, "Admin Login", "Enter admin password:", QLineEdit.EchoMode.Password)
        if ok:
            if password == "admin123":  # Change to secure password or use hashed check
                self.admin_window = AdminWindow(self)
                self.admin_window.show()
            else:
                QMessageBox.warning(self, "Access Denied", "Incorrect admin password.")

    def closeEvent(self, event):
        self.video_thread.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
