import speech_recognition as sr
import pyttsx3
import pywhatkit
import datetime
import wikipedia
import pyjokes
import os
import webbrowser

# Initialize the speech engine
engine = pyttsx3.init()
engine.setProperty('rate', 150)

def talk(text):
    engine.say(text)
    engine.runAndWait()

def listen_command():
    listener = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Listening...")
        listener.adjust_for_ambient_noise(source)
        audio = listener.listen(source)
    try:
        command = listener.recognize_google(audio)
        command = command.lower()
        print(f"🔊 You said: {command}")
    except sr.UnknownValueError:
        print("❗ I didn't catch that.")
        return ""
    return command

def run_jarvis():
    command = listen_command()

    if 'play' in command:
        song = command.replace('play', '')
        talk(f"Playing {song}")
        pywhatkit.playonyt(song)

    elif 'time' in command:
        time = datetime.datetime.now().strftime('%I:%M %p')
        talk(f"Current time is {time}")

    elif 'who is' in command:
        person = command.replace('who is', '')
        info = wikipedia.summary(person, 1)
        print(info)
        talk(info)

    elif 'joke' in command:
        joke = pyjokes.get_joke()
        talk(joke)

    elif 'open google' in command:
        talk("Opening Google")
        webbrowser.open("https://www.google.com")

    elif 'open youtube' in command:
        talk("Opening YouTube")
        webbrowser.open("https://www.youtube.com")

    elif 'your name' in command:
        talk("My name is Jarvis, your personal assistant.")

    elif 'exit' in command or 'quit' in command:
        talk("Goodbye!")
        exit()

    else:
        talk("Please repeat. I didn't understand.")

# Run forever
talk("Hello, I am Jarvis. How can I help you?")
while True:
    run_jarvis()
