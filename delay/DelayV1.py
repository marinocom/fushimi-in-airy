import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import librosa
import soundfile as sf
import pygame
import os

class ToriDelayPlugin:
    def __init__(self, root, bpm=120):
        self.root = root
        self.root.title("Fushimi In-Airy")
        self.bpm = bpm
        self.fs = 44100
        self.scale_factor = 0.3

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_file = "examples/delay/minecraft-firework.mp3"
        self.output_file = "examples/delay/minecraft-firework-delay-output.wav"

        # 1. GATE Boundaries
        self.LEFT = 230 * self.scale_factor
        self.RIGHT = 1755 * self.scale_factor
        self.TOP = 710 * self.scale_factor
        self.BOTTOM = 2140 * self.scale_factor  

        # 2. KNOB Boundaries 
        self.KNOB_TOP = 2320 * self.scale_factor
        self.KNOB_BOTTOM = 2537 * self.scale_factor
        self.DRY_X = 255 * self.scale_factor
        self.WET_X = 538 * self.scale_factor

        pygame.mixer.init()

        # Load Background
        bg_raw = Image.open("gui/backgrounds/background_delay.png")
        self.w, self.h = int(bg_raw.width * self.scale_factor), int(bg_raw.height * self.scale_factor)
        self.bg_img = ImageTk.PhotoImage(bg_raw.resize((self.w, self.h), Image.Resampling.LANCZOS))

        self.canvas = tk.Canvas(root, width=self.w, height=self.h)
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.bg_img, anchor="nw")

        # # Lines for debugging
        # self.canvas.create_line(self.DRY_X, self.KNOB_TOP, self.DRY_X, self.KNOB_BOTTOM, fill="red", width=2)
        # self.canvas.create_line(self.WET_X, self.KNOB_TOP, self.WET_X, self.KNOB_BOTTOM, fill="red", width=2)
        # self.canvas.create_rectangle(self.LEFT, self.TOP, self.RIGHT, self.BOTTOM, outline="red")

        # 3. Load Gates
        self.gate_images, self.gate_objects = [], []
        for i in range(1, 6):
            img = Image.open(f"gui/icons/gates/torii{i}.png")
            resized = ImageTk.PhotoImage(img.resize((int(img.width*self.scale_factor), int(img.height*self.scale_factor)), Image.Resampling.LANCZOS))
            self.gate_images.append(resized)
            # Start them at BOTTOM (Silent)
            gate = self.canvas.create_image(self.LEFT + (150*i*self.scale_factor), self.BOTTOM, image=resized, tags="gate")
            self.gate_objects.append(gate)

        # 4. Load Knobs (Dry/Wet)
        dry_raw = Image.open("gui/icons/knobs/dry_knob.png")
        self.dry_knob_img = ImageTk.PhotoImage(dry_raw.resize((int(dry_raw.width*self.scale_factor), int(dry_raw.height*self.scale_factor)), Image.Resampling.LANCZOS))
        # Initialize at TOP (100% Volume)
        self.dry_knob_obj = self.canvas.create_image(self.DRY_X, self.KNOB_TOP, image=self.dry_knob_img, tags="dry_knob")

        wet_raw = Image.open("gui/icons/knobs/wet_knob.png")
        self.wet_knob_img = ImageTk.PhotoImage(wet_raw.resize((int(wet_raw.width*self.scale_factor), int(wet_raw.height*self.scale_factor)), Image.Resampling.LANCZOS))
        # Initialize at TOP (100% Volume)
        self.wet_knob_obj = self.canvas.create_image(self.WET_X, self.KNOB_TOP, image=self.wet_knob_img, tags="wet_knob")

        # 5. Bind Interactions
        self.canvas.tag_bind("gate", "<B1-Motion>", self.drag_gate)
        self.canvas.tag_bind("dry_knob", "<B1-Motion>", self.drag_dry)
        self.canvas.tag_bind("wet_knob", "<B1-Motion>", self.drag_wet)
        
        self.canvas.tag_bind("gate", "<ButtonRelease-1>", self.process_and_play)
        self.canvas.tag_bind("dry_knob", "<ButtonRelease-1>", self.process_and_play)
        self.canvas.tag_bind("wet_knob", "<ButtonRelease-1>", self.process_and_play)
        
        self.audio_data, _ = librosa.load(self.input_file, sr=self.fs, mono=True)

    def drag_gate(self, event):
        new_x = max(self.LEFT, min(event.x, self.RIGHT))
        new_y = max(self.TOP, min(event.y, self.BOTTOM))
        self.canvas.coords(tk.CURRENT, new_x, new_y)

    def drag_dry(self, event):
        new_y = max(self.KNOB_TOP, min(event.y, self.KNOB_BOTTOM))
        self.canvas.coords(self.dry_knob_obj, self.DRY_X, new_y)

    def drag_wet(self, event):
        new_y = max(self.KNOB_TOP, min(event.y, self.KNOB_BOTTOM))
        self.canvas.coords(self.wet_knob_obj, self.WET_X, new_y)

    def process_and_play(self, event):
        taps = []
        ms_per_beat = 60000 / self.bpm
        for gate in self.gate_objects:
            x, y = self.canvas.coords(gate)
            # Time: X relative to the gate area (LEFT to RIGHT)
            gate_width = self.RIGHT - self.LEFT
            num_beats = ((x - self.LEFT) / gate_width) * 4.0
            time_ms = num_beats * ms_per_beat
            # Volume: Y relative to TOP and BOTTOM
            range_y = self.BOTTOM - self.TOP
            gain_db = 0 - (((y - self.TOP) / range_y) * 60)
            taps.append({'time_ms': time_ms, 'gain_db': gain_db})

        # Calculate Mix from Knobs
        _, dry_y = self.canvas.coords(self.dry_knob_obj)
        _, wet_y = self.canvas.coords(self.wet_knob_obj)
        knob_range = self.KNOB_BOTTOM - self.KNOB_TOP
        
        # If range is 0 to avoid division by zero
        if knob_range == 0: knob_range = 1
        
        # Inverting: Top (KNOB_TOP) is 1.0, Bottom (KNOB_BOTTOM) is 0.0
        dry_mix = 1.0 - ((dry_y - self.KNOB_TOP) / knob_range)
        wet_mix = 1.0 - ((wet_y - self.KNOB_TOP) / knob_range)

        print("Dry= ", dry_mix ,  ", Wet= ", wet_mix ,  ", Taps Active: " , len(taps))
        processed = self.apply_dsp(self.audio_data, taps, dry_mix, wet_mix)
        
        sf.write(self.output_file, processed, self.fs)
        pygame.mixer.music.load(self.output_file)
        pygame.mixer.music.play()

    def apply_dsp(self, input_signal, taps, dry_mix, wet_mix):
        max_delay = max([t['time_ms'] for t in taps]) if taps else 0
        tail = int(self.fs * (max_delay / 1000.0) + self.fs)
        output = np.zeros(len(input_signal) + tail)
        
        # 1. Apply Dry Signal
        output[:len(input_signal)] += input_signal * dry_mix
        
        # 2. Apply Wet Taps
        for tap in taps:
            # Tap Gain * Master Wet Mix
            gain = (10**(tap['gain_db'] / 20)) * wet_mix
            shift = int(self.fs * (tap['time_ms'] / 1000.0))
            if shift + len(input_signal) < len(output):
                output[shift:shift+len(input_signal)] += input_signal * gain
        
        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0.001: # Avoid dividing by zero if silent
            if peak > 1.0:
                output /= peak
        return output

root = tk.Tk()
app = ToriDelayPlugin(root)
root.mainloop()