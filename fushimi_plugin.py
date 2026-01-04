import os
import numpy as np
import librosa
import soundfile as sf
import json
from reverb._engine import apply_multi_instance_reverb
from reverb.figma_reverb import load_reverb_gates_from_figma, figma_to_reverb_params

def apply_multi_tap_delay(input_signal, sample_rate, taps, dry_mix=1.0):
    """
    Applies multiple parallel delay taps to an input signal.
    (From original delay implementation)
    """
    max_delay_ms = max([tap['time_ms'] for tap in taps])
    tail_samples = int(sample_rate * (max_delay_ms / 1000.0) + (sample_rate * 0.5))
    
    total_length = len(input_signal) + tail_samples
    output_signal = np.zeros(total_length)
    
    output_signal[:len(input_signal)] += input_signal * dry_mix
    
    print(f"Applying {len(taps)} delay taps...")
    for i, tap in enumerate(taps):
        delay_time_ms = tap['time_ms']
        gain_db = tap['gain_db']
        
        linear_gain = 10**(gain_db / 20)
        delay_samples = int(sample_rate * (delay_time_ms / 1000.0))
        
        start = delay_samples
        end = start + len(input_signal)
        
        output_signal[start:end] += input_signal * linear_gain
        print(f" - Tap {i+1}: {delay_time_ms}ms at {gain_db}dB")

    max_peak = np.max(np.abs(output_signal))
    if max_peak > 1.0:
        print(f"Normalization applied: Signal peaked at {20 * np.log10(max_peak):.2f} dB")
        output_signal = output_signal / max_peak
        
    return output_signal


def figma_to_delay_params(x_pos, y_pos, frame_width, frame_height, 
                          max_time_ms=4000, max_gain_db=3.5, min_gain_db=-60):
    """
    Convert Figma X/Y coordinates to delay parameters.
    
    Based on the PDF specification for DELAY MODE:
    - X-axis: Time (0 to 4000ms)
    - Y-axis: Volume (0% to 150% of dry signal)
    
    Parameters:
    - x_pos: X position in Figma (0 = left edge)
    - y_pos: Y position in Figma (0 = top edge)
    - frame_width: Width of the Figma frame
    - frame_height: Height of the Figma frame
    
    Returns:
    - dict with 'time_ms' and 'gain_db'
    """
    x_norm = np.clip(x_pos / frame_width, 0.0, 1.0)
    y_norm = np.clip(y_pos / frame_height, 0.0, 1.0)
    
    # X-axis: Map to delay time (0 to 4000ms)
    time_ms = x_norm * max_time_ms
    
    # Y-axis: Map to gain (0% to 150%)
    # Y=0 is TOP (150%), Y=height is BOTTOM (0%)
    volume_percent = (1.0 - y_norm) * 150.0
    
    if volume_percent <= 0.1:
        gain_db = min_gain_db
    else:
        gain_db = 20 * np.log10(volume_percent / 100.0)
        gain_db = np.clip(gain_db, min_gain_db, max_gain_db)
    
    return {
        'time_ms': time_ms,
        'gain_db': gain_db
    }


