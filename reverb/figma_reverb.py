import numpy as np

def figma_to_reverb_params(x_pos, y_pos, frame_width, frame_height, 
                           max_decay_ms=10000, max_gain_db=0, min_gain_db=-60):
    """
    Convert Figma X/Y coordinates to reverb parameters.
    
    Based on the PDF specification:
    - X-axis (horizontal): Decay time (0 to 10,000ms)
    - Y-axis (vertical): Volume/Attack (0% to 100% of dry signal)
    
    Parameters:
    - x_pos: X position in Figma (0 = left edge)
    - y_pos: Y position in Figma (0 = top edge)
    - frame_width: Width of the Figma frame
    - frame_height: Height of the Figma frame
    - max_decay_ms: Maximum decay time in milliseconds (default 10000)
    - max_gain_db: Maximum gain in dB (default 0 dB = 100%)
    - min_gain_db: Minimum gain in dB (default -60 dB ≈ 0.1%)
    
    Returns:
    - dict with 'decay_ms' and 'gain_db'
    """
    
    # Normalize positions to 0-1 range
    x_norm = np.clip(x_pos / frame_width, 0.0, 1.0)
    y_norm = np.clip(y_pos / frame_height, 0.0, 1.0)
    
    # X-axis: Map to decay time (0 to max_decay_ms)
    decay_ms = x_norm * max_decay_ms
    
    # Y-axis: Map to gain in dB
    # In Figma, Y=0 is TOP (high volume), Y=height is BOTTOM (low volume)
    # So we need to invert: (1 - y_norm) gives us bottom=0%, top=100%
    volume_percent = (1.0 - y_norm) * 100.0  # 0% to 100%
    
    # Convert percentage to dB
    # 100% = 0 dB, 0% = -∞ dB (we use -60 dB as practical minimum)
    if volume_percent <= 0.1:
        gain_db = min_gain_db
    else:
        # Linear percentage to dB: dB = 20*log10(percent/100)
        gain_db = 20 * np.log10(volume_percent / 100.0)
        gain_db = np.clip(gain_db, min_gain_db, max_gain_db)
    
    return {
        'decay_ms': decay_ms,
        'gain_db': gain_db
    }


def load_reverb_gates_from_figma(json_file, frame_width, frame_height):
    """
    Load reverb gate parameters from a Figma export JSON file.
    
    Parameters:
    - json_file: Path to the exported Figma JSON
    - frame_width: Width of the Figma artboard/frame
    - frame_height: Height of the Figma artboard/frame
    
    Returns:
    - List of reverb gate dicts with 'decay_ms' and 'gain_db'
    """
    import json
    
    with open(json_file) as f:
        data = json.load(f)
    
    reverb_gates = []
    
    # Assuming the JSON exports layer names and their x/y positions
    # Adjust the structure based on your actual Figma export format
    for layer in data.get('layers', []):
        # Look for layers named "Torii" or "Gate" or similar
        if any(keyword in layer.get('name', '') for keyword in ['Torii', 'Gate', 'Reverb']):
            x = layer.get('x', 0)
            y = layer.get('y', 0)
            
            params = figma_to_reverb_params(x, y, frame_width, frame_height)
            reverb_gates.append(params)
    
    return reverb_gates


# Example usage and testing
if __name__ == "__main__":
    # Test the conversion with example coordinates
    frame_w = 1000  # Example Figma frame width
    frame_h = 800   # Example Figma frame height
    
    print("Testing Figma to Reverb Parameter Conversion:")
    print("=" * 60)
    
    # Test cases representing different positions on the mountain
    test_positions = [
        ("Top-left (short decay, loud)", 100, 100),
        ("Top-right (long decay, loud)", 900, 100),
        ("Bottom-left (short decay, quiet)", 100, 700),
        ("Bottom-right (long decay, quiet)", 900, 700),
        ("Center (medium decay, medium volume)", 500, 400),
    ]
    
    for name, x, y in test_positions:
        params = figma_to_reverb_params(x, y, frame_w, frame_h)
        volume_percent = 10 ** (params['gain_db'] / 20.0) * 100
        print(f"\n{name}:")
        print(f"  Position: ({x}, {y})")
        print(f"  Decay: {params['decay_ms']:.0f}ms")
        print(f"  Gain: {params['gain_db']:.1f}dB (~{volume_percent:.1f}%)")