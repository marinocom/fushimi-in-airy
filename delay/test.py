import os
import numpy as np
from scipy.io import wavfile

import numpy as np

def apply_multi_tap_delay(input_signal, sample_rate, taps, dry_mix=1.0):
    """
    :param taps: A list of dicts, e.g., [{'time_ms': 20, 'gain_db': -6}, ...]
    :param dry_mix: Volume of the original unaffected signal (0.0 to 1.0)
    """
    # 1. Find the longest delay to determine the tail length
    max_delay_ms = max([tap['time_ms'] for tap in taps])
    tail_samples = int(sample_rate * (max_delay_ms / 1000.0) + (sample_rate * 0.5))
    
    # 2. Prepare the output buffer
    output_signal = np.zeros(len(input_signal) + tail_samples)
    
    # 3. Add the DRY signal first
    output_signal[:len(input_signal)] += input_signal * dry_mix
    
    # 4. Process each TAP
    for tap in taps:
        delay_time_ms = tap['time_ms']
        gain_db = tap['gain_db']
        
        # Convert dB to Linear Gain (Logic: 0dB = 1.0, -6dB ≈ 0.5)
        # Formula: linear = 10^(db/20)
        linear_gain = 10**(gain_db / 20)
        
        delay_samples = int(sample_rate * (delay_time_ms / 1000.0))
        
        # Create the 'Wet' version for this specific tap
        # We shift the input signal by delay_samples and multiply by gain
        start = delay_samples
        end = start + len(input_signal)
        
        # Add this tap's contribution to the output
        output_signal[start:end] += input_signal * linear_gain

    # 5. Final Normalization to prevent digital clipping
    if np.max(np.abs(output_signal)) > 1.0:
        output_signal = output_signal / np.max(np.abs(output_signal))
        
    return output_signal

# --- HOW TO USE IT ---

my_taps = [
    {'time_ms': 20,  'gain_db': -12}, # 0.5dB in your prompt is very loud/clipping! 
    {'time_ms': 50,  'gain_db': -10}, # I used negative dB for safety (standard for delay taps)
    {'time_ms': 100, 'gain_db': -6},
    {'time_ms': 110, 'gain_db': -10},
    {'time_ms': 250, 'gain_db': -3}
]

# processed_audio = apply_multi_tap_delay(data, fs, my_taps, dry_mix=1.0)


# ... (keep your apply_delay function exactly as it is) ...

# 1. Define your file path
# Since your script is in "fushimi in airy", put your wav file there too!
script_dir = os.path.dirname(os.path.abspath(__file__))
input_filename = 'guitar_1.wav'  # <--- CHANGE THIS to your filename ------------------------------------------------------------------------------------------------------------------------
input_path = os.path.join(script_dir, input_filename)
output_path = os.path.join(script_dir, 'delayed_output.wav')

# 2. Load the audio
fs, data = wavfile.read(input_path)

# 3. Convert to Float32 and Normalize
# SciPy often loads wavs as integers; we need floats between -1.0 and 1.0 for DSP
if data.dtype == np.int16:
    data = data.astype(np.float32) / 32768.0
elif data.dtype == np.int32:
    data = data.astype(np.float32) / 2147483648.0

# 4. Handle Stereo (Process Left and Right separately or mix to Mono)
if len(data.shape) > 1:
    print("Stereo file detected. Converting to Mono for processing...")
    data = data.mean(axis=1)

# 5. Apply the effect
print(f"Processing '{input_filename}'...")
processed_audio = apply_delay(data, fs, delay_ms=500, feedback=0.2, dry_wet=0.2)

# 6. Save the result
# Convert back to 16-bit integer so your Mac can play it easily
output_data = (processed_audio * 32767).astype(np.int16)
wavfile.write(output_path, fs, output_data)

print(f"Success! Listen to: {output_path}")