class FushimiInAiry:
    """
    Main plugin class for Fushimi In-Airy.
    Supports both Delay Mode and Reverb Mode.
    """
    
    def __init__(self, mode='delay'):
        """
        Initialize the plugin.
        
        Parameters:
        - mode: 'delay' or 'reverb'
        """
        self.mode = mode
        self.gates = []
        self.dry_mix = 1.0
        self.wet_mix = 1.0
        self.tail_factor = 0.4  # Controls reverb tail length (0.3-0.5 recommended)
        
    def set_mode(self, mode):
        """Switch between 'delay' and 'reverb' mode"""
        if mode not in ['delay', 'reverb']:
            raise ValueError("Mode must be 'delay' or 'reverb'")
        self.mode = mode
        print(f"Mode switched to: {mode.upper()}")
        
    def load_gates_from_figma(self, json_file, frame_width, frame_height):
        """
        Load gate positions from Figma export and convert to audio parameters.
        """
        with open(json_file) as f:
            data = json.load(f)
        
        self.gates = []
        
        for layer in data.get('layers', []):
            if any(keyword in layer.get('name', '') for keyword in ['Torii', 'Gate']):
                x = layer.get('x', 0)
                y = layer.get('y', 0)
                
                if self.mode == 'delay':
                    params = figma_to_delay_params(x, y, frame_width, frame_height)
                else:  # reverb
                    params = figma_to_reverb_params(x, y, frame_width, frame_height)
                
                self.gates.append(params)
        
        print(f"Loaded {len(self.gates)} gates from Figma in {self.mode} mode")
        return self.gates
    
    def set_gates_manual(self, gates):
        """
        Manually set gate parameters.
        
        For delay mode: List of dicts with 'time_ms' and 'gain_db'
        For reverb mode: List of dicts with 'decay_ms' and 'gain_db'
        """
        self.gates = gates
        
    def process_audio(self, input_signal, sample_rate):
        """
        Process audio with the current mode and gate settings.
        """
        if len(self.gates) == 0:
            print("Warning: No gates configured!")
            return input_signal
        
        print(f"\n{'='*60}")
        print(f"Processing in {self.mode.upper()} MODE")
        print(f"{'='*60}")
        
        if self.mode == 'delay':
            output = apply_multi_tap_delay(
                input_signal, 
                sample_rate, 
                self.gates, 
                dry_mix=self.dry_mix
            )
        else:  # reverb
            output = apply_multi_instance_reverb(
                input_signal, 
                sample_rate, 
                self.gates, 
                dry_mix=self.dry_mix,
                tail_factor=self.tail_factor
            )
        
        # Apply wet mix
        return output * self.wet_mix


# --- MAIN EXECUTION EXAMPLE ---

if __name__ == "__main__":
    
    # Configuration
    input_filename = 'minecraft-firework.mp3'
    
    # Choose your mode: 'delay' or 'reverb'
    MODE = 'reverb'  # Change to 'delay' for delay mode
    
    output_filename = f'fushimi_{MODE}_output.wav'
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_path = os.path.join(script_dir, input_filename)
        output_path = os.path.join(script_dir, output_filename)
        
        # Initialize plugin
        plugin = FushimiInAiry(mode=MODE)
        
        # Configure gates manually (or use load_gates_from_figma for Figma integration)
        if MODE == 'delay':
            plugin.set_gates_manual([
                {'time_ms': 200,  'gain_db': -3.0}, 
                {'time_ms': 500,  'gain_db': -10.0},
                {'time_ms': 600,  'gain_db': -5.0},
                {'time_ms': 1000, 'gain_db': -10.0},
                {'time_ms': 1200, 'gain_db': -3.0}
            ])
        else:  # reverb
            plugin.set_gates_manual([
                {'decay_ms': 2000, 'gain_db': -3.0},
                {'decay_ms': 5000, 'gain_db': -10.0},
                {'decay_ms': 8000, 'gain_db': -15.0},
                {'decay_ms': 10000, 'gain_db': -20.0}
            ])
        
        # Set mix levels
        plugin.dry_mix = 0.7  # 70% dry signal
        plugin.wet_mix = 1.0  # 100% wet signal
        plugin.tail_factor = 0.4  # Reverb tail length (0.3=short, 0.5=long)
        
        # Load audio
        print(f"Loading: {input_path}")
        data, fs = librosa.load(input_path, sr=None, mono=False)
        
        if len(data.shape) > 1:
            print("Stereo file detected. Converting to Mono for processing...")
            data = librosa.to_mono(data)
        
        # Process
        processed_audio = plugin.process_audio(data, fs)
        
        # Save
        sf.write(output_path, processed_audio, fs)
        print(f"\n{'='*60}")
        print(f"SUCCESS!")
        print(f"File saved to: {output_path}")
        print(f"Output length: {len(processed_audio)/fs:.2f} seconds")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()