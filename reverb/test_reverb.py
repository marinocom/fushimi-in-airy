import os
import numpy as np
import librosa
import soundfile as sf
from reverb_engine import apply_multi_instance_reverb


#  MAIN EXECUTION 
# this file is used to test the reverb algorithm schroeder reverb from the original reverbVx file

# Configuration
input_filename = 'minecraft-firework-reverb-input.mp3'  
output_filename = 'minecraft-firework-reverb-output.wav'

# define your Reverb Gates (Torii Gates on the mountain)
# X-axis = Decay time (0-10,000ms)
# Y-axis = Volume (0-100% of dry signal, which is 0 to -∞ dB)

# example gates: mix of short/loud and long/quiet reverbs
reverb_gates = [
    # Short, loud reverb (high on mountain, quick decay)
    {'decay_ms': 2000, 'gain_db': -3.0},   # ~71% volume, 2 second decay
    
    # Medium reverb
    {'decay_ms': 5000, 'gain_db': -10.0},  # ~32% volume, 5 second decay
    
    # Long, quiet reverb (low on mountain, slow decay)
    {'decay_ms': 8000, 'gain_db': -15.0},  # ~18% volume, 8 second decay
    
    # Very subtle, very long reverb
    {'decay_ms': 10000, 'gain_db': -20.0}, # ~10% volume, 10 second decay
]

try:
    # get absolute path to the folder where this script is saved
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = "examples/reverb/minecraft-firework-reverb-input.mp3"
    output_path = "examples/reverb/minecraft-firework-reverb-output.wav"

    # 1. load Audio (Handles MP3 and WAV)
    print(f"Loading: {input_path}")
    data, fs = librosa.load(input_path, sr=None, mono=False)

    # 2. handle Stereo
    if len(data.shape) > 1:
        data = librosa.to_mono(data)

    # 3. process with multi-instance reverb
    print(f"\nProcessing with Schroeder Reverb Algorithm...")
    processed_audio = apply_multi_instance_reverb(data, fs, reverb_gates, dry_mix=0.7)

    # 4. Save
    sf.write(output_path, processed_audio, fs)
    print(f"\nSUCCESS!")
    print(f"File saved to: {output_path}")
    print(f"Output length: {len(processed_audio)/fs:.2f} seconds")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()