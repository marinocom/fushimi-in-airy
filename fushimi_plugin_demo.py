import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import librosa
import soundfile as sf
import pygame
import os
from reverb.reverb_engine import apply_multi_instance_reverb

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
        self.tail_factor = 0.1

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # file paths - will switch based on mode
        self.input_file = "examples/delay/minecraft-firework.mp3"
        self.delay_output_file = "examples/delay/minecraft-firework-delay-output.wav"
        self.reverb_output_file = "examples/reverb/minecraft-firework-reverb-output.wav"

        # 1. gate boundaries (same for both modes)
        self.LEFT = 230 * self.scale_factor
        self.RIGHT = 1755 * self.scale_factor
        self.TOP = 710 * self.scale_factor
        self.BOTTOM = 2140 * self.scale_factor  

        # 2. knob boundaries 
        self.KNOB_TOP = 2320 * self.scale_factor
        self.KNOB_BOTTOM = 2537 * self.scale_factor
        self.DRY_X = 255 * self.scale_factor
        self.WET_X = 538 * self.scale_factor
        
        # 3. mode switch button position (Sun/Moon slider at bottom)
        self.MODE_SWITCH_LEFT = 800 * self.scale_factor
        self.MODE_SWITCH_RIGHT = 1100 * self.scale_factor
        self.MODE_SWITCH_TOP = 2300 * self.scale_factor
        self.MODE_SWITCH_BOTTOM = 2550 * self.scale_factor

        pygame.mixer.init()

        # load background (starts with delay)
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

        self.canvas = tk.Canvas(root, width=self.w, height=self.h)
        self.canvas.pack()
        
        # create background image object
        self.bg_obj = self.canvas.create_image(0, 0, image=self.bg_img_delay, anchor="nw")
        
        # mode switching rectangle
        self.mode_switch_hitbox = self.canvas.create_rectangle(
            self.MODE_SWITCH_LEFT, self.MODE_SWITCH_TOP,
            self.MODE_SWITCH_RIGHT, self.MODE_SWITCH_BOTTOM,
            outline="", width=0
        )

        # 4. load gates
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

        # 5. load knobs (dry/wet)
        dry_raw = Image.open("gui/icons/knobs/dry_knob.png")
        self.dry_knob_img = ImageTk.PhotoImage(
            dry_raw.resize(
                (int(dry_raw.width*self.scale_factor), int(dry_raw.height*self.scale_factor)), 
                Image.Resampling.LANCZOS
            )
        )
        # initialize at top (100% volume)
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


        # 6. bind interactions
        self.canvas.tag_bind("gate", "<B1-Motion>", self.drag_gate)
        self.canvas.tag_bind("dry_knob", "<B1-Motion>", self.drag_dry)
        self.canvas.tag_bind("wet_knob", "<B1-Motion>", self.drag_wet)
        
        self.canvas.tag_bind("gate", "<ButtonRelease-1>", self.process_and_play)
        self.canvas.tag_bind("dry_knob", "<ButtonRelease-1>", self.process_and_play)
        self.canvas.tag_bind("wet_knob", "<ButtonRelease-1>", self.process_and_play)
        
        # mode switch - bind to the hitbox
        self.canvas.tag_bind("mode_switch", "<Button-1>", self.toggle_mode_click)
        
        # bind general canvas click as backup
        self.canvas.bind("<Button-1>", self.check_mode_switch)
        
        # keyboard shortcut: press 'M' to toggle mode
        self.root.bind("<m>", lambda e: self.toggle_mode())
        self.root.bind("<M>", lambda e: self.toggle_mode())
        
        # load audio
        self.audio_data, _ = librosa.load(self.input_file, sr=self.fs, mono=True)
        
        print(f"\n{'='*60}")
        print(f"Fushimi In-Airy initialized in {self.current_mode.upper()} mode")
        print(f"Press 'M' to toggle between Delay and Reverb modes")
        print(f"{'='*60}\n")

    def check_mode_switch(self, event):
        # check if click is within the mode switch rectangle
        if (self.MODE_SWITCH_LEFT <= event.x <= self.MODE_SWITCH_RIGHT and self.MODE_SWITCH_TOP <= event.y <= self.MODE_SWITCH_BOTTOM):
            self.toggle_mode()

    def toggle_mode_click(self, event):
        self.toggle_mode()

    def toggle_mode(self):
        """Switch between delay and reverb modes"""
        if self.current_mode == 'delay':
            self.current_mode = 'reverb'
            self.canvas.itemconfig(self.bg_obj, image=self.bg_img_reverb)
    
        else:
            self.current_mode = 'delay'
            self.canvas.itemconfig(self.bg_obj, image=self.bg_img_delay)
        
        # Re-process with current gate positions
        self.process_and_play(None)

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
        """Process audio with current mode (delay or reverb)"""
        # calculate mix from knobs
        _, dry_y = self.canvas.coords(self.dry_knob_obj)
        _, wet_y = self.canvas.coords(self.wet_knob_obj)
        knob_range = self.KNOB_BOTTOM - self.KNOB_TOP
        
        if knob_range == 0: 
            knob_range = 1
        
        # inverting: top (KNOB_TOP) is 1.0, bottom (KNOB_BOTTOM) is 0.0
        dry_mix = 1.0 - ((dry_y - self.KNOB_TOP) / knob_range)
        wet_mix = 1.0 - ((wet_y - self.KNOB_TOP) / knob_range)

        if self.current_mode == 'delay':
            processed = self.process_delay(dry_mix, wet_mix)
            output_file = self.delay_output_file
        else:  # reverb
            processed = self.process_reverb(dry_mix, wet_mix)
            output_file = self.reverb_output_file
        
        # Save and play
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        sf.write(output_file, processed, self.fs)
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()

    def process_delay(self, dry_mix, wet_mix):
        """process with delay taps"""
        taps = []
        ms_per_beat = 60000 / self.bpm
        
        for gate in self.gate_objects:
            x, y = self.canvas.coords(gate)
            
            # X-axis: Time (0 to 4 seconds / 4 bars)
            gate_width = self.RIGHT - self.LEFT
            num_beats = ((x - self.LEFT) / gate_width) * 4.0
            time_ms = num_beats * ms_per_beat
            
            # Y-axis: Volume (0% to 150%)
            range_y = self.BOTTOM - self.TOP
            # Top = 150%, Bottom = 0%
            volume_percent = (1.0 - ((y - self.TOP) / range_y)) * 150.0
            gain_db = 20 * np.log10(volume_percent / 100.0) if volume_percent > 0.1 else -60
            
            taps.append({'time_ms': time_ms, 'gain_db': gain_db})

        print(f"\nDELAY: Dry={dry_mix:.2f}, Wet={wet_mix:.2f}, Taps={len(taps)}")
        return self.apply_delay_dsp(self.audio_data, taps, dry_mix, wet_mix)

    def process_reverb(self, dry_mix, wet_mix):
        """Process with reverb (descending the mountain)"""
        reverb_gates = []
        
        for gate in self.gate_objects:
            x, y = self.canvas.coords(gate)
            
            # X-axis: Decay time (0 to 10 seconds)
            gate_width = self.RIGHT - self.LEFT
            decay_ms = ((x - self.LEFT) / gate_width) * 10000.0
            
            # Y-axis: Volume (0% to 100%)
            range_y = self.BOTTOM - self.TOP
            # Top = 100%, Bottom = 0%
            volume_percent = (1.0 - ((y - self.TOP) / range_y)) * 100.0
            gain_db = 20 * np.log10(volume_percent / 100.0) if volume_percent > 0.1 else -60
            
            reverb_gates.append({'decay_ms': decay_ms, 'gain_db': gain_db})

        print(f"\nREVERB: Dry={dry_mix:.2f}, Wet={wet_mix:.2f}, Gates={len(reverb_gates)}")
        
        return self.apply_reverb_dsp(self.audio_data, reverb_gates, dry_mix, wet_mix)

    def apply_delay_dsp(self, input_signal, taps, dry_mix, wet_mix):
        """Apply multi-tap delay"""
        max_delay = max([t['time_ms'] for t in taps]) if taps else 0
        tail = int(self.fs * (max_delay / 1000.0) + self.fs * 0.5)
        output = np.zeros(len(input_signal) + tail)
        
        # Dry Signal
        output[:len(input_signal)] += input_signal * dry_mix
        
        # Wet Taps
        for tap in taps:
            gain = (10**(tap['gain_db'] / 20)) * wet_mix
            shift = int(self.fs * (tap['time_ms'] / 1000.0))
            if shift + len(input_signal) < len(output):
                output[shift:shift+len(input_signal)] += input_signal * gain
        
        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0.001:
            if peak > 1.0:
                output /= peak
        
        return output

    def apply_reverb_dsp(self, input_signal, reverb_gates, dry_mix, wet_mix):
        """Apply multi-instance reverb using the reverb engine"""
        # filter out gates with very low volume 
        active_gates = [g for g in reverb_gates if g['gain_db'] > -50]
        
        if len(active_gates) == 0:
            return input_signal
        
        # process reverb with dry_mix=1.0 to get the full reverb+dry signal
        # then apply the wet/dry mix
        full_output = apply_multi_instance_reverb(
            input_signal, 
            self.fs, 
            active_gates, 
            dry_mix=0.0,  
            tail_factor=self.tail_factor
        )
        
        # create final output 
        output = np.zeros_like(full_output)
        # add dry signal
        output[:len(input_signal)] += input_signal * dry_mix
        # add wet (reverb) signal
        output += full_output * wet_mix
        # normalize if needed - clipping problem prevention
        peak = np.max(np.abs(output))
        if peak > 1.0:
            output /= peak
        
        return output


# main
if __name__ == "__main__":
    root = tk.Tk()
    app = FushimiInAiryGUI(root, bpm=120)
    root.mainloop()