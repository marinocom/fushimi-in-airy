import numpy as np
from numba import njit

# this is the reverb formula file for the Fushimi In-Airy plugin's reverb section
# schroeder reverb algorithm 
# optimized for speed using Numba 


@njit
def allpass_filter(input_signal, delay_samples, gain):
    """
    numba-optimized allpass filter for reverb

    equation: y[n] = -g*x[n] + x[n-D] + g*y[n-D] 
    where g is the gain and D is the delay in samples

    """
    output = np.zeros(len(input_signal))
    buffer = np.zeros(delay_samples)
    buffer_idx = 0
    
    for i in range(len(input_signal)):
        # read from delay buffer
        delayed = buffer[buffer_idx]
        
        # allpass equation: y[n] = -g*x[n] + x[n-D] + g*y[n-D]
        output[i] = -gain * input_signal[i] + delayed
        
        # write to buffer: x[n] + g*y[n]
        buffer[buffer_idx] = input_signal[i] + gain * output[i]
        
        # increment buffer index (circular)
        buffer_idx = (buffer_idx + 1) % delay_samples
    
    return output

@njit
def comb_filter(input_signal, delay_samples, feedback_gain):
    """
    comb filter for reverb
    creates the initial echo density
    equation: y[n] = x[n] + g*y[n-D] 
    where g is the feedback gain and D is the delay in samples (y[n-D] is the delayed output)
    """
    output = np.zeros(len(input_signal))
    buffer = np.zeros(delay_samples)
    buffer_idx = 0
    
    for i in range(len(input_signal)):
        # read from delay buffer
        delayed = buffer[buffer_idx]
        
        # comb filter: y[n] = x[n] + g*y[n-D]
        output[i] = input_signal[i] + feedback_gain * delayed
        
        # write current output to buffer
        buffer[buffer_idx] = output[i]
        
        # increment buffer index (circular)
        buffer_idx = (buffer_idx + 1) % delay_samples
    
    return output

@njit
def parallel_comb_filters(input_signal, sample_rate, comb_delays_ms, feedback_gain):
    """
    apply multiple parallel comb filters (schroeder reverb first stage)
    equation: y[n] = x[n] + g*y[n-D] 
    where g is the feedback gain and D is the delay in samples (y[n-D] is the delayed output)
    """
    output = np.zeros(len(input_signal))
    
    for delay_ms in comb_delays_ms:
        delay_samples = int(sample_rate * delay_ms / 1000.0)
        if delay_samples > 0:
            filtered = comb_filter(input_signal, delay_samples, feedback_gain)
            output += filtered
    
    # average the parallel combs
    output = output / len(comb_delays_ms)
    return output

@njit
def serial_allpass_filters(input_signal, sample_rate, allpass_delays_ms, allpass_gain):
    """
    apply multiple serial allpass filters (schroeder reverb second stage)
    equation: y[n] = -g*x[n] + x[n-D] + g*y[n-D] 
    where g is the gain and D is the delay in samples
    """
    signal = input_signal.copy()
    
    for delay_ms in allpass_delays_ms:
        delay_samples = int(sample_rate * delay_ms / 1000.0)
        if delay_samples > 0:
            signal = allpass_filter(signal, delay_samples, allpass_gain)
    
    return signal

@njit
def apply_decay_envelope(signal, decay_time_samples):
    """
    apply exponential decay envelope to the reverb signal
    equation: y[n] = y[n] * decay_rate
    y[n] is the output signal
    """
    output = signal.copy()
    decay_rate = np.exp(-5.0 / decay_time_samples)  # decay to ~0.7% in decay_time
    
    envelope = 1.0
    for i in range(len(output)):
        output[i] *= envelope
        envelope *= decay_rate
    
    return output


