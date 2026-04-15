import subprocess
import sys
import urllib.request
import os

print("Installing requirements...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)

print("Downloading Mediapipe Face Landmarker Model...")
model_url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
model_path = "face_landmarker.task"
if not os.path.exists(model_path):
    urllib.request.urlretrieve(model_url, model_path)
    print("✅ Model downloaded successfully.")
else:
    print("✅ Model already exists.")

print("\n✅ Setup complete! Run 'python main.py' to start MARK XXV.")
