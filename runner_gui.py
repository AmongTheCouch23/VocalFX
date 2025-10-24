import sys, threading, numpy as np, pyaudio, os, time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QSlider, QHBoxLayout
)
from PyQt6.QtCore import Qt

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

AUDIO_CORE_PATH = os.path.join(BASE_DIR, "audio_core.py")
EFFECTS_DIR = os.path.join(BASE_DIR, "effects")
os.makedirs(EFFECTS_DIR, exist_ok=True)

print(f"[Info] Effects folder located at: {EFFECTS_DIR}")

try:
    import importlib.util, importlib.machinery
    if os.path.exists(AUDIO_CORE_PATH):
        spec = importlib.util.spec_from_file_location("audio_core", AUDIO_CORE_PATH)
        audio_core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audio_core)
        print("[Info] audio_core imported from", AUDIO_CORE_PATH)
    else:
        import audio_core
        print("[Info] audio_core imported from package")

    load_effect = audio_core.load_effect
    record_chunk = audio_core.record_chunk
    play_chunk = audio_core.play_chunk

except Exception as e:
    print(f"[Warning] Failed to import audio_core: {e}")
    def load_effect(path): return None
    def record_chunk(s, c): return np.zeros(c, np.float32)
    def play_chunk(s, d): pass

class FXRunner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Couchy VocalFX Runner")
        self.resize(420, 340)
        layout = QVBoxLayout()

        self.p = pyaudio.PyAudio()
        self.in_box, self.out_box = QComboBox(), QComboBox()
        self.refresh_devices()

        self.effect_box = QComboBox()
        self.effect_box.addItem("None (Dry Mic)")
        for f in os.listdir(EFFECTS_DIR):
            if f.endswith(".vocaleffect"):
                self.effect_box.addItem(f)

        for w in [
            QLabel("Input Device:"), self.in_box,
            QLabel("Output Device:"), self.out_box,
            QLabel("Effect:"), self.effect_box,
        ]:
            layout.addWidget(w)

        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(1, 10)
        self.gain_slider.setValue(2)
        layout.addWidget(QLabel("Gain:"))
        layout.addWidget(self.gain_slider)

        self.start_btn = QPushButton("Start Processing")
        self.stop_btn = QPushButton("Stop")
        bl = QHBoxLayout()
        bl.addWidget(self.start_btn)
        bl.addWidget(self.stop_btn)
        layout.addLayout(bl)

        self.status = QLabel("Idle")
        layout.addWidget(self.status)
        self.setLayout(layout)

        self.running = False
        self.thread = None
        self.instream = None
        self.outstream = None

        self.start_btn.clicked.connect(self.start_fx)
        self.stop_btn.clicked.connect(self.stop_fx)

    def refresh_devices(self):
        self.in_box.clear()
        self.out_box.clear()
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            name = info.get("name", f"Device {i}")
            if info.get("maxInputChannels", 0) > 0:
                self.in_box.addItem(name, i)
            if info.get("maxOutputChannels", 0) > 0:
                self.out_box.addItem(name, i)

    def resolve_device_index(self, name, is_input=True):
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info.get("name") == name:
                if is_input and info.get("maxInputChannels", 0) > 0:
                    return i
                if not is_input and info.get("maxOutputChannels", 0) > 0:
                    return i
        return None

    def get_first_valid_devices(self):
        in_idx = out_idx = None
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if in_idx is None and info.get("maxInputChannels", 0) > 0:
                in_idx = i
            if out_idx is None and info.get("maxOutputChannels", 0) > 0:
                out_idx = i
            if in_idx is not None and out_idx is not None:
                break
        return in_idx, out_idx

    def start_fx(self):
        if self.running:
            return
        self.running = True
        self.status.setText("Starting...")
        self.thread = threading.Thread(target=self.fx_thread, daemon=False)
        self.thread.start()

    def stop_fx(self):
        if not self.running:
            return
        self.status.setText("Stopping...")
        self.running = False

    def fx_thread(self):
        RATE, CHUNK = 44100, 1024
        in_name = self.in_box.currentText()
        out_name = self.out_box.currentText()
        in_idx = self.resolve_device_index(in_name, True)
        out_idx = self.resolve_device_index(out_name, False)
        if in_idx is None or out_idx is None:
            in_idx, out_idx = self.get_first_valid_devices()

        fx = None
        effect_name = self.effect_box.currentText()
        if effect_name != "None (Dry Mic)":
            path = os.path.join(EFFECTS_DIR, effect_name)
            try:
                fx = load_effect(path)
                if fx and hasattr(fx, "apply"):
                    print(f"[FXRunner] Loaded effect: {effect_name}")
                else:
                    print(f"[FXRunner] Invalid effect file: {effect_name}")
                    fx = None
            except Exception as e:
                print(f"[FXRunner] Load error: {e}")
                self.status.setText(f"Failed to load effect.")
                fx = None

        params = {"gain": self.gain_slider.value()}

        try:
            self.instream = self.p.open(format=pyaudio.paFloat32,
                channels=1, rate=RATE, input=True,
                input_device_index=in_idx, frames_per_buffer=CHUNK)
            self.outstream = self.p.open(format=pyaudio.paFloat32,
                channels=1, rate=RATE, output=True,
                output_device_index=out_idx, frames_per_buffer=CHUNK)
        except Exception as e:
            self.status.setText(f"Audio error: {e}")
            self.running = False
            return

        self.status.setText("Running..." if fx else "Running (Dry Mic)...")
        time.sleep(0.15)

        try:
            while self.running:
                data = record_chunk(self.instream, CHUNK)
                if data.size == 0:
                    continue
                if fx and hasattr(fx, "apply"):
                    try:
                        data = fx.apply(data, RATE, params)
                    except Exception as e:
                        print(f"[Effect Error] {e}")
                        data = data * params["gain"]
                else:
                    data = data * params["gain"]
                play_chunk(self.outstream, data)
        except Exception as e:
            print(f"[Audio Thread Error] {e}")

        for s in [self.instream, self.outstream]:
            try:
                if s:
                    s.stop_stream()
                    s.close()
            except Exception:
                pass

        self.instream = self.outstream = None
        self.running = False
        self.status.setText("Stopped.")
        print("[FXRunner] Processing stopped cleanly.")


if __name__ == "__main__":
    p = pyaudio.PyAudio()
    print("=== Detected Audio Devices ===")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"[{i}] {info['name']} | In: {info['maxInputChannels']} | Out: {info['maxOutputChannels']}")
    p.terminate()

    app = QApplication(sys.argv)
    w = FXRunner()
    w.show()
    sys.exit(app.exec())
