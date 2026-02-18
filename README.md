# Steganography Payload Embedder

Educational tools for embedding payloads into images using LSB (Least Significant Bit) steganography. This project contains two versions: a Desktop GUI and a Web Application.

## Disclaimer
**⚠ FOR EDUCATIONAL PURPOSES ONLY ⚠**
This tool is designed for security research and education. Use only in controlled environments with explicit authorization. Misuse may violate laws and ethical guidelines.

## Project Structure

### v1 - Desktop GUI
- **Path:** `v1/stgphy_v1.py`
- **Interface:** Python Tkinter
- **Features:**
  - Embed EXE, VBS, BAT payloads into images.
  - Extract payloads from stego images.
  - Generate test payloads and decoy files.

### v2 - Web Interface
- **Path:** `v2/stgphy_v2.py`
- **Interface:** Flask Web App
- **Features:**
  - Browser-based upload and embedding.
  - Automatic compression and encoding.
  - Downloadable stego images.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the desired version:
   ```bash
   # For GUI
   python v1/stgphy_v1.py
   ```