def schroeder_reverb(input_signal, sample_rate, decay_time_ms, initial_gain=1.0):
    """
    schroeder reverb algorithm using parallel comb filters + serial allpass filters
    
    parameters:
    - input_signal: input audio array
    - sample_rate: sample rate in hz
    - decay_time_ms: reverb decay time in milliseconds
    - initial_gain: initial volume (0.0 to 1.0)

    equation: y[n] = x[n] + g*y[n-D] + g*y[n-2D] + g*y[n-3D] + ...
    """
    
    # schroeder's recommended comb filter delays (in ms) - slightly detuned to avoid metallic sound
    comb_delays = np.array([29.7, 37.1, 41.1, 43.7])
    
    # allpass filter delays (in ms)
    allpass_delays = np.array([5.0, 1.7])
    
    # calculate feedback gain based on desired decay time
    # rt60 formula: g = 10^(-3*D/(RT60*fs)) where D is delay in samples -> calculate the reverb in a room
    avg_comb_delay_samples = int(sample_rate * np.mean(comb_delays) / 1000.0)
    decay_time_sec = decay_time_ms / 1000.0
    feedback_gain = 10 ** (-3.0 * avg_comb_delay_samples / (decay_time_sec * sample_rate))
    feedback_gain = min(feedback_gain, 0.98)  # clamp to prevent instability
    
    allpass_gain = 0.7
    
    # apply initial gain to input
    scaled_input = input_signal * initial_gain
    
    # stage 1: parallel comb filters
    comb_output = parallel_comb_filters(scaled_input, sample_rate, comb_delays, feedback_gain)
    
    # stage 2: serial allpass filters
    reverb_output = serial_allpass_filters(comb_output, sample_rate, allpass_delays, allpass_gain)
    
    # apply decay envelope
    #decay_samples = int(sample_rate * decay_time_ms / 1000.0)
    #reverb_output = apply_decay_envelope(reverb_output, decay_samples)
    
    return reverb_output


def apply_multi_instance_reverb(input_signal, sample_rate, reverb_gates, dry_mix=1.0, tail_factor=0.0):
    """
    apply multiple independent reverb instances (torii gates) to the input signal.
    
    parameters:
    - input_signal: input audio array
    - sample_rate: sample rate in hz
    - reverb_gates: list of dicts with 'decay_ms' and 'gain_db' keys
    - dry_mix: dry signal mix level (0.0 to 1.0)
    - tail_factor: multiplier for tail length -> lower = shorter output, higher = longer reverb tail
    
    returns:
    - mixed output signal with reverbs
    """
    
    # calculate required buffer length
    # using tail_factor to control output length
    # default 0.4 means tail is 40% of the max decay time
    # (reverb naturally decays to inaudible levels before theoretical end)
    max_decay_ms = max([gate['decay_ms'] for gate in reverb_gates])
    tail_samples = int(sample_rate * (max_decay_ms / 1000.0) * tail_factor)
    
    total_length = len(input_signal) + tail_samples
    output_signal = np.zeros(total_length)
    
    # add dry signal
    output_signal[:len(input_signal)] += input_signal * dry_mix
    
    print(f"Applying {len(reverb_gates)} reverb instances...")
    
    for i, gate in enumerate(reverb_gates):
        decay_time_ms = gate['decay_ms']
        gain_db = gate['gain_db']
        
        # convert db to linear gain
        linear_gain = 10 ** (gain_db / 20.0)
        linear_gain = np.clip(linear_gain, 0.0, 1.0)  
        
        # generate reverb for this gate
        reverb_signal = schroeder_reverb(input_signal, sample_rate, decay_time_ms, linear_gain)
        
        # add to output (reverb starts immediately)
        end_idx = min(len(reverb_signal), total_length)
        output_signal[:end_idx] += reverb_signal[:end_idx]
        
        print(f" - Gate {i+1}: Decay={decay_time_ms}ms, Gain={gain_db}dB ({linear_gain*100:.1f}%)")
    
    # normalize to prevent clipping -> causes distortion if the signal is too big
    max_peak = np.max(np.abs(output_signal))
    if max_peak > 1.0:
        print(f"Normalization applied: Signal peaked at {20 * np.log10(max_peak):.2f} dB")
        output_signal = output_signal / max_peak
    
    return output_signal
