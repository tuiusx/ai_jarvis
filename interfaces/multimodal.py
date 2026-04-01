import time

import pyttsx3
import speech_recognition as sr


class MultiModalInterface:
    def __init__(self, wake_word="jarvis"):
        self.wake_word = wake_word.lower()
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        try:
            self.microphone = sr.Microphone()
        except Exception as exc:
            print(f"Erro ao inicializar microfone: {exc}")
            self.microphone = None

        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", 180)
        self.tts.setProperty("volume", 0.9)

        for voice in self.tts.getProperty("voices"):
            if "portuguese" in voice.name.lower() or "pt" in voice.name.lower():
                self.tts.setProperty("voice", voice.id)
                break

        self.last_wake_time = 0.0
        self.wake_timeout = 8
        self.listening = False

    def get_input(self):
        if not self.microphone:
            return None

        try:
            with self.microphone as source:
                if not self.listening:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    self.listening = True

                audio = self.recognizer.listen(source, phrase_time_limit=6, timeout=3)

            text = self.recognizer.recognize_google(audio, language="pt-BR").lower().strip()

            if self.wake_word in text:
                self.last_wake_time = time.time()
                self.output("Sim, estou ouvindo!")
                return None

            if time.time() - self.last_wake_time <= self.wake_timeout:
                return {"mode": "voice", "content": text, "confidence": 0.9}

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            if time.time() - self.last_wake_time <= self.wake_timeout:
                print("Nao entendi, pode repetir?")
        except sr.RequestError as exc:
            print(f"Erro no servico de reconhecimento: {exc}")
        except Exception as exc:
            print(f"Erro no reconhecimento: {exc}")

        return None

    def output(self, message):
        print(f"JARVIS: {message}")
        self.tts.say(message)
        self.tts.runAndWait()
