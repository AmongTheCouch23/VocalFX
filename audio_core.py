import sys, os, pyaudio, numpy as np, wave, marshal, types

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EFFECTS_DIR = os.path.join(BASE_DIR, "effects")

if not os.path.exists(EFFECTS_DIR):
    os.makedirs(EFFECTS_DIR)

def list_devices():
    p = pyaudio.PyAudio()
    inputs, outputs = [], []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            inputs.append((i, info["name"]))
        if info.get("maxOutputChannels", 0) > 0:
            outputs.append((i, info["name"]))
    p.terminate()
    return inputs, outputs

def compile_effect(source_code: str, output_name: str):
    path = os.path.join(EFFECTS_DIR, f"{output_name}.vocaleffect")
    with open(path, "w", encoding="utf-8") as f:
        f.write(source_code)
    print(f"[Compiled] Saved text effect -> {path}")
    return path

def load_effect(path: str):
    import types
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    mod = types.ModuleType("vocaleffect_module")
    exec(compile(code, path, "exec"), mod.__dict__)
    if not hasattr(mod, "apply"):
        raise AttributeError(f"No 'apply' function defined in {path}")
    return mod

def record_chunk(stream, chunk=1024):
    return np.frombuffer(stream.read(chunk, exception_on_overflow=False), dtype=np.float32)

def play_chunk(stream, data):
    stream.write(data.astype(np.float32).tobytes())

def save_wav(filename, frames, rate=44100):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
