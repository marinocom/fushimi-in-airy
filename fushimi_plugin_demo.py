import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import librosa
import soundfile as sf
import pygame
import os
from reverb.reverb_engine import apply_multi_instance_reverb

# plug in support demo for both delay and reverb sections

class FushimiInAiryGUI:
    def __init__(self, root, bpm=120):
        self.root = root
        self.root.title("Fushimi In-Airy")
        self.bpm = bpm
        self.fs = 44100
        self.scale_factor = 0.3
        
        # current mode: 'delay' or 'reverb'
        self.current_mode = 'delay'
        
        # reverb parameters
        self.tail_factor = 0.0

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # file paths
        self.input_file = "examples/delay/minecraft-firework.mp3"
        self.delay_output_file = "examples/delay/minecraft-firework-delay-outputMAIN.wav"
        self.reverb_output_file = "examples/reverb/minecraft-firework-reverb-outputMAIN.wav"

        # 1. gate boundaries
        self.LEFT = 230 * self.scale_factor
        self.RIGHT = 1755 * self.scale_factor
        self.TOP = 710 * self.scale_factor
        self.BOTTOM = 2140 * self.scale_factor  

        # 2. knob boundaries 
        self.KNOB_TOP = 2320 * self.scale_factor
        self.KNOB_BOTTOM = 2537 * self.scale_factor
        self.DRY_X = 255 * self.scale_factor
        self.WET_X = 538 * self.scale_factor
        
        # 3. mode switch button position
        self.MODE_SWITCH_LEFT = 800 * self.scale_factor
        self.MODE_SWITCH_RIGHT = 1100 * self.scale_factor
        self.MODE_SWITCH_TOP = 2300 * self.scale_factor
        self.MODE_SWITCH_BOTTOM = 2550 * self.scale_factor

        pygame.mixer.init()

        # load backgrounds
        self.bg_delay = Image.open("gui/backgrounds/background_delay.png")
        self.bg_reverb = Image.open("gui/backgrounds/background_reverb.png")
        
        self.w = int(self.bg_delay.width * self.scale_factor)
        self.h = int(self.bg_delay.height * self.scale_factor)
        
        self.bg_img_delay = ImageTk.PhotoImage(
            self.bg_delay.resize((self.w, self.h), Image.Resampling.LANCZOS)
        )
        self.bg_img_reverb = ImageTk.PhotoImage(
            self.bg_reverb.resize((self.w, self.h), Image.Resampling.LANCZOS)
        )

        # create canvas
        self.canvas = tk.Canvas(root, width=self.w, height=self.h)
        self.canvas.pack()
        
        # set initial background
        self.bg_obj = self.canvas.create_image(0, 0, image=self.bg_img_delay, anchor="nw")

        # 3. load gates
        self.gate_images, self.gate_objects = [], []
        for i in range(1, 6):
            img = Image.open(f"gui/icons/gates/torii{i}.png")
            resized = ImageTk.PhotoImage(
                img.resize(
                    (int(img.width*self.scale_factor), int(img.height*self.scale_factor)), 
                    Image.Resampling.LANCZOS
                )
            )
            self.gate_images.append(resized)
            # start them at bottom (silent)
            gate = self.canvas.create_image(
                self.LEFT + (150*i*self.scale_factor), 
                self.BOTTOM, 
                image=resized, 
                tags="gate"
            )
            self.gate_objects.append(gate)

        # 4. load knobs (dry/wet)
        dry_raw = Image.open("gui/icons/knobs/dry_knob.png")
        self.dry_knob_img = ImageTk.PhotoImage(
            dry_raw.resize(
                (int(dry_raw.width*self.scale_factor), int(dry_raw.height*self.scale_factor)), 
                Image.Resampling.LANCZOS
            )
        )
        # initialize at top 100% volume
        self.dry_knob_obj = self.canvas.create_image(
            self.DRY_X, self.KNOB_TOP, 
            image=self.dry_knob_img, 
            tags="dry_knob"
        )

        wet_raw = Image.open("gui/icons/knobs/wet_knob.png")
        self.wet_knob_img = ImageTk.PhotoImage(
            wet_raw.resize(
                (int(wet_raw.width*self.scale_factor), int(wet_raw.height*self.scale_factor)), 
                Image.Resampling.LANCZOS
            )
        )
        # initialize at top (100% volume)
        self.wet_knob_obj = self.canvas.create_image(
            self.WET_X, self.KNOB_TOP, 
            image=self.wet_knob_img, 
            tags="wet_knob"
        )

        # 5. bind interactions
        self.canvas.tag_bind("gate", "<B1-Motion>", self.drag_gate)
        self.canvas.tag_bind("dry_knob", "<B1-Motion>", self.drag_dry)
        self.canvas.tag_bind("wet_knob", "<B1-Motion>", self.drag_wet)
        
        self.canvas.tag_bind("gate", "<ButtonRelease-1>", self.process_and_play)
        self.canvas.tag_bind("dry_knob", "<ButtonRelease-1>", self.process_and_play)
        self.canvas.tag_bind("wet_knob", "<ButtonRelease-1>", self.process_and_play)
        
        # mode switch - keyboard
        self.root.bind("<m>", lambda e: self.toggle_mode())
        self.root.bind("<M>", lambda e: self.toggle_mode())
        
        # mode switch - click area
        self.canvas.bind("<Button-1>", self.check_mode_switch)
        
        # load audio
        self.audio_data, _ = librosa.load(self.input_file, sr=self.fs, mono=True)
        
        print(f"Fushimi In-Airy initialized in {self.current_mode.upper()} mode")
        print("Press 'M' to toggle modes")

    def check_mode_switch(self, event):
        """check if click is in mode switch area"""
        if (self.MODE_SWITCH_LEFT <= event.x <= self.MODE_SWITCH_RIGHT and
            self.MODE_SWITCH_TOP <= event.y <= self.MODE_SWITCH_BOTTOM):
            self.toggle_mode()

    def toggle_mode(self):
        """switch between delay and reverb modes"""
        if self.current_mode == 'delay':
            self.current_mode = 'reverb'
            self.canvas.itemconfig(self.bg_obj, image=self.bg_img_reverb)
            print("\n=== SWITCHED TO REVERB MODE ===\n")
        else:
            self.current_mode = 'delay'
            self.canvas.itemconfig(self.bg_obj, image=self.bg_img_delay)
            print("\n=== SWITCHED TO DELAY MODE ===\n")

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
        """process audio based on current mode"""
        # get knob positions
        _, dry_y = self.canvas.coords(self.dry_knob_obj)
        _, wet_y = self.canvas.coords(self.wet_knob_obj)
        knob_range = self.KNOB_BOTTOM - self.KNOB_TOP
        
        if knob_range == 0: 
            knob_range = 1
        
        # calculate mix levels (inverted: top = 1.0, bottom = 0.0)
        dry_mix = 1.0 - ((dry_y - self.KNOB_TOP) / knob_range)
        wet_mix = 1.0 - ((wet_y - self.KNOB_TOP) / knob_range)

        # process based on mode
        if self.current_mode == 'delay':
            processed = self.apply_delay(dry_mix, wet_mix)
            output_file = self.delay_output_file
        else:  # reverb
            processed = self.apply_reverb(dry_mix, wet_mix)
            output_file = self.reverb_output_file
        
        # save and play
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        sf.write(output_file, processed, self.fs)
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()

    def apply_delay(self, dry_mix, wet_mix):
        """apply delay effect - exactly like delayv1"""
        taps = []
        ms_per_beat = 60000 / self.bpm
        
        for gate in self.gate_objects:
            x, y = self.canvas.coords(gate)
            
            # time: x relative to the gate area left to right
            gate_width = self.RIGHT - self.LEFT
            num_beats = ((x - self.LEFT) / gate_width) * 4.0
            time_ms = num_beats * ms_per_beat
            
            # volume: y relative to top and bottom
            range_y = self.BOTTOM - self.TOP
            gain_db = 0 - (((y - self.TOP) / range_y) * 60)
            
            taps.append({'time_ms': time_ms, 'gain_db': gain_db})

        print(f"DELAY: Dry={dry_mix:.2f}, Wet={wet_mix:.2f}, Taps={len(taps)}")
        
        # apply dsp
        max_delay = max([t['time_ms'] for t in taps]) if taps else 0
        tail = int(self.fs * (max_delay / 1000.0) + self.fs)
        output = np.zeros(len(self.audio_data) + tail)
        
        # 1. apply dry signal
        output[:len(self.audio_data)] += self.audio_data * dry_mix
        
        # 2. apply wet taps
        for tap in taps:
            # tap gain * master wet mix
            gain = (10**(tap['gain_db'] / 20)) * wet_mix
            shift = int(self.fs * (tap['time_ms'] / 1000.0))
            if shift + len(self.audio_data) < len(output):
                output[shift:shift+len(self.audio_data)] += self.audio_data * gain
        
        # normalize
        peak = np.max(np.abs(output))
        if peak > 0.001:
            if peak > 1.0:
                output /= peak
        
        return output

    def apply_reverb(self, dry_mix, wet_mix):
        """apply reverb effect, import function from reverb engine"""

        reverb_gates = []
        
        for gate in self.gate_objects:
            x, y = self.canvas.coords(gate)
            
            # x-axis: decay time 0 to 10 seconds
            gate_width = self.RIGHT - self.LEFT
            decay_ms = ((x - self.LEFT) / gate_width) * 10000.0
            
            # y-axis: volume 0% to 100%
            range_y = self.BOTTOM - self.TOP
            volume_percent = (1.0 - ((y - self.TOP) / range_y)) * 100.0
            gain_db = 20 * np.log10(volume_percent / 100.0) if volume_percent > 0.1 else -60
            
            reverb_gates.append({'decay_ms': decay_ms, 'gain_db': gain_db})

        print(f"REVERB: Dry={dry_mix:.2f}, Wet={wet_mix:.2f}, Gates={len(reverb_gates)}")
        
        # filter out silent gates
        active_gates = [g for g in reverb_gates if g['gain_db'] > -50]
        
        if len(active_gates) == 0:
            return self.audio_data
        
        # process reverb
        reverb_output = apply_multi_instance_reverb(
            self.audio_data, 
            self.fs, 
            active_gates, 
            dry_mix=0.0,
            tail_factor=self.tail_factor
        )
        
        # mix dry and wet
        output = np.zeros_like(reverb_output)
        output[:len(self.audio_data)] += self.audio_data * dry_mix
        output += reverb_output * wet_mix
        
        # normalize if needed to prevent clipping
        peak = np.max(np.abs(output))
        if peak > 1.0:
            output /= peak
        
        return output


# MAIN
if __name__ == "__main__":
    root = tk.Tk()
    app = FushimiInAiryGUI(root, bpm=120)
    root.mainloop()