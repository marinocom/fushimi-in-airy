import os
import numpy as np
import librosa
import soundfile as sf
import json

# this file is mainly used to convert json coordinates to delay parameters in figma
# not used in the main live gui application, but used to load/save torii gate presets and export gate positions
# part of original plan documentation 


def load_taps_from_figma(json_file, frame_w, frame_h):
    with open(json_file) as f:
        data = json.load(f)
    
    taps = []
    # Assuming the JSON exports layer names and their x/y positions
    for layer in data['layers']:
        if "Tap" in layer['name']:
            # Use the conversion logic from Method 1
            audio_params = figma_to_audio(layer['x'], layer['y'], frame_w, frame_h)
            taps.append(audio_params)
    return taps

def apply_multi_tap_delay(input_signal, sample_rate, taps, dry_mix=1.0):
    """
    Applies multiple parallel delay taps to an input signal.
    """
    # 1. Calculate the required tail length based on the longest delay
    max_delay_ms = max([tap['time_ms'] for tap in taps])
    # Add an extra 500ms buffer just to be safe
    tail_samples = int(sample_rate * (max_delay_ms / 1000.0) + (sample_rate * 0.5))
    
    # 2. Prepare the output buffer (Input + Tail)
    total_length = len(input_signal) + tail_samples
    output_signal = np.zeros(total_length)
    
    # 3. Add the DRY (original) signal
    output_signal[:len(input_signal)] += input_signal * dry_mix
    
    # 4. Process each TAP independently
    print(f"Applying {len(taps)} delay taps...")
    for i, tap in enumerate(taps):
        delay_time_ms = tap['time_ms']
        gain_db = tap['gain_db']
        
        # Convert dB to Linear Gain: linear = 10^(db/20)
        linear_gain = 10**(gain_db / 20)
        
        # Calculate offset in samples
        delay_samples = int(sample_rate * (delay_time_ms / 1000.0))
        
        # Define where this tap starts and ends in the output buffer
        start = delay_samples
        end = start + len(input_signal)
        
        # Sum this tap into the output
        output_signal[start:end] += input_signal * linear_gain
        print(f" - Tap {i+1}: {delay_time_ms}ms at {gain_db}dB")

    # 5. Normalization: If the summing caused the signal to exceed 1.0, 
    # we scale it back down to prevent clipping.
    max_peak = np.max(np.abs(output_signal))
    if max_peak > 1.0:
        print(f"Normalization applied: Signal peaked at {20 * np.log10(max_peak):.2f} dB")
        output_signal = output_signal / max_peak
        
    return output_signal

# --- MAIN EXECUTION ---

# Configuration
input_filename = 'minecraft-firework.mp3'  
output_filename = 'multi_tap_output.wav'

# Define your 5 Custom Taps here
my_taps = [
    {'time_ms': 200,  'gain_db': -3.0}, 
    {'time_ms': 500,  'gain_db': -10.0},
    {'time_ms': 600, 'gain_db': -5.0},
    {'time_ms': 1000, 'gain_db': -10.0},
    {'time_ms': 1200, 'gain_db': -3.0}   
]

try:
    # Get absolute path to the folder where this script is saved
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, input_filename)
    output_path = os.path.join(script_dir, output_filename)

    # 1. Load Audio (Handles MP3 and WAV)
    print(f"Loading: {input_path}")
    data, fs = librosa.load(input_path, sr=None, mono=False)

    # 2. Handle Stereo
    if len(data.shape) > 1:
        print("Stereo file detected. Converting to Mono for processing...")
        data = librosa.to_mono(data)

    # 3. Process
    processed_audio = apply_multi_tap_delay(data, fs, my_taps, dry_mix=1.0)

    # 4. Save
    sf.write(output_path, processed_audio, fs)
    print(f"\nSUCCESS!")
    print(f"File saved to: {output_path}")

except Exception as e:
    print(f"\nERROR: {e}")