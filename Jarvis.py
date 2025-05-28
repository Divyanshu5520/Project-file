import speech_recognition as sr
import pyttsx3
import pywhatkit
import datetime
import wikipedia
import pyjokes
import os
import webbrowser
import logging
import threading
import requests
from dateutil import parser as date_parser
import sys

try:
    import tkinter as tk
except ImportError:
    tk = None

# ----------------- Configuration -----------------
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "YOUR_API_KEY")  # <- Replace with your OpenWeather key
LOG_FILE = "jarvis_log.txt"

# ----------------- Logging -----------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)

# ----------------- Text‑to‑Speech -----------------
engine = pyttsx3.init()
engine.setProperty("rate", 150)

language_voice_map = {
    "en": "en",
    "es": "spanish",
    "hi": "hindi",
}
current_language = "en"

def set_language(lang_code: str):
    """Switch recognition & TTS language if supported."""
    global current_language
    if lang_code not in language_voice_map:
        talk("Language not supported.")
        return
    current_language = lang_code
    # Voice handling may vary by system—adjust as needed
    talk(f"Language switched to {lang_code}")


def talk(text: str):
    """Speak & log a message."""
    logging.info(f"Jarvis: {text}")
    engine.say(text)
    engine.runAndWait()


# ----------------- Speech / Keyboard Input -----------------

def listen_command() -> str:
    """Listen via mic; fall back to typed input if anything goes wrong."""
    listener = sr.Recognizer()
    listener.dynamic_energy_threshold = True
    with sr.Microphone() as source:
        print("🎤 Listening…")
        listener.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = listener.listen(source, timeout=5)
        except sr.WaitTimeoutError:
            print("⌨️  Mic timeout, please type your command:")
            return input(">>> ").lower()
    try:
        command = listener.recognize_google(audio, language=current_language).lower()
        print(f"🔊 You said: {command}")
        logging.info(f"User: {command}")
        return command
    except (sr.UnknownValueError, sr.RequestError):
        print("❗ I didn't catch that. Please type your command:")
        cmd = input(">>> ").lower()
        logging.info(f"User(typed): {cmd}")
        return cmd


# ----------------- Reminders -----------------
reminders = []  # (text, datetime, timer)

def schedule_reminder(text: str, remind_time: datetime.datetime):
    delay = (remind_time - datetime.datetime.now()).total_seconds()
    if delay <= 0:
        talk("That time is in the past.")
        return

    def remind():
        talk(f"Reminder: {text}")

    timer = threading.Timer(delay, remind)
    timer.start()
    reminders.append((text, remind_time, timer))
    talk(f"Reminder set for {remind_time.strftime('%I:%M %p')}")


# ----------------- Weather -----------------

def get_weather(city: str):
    url = (
        "https://api.openweathermap.org/data/2.5/weather?"  # nosec
        f"q={city}&appid={WEATHER_API_KEY}&units=metric"
    )
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get("cod") != 200:
            talk("City not found.")
            return
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        talk(f"The temperature in {city} is {temp}°C with {desc}.")
    except requests.RequestException:
        talk("Unable to reach weather service at the moment.")


# ----------------- System Control -----------------

def system_control(cmd: str):
    if "shutdown" in cmd:
        talk("Shutting down the system.")
        if sys.platform.startswith("win"):
            os.system("shutdown /s /t 1")  # nosec
        else:
            os.system("shutdown -h now")  # nosec
    elif "restart" in cmd:
        talk("Restarting the system.")
        if sys.platform.startswith("win"):
            os.system("shutdown /r /t 1")  # nosec
        else:
            os.system("shutdown -r now")  # nosec
    elif "open notepad" in cmd and sys.platform.startswith("win"):
        talk("Opening Notepad.")
        os.system("notepad")  # nosec
    else:
        talk("System command not recognized.")


# ----------------- Core Command Router -----------------

def handle_command(command: str):
    if not command:
        return

    if "play" in command:
        song = command.replace("play", "").strip()
        talk(f"Playing {song}")
        pywhatkit.playonyt(song)

    elif "time" in command:
        now = datetime.datetime.now().strftime("%I:%M %p")
        talk(f"Current time is {now}")

    elif "who is" in command:
        person = command.replace("who is", "").strip()
        try:
            info = wikipedia.summary(person, sentences=1)
        except wikipedia.exceptions.WikipediaException:
            info = "Sorry, I couldn't find information on that."
        print(info)
        talk(info)

    elif "joke" in command:
        talk(pyjokes.get_joke())

    elif "open google" in command:
        talk("Opening Google")
        webbrowser.open("https://google.com")

    elif "open youtube" in command:
        talk("Opening YouTube")
        webbrowser.open("https://youtube.com")

    elif "weather" in command:
        city = command.replace("weather", "").strip() or ""
        if not city:
            talk("Which city?")
            city = listen_command()
        get_weather(city)

    elif "remind me" in command:
        try:
            parts = command.replace("remind me", "").split(" at ")
            text = parts[0].strip()
            remind_time = date_parser.parse(parts[1])
            schedule_reminder(text, remind_time)
        except (IndexError, ValueError):
            talk("Please specify reminder in the format 'remind me to <task> at <time>'.")

    elif "language" in command:
        lang = command.split()[-1]
        set_language(lang)

    elif any(x in command for x in ["shutdown", "restart", "open notepad"]):
        system_control(command)

    elif command in {"exit", "quit"}:
        talk("Goodbye!")
        sys.exit()

    else:
        talk("Please repeat. I didn't understand.")


# ----------------- Main Loop -----------------

def run_jarvis():
    command = listen_command()
    handle_command(command)


def start_gui():
    if tk is None:
        talk("Tkinter is not available on this system.")
        return

    root = tk.Tk()
    root.title("Jarvis Assistant")
    root.geometry("400x200")

    entry = tk.Entry(root, width=50)
    entry.pack(pady=20)

    output = tk.Label(root, text="", wraplength=380)
    output.pack()

    def on_enter(event=None):
        cmd = entry.get().lower()
        entry.delete(0, tk.END)
        output["text"] = f"You: {cmd}"
        handle_command(cmd)

    entry.bind("<Return>", on_enter)
    root.mainloop()


if __name__ == "__main__":
    if "--gui" in sys.argv:
        talk("Starting Jarvis with GUI mode.")
        start_gui()
    else:
        talk("Hello, I am Jarvis. How can I help you?")
        while True:
            run_jarvis()
