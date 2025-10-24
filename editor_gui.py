import sys, threading, numpy as np, pyaudio
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QSlider, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from audio_core import list_devices, compile_effect, EFFECTS_DIR, record_chunk, play_chunk


class EffectEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Couchy VocalFX Editor")
        self.resize(800, 600)

        layout = QVBoxLayout()
        self.text_area = QTextEdit()
        self.text_area.setPlainText("""def apply(audio_data, sample_rate, params):
    import numpy as np
    gain = params.get("gain", 1.0)
    return np.clip(audio_data * gain, -1.0, 1.0)
""")
        layout.addWidget(QLabel("Effect Script (Python apply function):"))
        layout.addWidget(self.text_area)

        inputs, outputs = list_devices()
        self.in_box, self.out_box = QComboBox(), QComboBox()
        for idx, name in inputs: self.in_box.addItem(name, idx)
        for idx, name in outputs: self.out_box.addItem(name, idx)
        dlayout = QHBoxLayout()
        dlayout.addWidget(QLabel("Input:"));  dlayout.addWidget(self.in_box)
        dlayout.addWidget(QLabel("Output:")); dlayout.addWidget(self.out_box)
        layout.addLayout(dlayout)

        glayout = QHBoxLayout()
        glayout.addWidget(QLabel("Gain:"))
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(1, 10)
        self.gain_slider.setValue(1)
        glayout.addWidget(self.gain_slider)
        layout.addLayout(glayout)

        blayout = QHBoxLayout()
        self.play_btn = QPushButton("Preview")
        self.stop_btn = QPushButton("Stop")
        self.save_btn = QPushButton("Compile Effect")
        blayout.addWidget(self.play_btn)
        blayout.addWidget(self.stop_btn)
        blayout.addWidget(self.save_btn)
        layout.addLayout(blayout)

        self.status = QLabel("Idle")
        layout.addWidget(self.status)
        self.setLayout(layout)

        self.running = False
        self.p = pyaudio.PyAudio()
        self.play_btn.clicked.connect(self.start_preview)
        self.stop_btn.clicked.connect(self.stop_preview)
        self.save_btn.clicked.connect(self.save_effect)

    def start_preview(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self.preview_thread, daemon=True).start()

    def stop_preview(self):
        self.running = False

    def preview_thread(self):
        try:
            RATE, CHUNK = 44100, 1024
            in_idx = self.in_box.currentData()
            out_idx = self.out_box.currentData()
            code = self.text_area.toPlainText()
            mod = self._load_effect_from_text(code)

            params = {"gain": self.gain_slider.value()}
            instream = self.p.open(format=pyaudio.paFloat32, channels=1,
                                   rate=RATE, input=True, input_device_index=in_idx,
                                   frames_per_buffer=CHUNK)
            outstream = self.p.open(format=pyaudio.paFloat32, channels=1,
                                    rate=RATE, output=True, output_device_index=out_idx,
                                    frames_per_buffer=CHUNK)
            self.status.setText("Previewing...")

            while self.running:
                data = record_chunk(instream, CHUNK)
                if hasattr(mod, "apply"):
                    try:
                        data = mod.apply(data, RATE, params)
                    except Exception as e:
                        print(f"[Preview Error] {e}")
                play_chunk(outstream, data)

            instream.stop_stream(); instream.close()
            outstream.stop_stream(); outstream.close()
            self.status.setText("Stopped.")
        except Exception as e:
            self.status.setText(f"Error: {e}")

    def save_effect(self):
        src = self.text_area.toPlainText()
        try:
            mod = self._load_effect_from_text(src)
            if not hasattr(mod, "apply"):
                QMessageBox.warning(self, "Invalid", "No 'apply()' function defined.")
                return
        except Exception as e:
            QMessageBox.warning(self, "Compile Error", f"Invalid code:\n{e}")
            return

        name, _ = QFileDialog.getSaveFileName(self, "Save Effect", EFFECTS_DIR, "VocalEffect (*.vocaleffect)")
        if not name:
            return
        out_name = os.path.splitext(os.path.basename(name))[0]
        compile_effect(src, out_name)
        QMessageBox.information(self, "Compiled", f"Effect saved as {out_name}.vocaleffect")
        self.status.setText(f"Saved: {out_name}.vocaleffect")

    def _load_effect_from_text(self, code_str):
        import types
        mod = types.ModuleType("temp_effect")
        exec(compile(code_str, "<preview>", "exec"), mod.__dict__)
        return mod


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = EffectEditor()
    w.show()
    sys.exit(app.exec())
