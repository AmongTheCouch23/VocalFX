import sys, threading, numpy as np, pyaudio, os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QSlider, QHBoxLayout
)
from PyQt6.QtCore import Qt
from audio_core import list_devices, load_effect, EFFECTS_DIR, record_chunk, play_chunk

class FXRunner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Couchy VocalFX Runner")
        self.resize(400, 320)
        layout = QVBoxLayout()

        inputs, outputs = list_devices()
        self.in_box, self.out_box = QComboBox(), QComboBox()
        for idx, name in inputs:
            self.in_box.addItem(name, idx)
        for idx, name in outputs:
            self.out_box.addItem(name, idx)

        self.effect_box = QComboBox()
        self.effect_box.addItem("None (Dry Mic)")
        for f in os.listdir(EFFECTS_DIR):
            if f.endswith(".vocaleffect"):
                self.effect_box.addItem(f)

        layout.addWidget(QLabel("Input Device:"))
        layout.addWidget(self.in_box)
        layout.addWidget(QLabel("Output Device:"))
        layout.addWidget(self.out_box)
        layout.addWidget(QLabel("Effect:"))
        layout.addWidget(self.effect_box)

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
        self.p = pyaudio.PyAudio()
        self.start_btn.clicked.connect(self.start_fx)
        self.stop_btn.clicked.connect(self.stop_fx)

    def start_fx(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self.fx_thread, daemon=True).start()

    def stop_fx(self):
        self.running = False

    def fx_thread(self):
        RATE, CHUNK = 44100, 1024
        in_idx, out_idx = self.in_box.currentData(), self.out_box.currentData()
        effect_name = self.effect_box.currentText()

        fx = None
        if effect_name != "None (Dry Mic)":
            path = os.path.join(EFFECTS_DIR, effect_name)
            fx = load_effect(path)

        params = {"gain": self.gain_slider.value()}

        instream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=RATE,
            input=True,
            input_device_index=in_idx,
            frames_per_buffer=CHUNK,
        )
        outstream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=RATE,
            output=True,
            output_device_index=out_idx,
            frames_per_buffer=CHUNK,
        )

        self.status.setText("Running..." if fx else "Running (Dry Mic)...")

        while self.running:
            data = record_chunk(instream, CHUNK)

            if fx and hasattr(fx, "apply"):
                data = fx.apply(data, RATE, params)
            else:
                data = data * params["gain"]

            play_chunk(outstream, data)

        instream.close()
        outstream.close()
        self.status.setText("Stopped.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FXRunner()
    w.show()
    sys.exit(app.exec())
