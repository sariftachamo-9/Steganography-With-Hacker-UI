import os
import struct
import base64
import zlib
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from PIL import Image
from werkzeug.utils import secure_filename
try:
    from js import Response, Headers
except ImportError:
    pass # Not running in Cloudflare Worker environment

app = Flask(__name__)
app.secret_key = 'super_secret_hacker_key'  # Required for flash messages

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Steganography Logic (Ported from v1) ---

def lsb_encode(image, data):
    """Encode data in image using Least Significant Bit steganography"""
    encoded = image.copy()
    width, height = image.size
    pixels = encoded.load()
    
    # Convert data to binary string
    binary_data = ''.join(format(byte, '08b') for byte in data)
    
    # Add end marker
    binary_data += '1111111111111110'  # 16-bit end marker
    
    data_len = len(binary_data)
    data_index = 0
    
    for y in range(height):
        for x in range(width):
            if data_index >= data_len:
                return encoded
            
            r, g, b = pixels[x, y][:3]
            
            # Modify LSB of each color channel
            if data_index < data_len:
                r = (r & ~1) | int(binary_data[data_index])
                data_index += 1
            if data_index < data_len:
                g = (g & ~1) | int(binary_data[data_index])
                data_index += 1
            if data_index < data_len:
                b = (b & ~1) | int(binary_data[data_index])
                data_index += 1
            
            pixels[x, y] = (r, g, b)
    
    return encoded

def lsb_decode(image):
    """Decode LSB hidden data from image"""
    width, height = image.size
    pixels = image.load()
    
    binary_data = ""
    
    for y in range(height):
        for x in range(width):
            try:
                r, g, b = pixels[x, y][:3]
            except Exception:
                continue
            binary_data += str(r & 1)
            binary_data += str(g & 1)
            binary_data += str(b & 1)

    # Find end marker
    end_marker = '1111111111111110'
    idx = binary_data.find(end_marker)
    if idx != -1:
        binary_data = binary_data[:idx]
    
    # Convert binary to bytes
    bytes_data = bytearray()
    for i in range(0, len(binary_data), 8):
        byte = binary_data[i:i+8]
        if len(byte) == 8:
            bytes_data.append(int(byte, 2))
            
    # Extract length and data
    if len(bytes_data) >= 4:
        length = struct.unpack('>I', bytes_data[:4])[0]
        if length + 4 <= len(bytes_data):
            return bytes(bytes_data[4:4+length])
    
    return None

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/embed', methods=['POST'])
def embed():
    if 'image' not in request.files or 'payload' not in request.files:
        flash("Missing image or payload file")
        return redirect(url_for('index'))
    
    image_file = request.files['image']
    payload_file = request.files['payload']
    
    if image_file.filename == '' or payload_file.filename == '':
        flash("No selected file")
        return redirect(url_for('index'))
        
    if image_file and allowed_file(image_file.filename):
        # Save uploaded image
        image_filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        image_file.save(image_path)
        
        # Read payload
        payload_data = payload_file.read()
        payload_name = secure_filename(payload_file.filename)
        payload_type = payload_name.split('.')[-1] if '.' in payload_name else 'dat'
        
        try:
            # Compress and Encode
            compressed = zlib.compress(payload_data)
            encoded_b64 = base64.b64encode(compressed).decode('ascii')
            
            # Metadata: STEGO_PAYLOAD:type:name:data
            metadata = f"STEGO_PAYLOAD:{payload_type}:{payload_name}:{encoded_b64}"
            metadata_bytes = metadata.encode('utf-8')
            
            # Header
            length = len(metadata_bytes)
            header = struct.pack('>I', length)
            data_to_hide = header + metadata_bytes
            
            # Process Image
            img = Image.open(image_path)
            # Ensure PNG for lossless
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            stego_image = lsb_encode(img, data_to_hide)
            
            # Save Output
            output_filename = f"stego_{os.path.splitext(image_filename)[0]}.png"
            output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
            stego_image.save(output_path, 'PNG')
            
            return render_template('result.html', 
                                   mode='embed',
                                   message="Payload Embedded Successfully!",
                                   filename=output_filename)
                                   
        except Exception as e:
            flash(f"Error embedding payload: {str(e)}")
            return redirect(url_for('index'))
            
    flash("Invalid file type")
    return redirect(url_for('index'))

@app.route('/extract', methods=['POST'])
def extract():
    if 'stego_image' not in request.files:
        flash("Missing stego image")
        return redirect(url_for('index'))
        
    stego_file = request.files['stego_image']
    
    if stego_file.filename == '':
        flash("No selected file")
        return redirect(url_for('index'))
        
    if stego_file and allowed_file(stego_file.filename):
        filename = secure_filename(stego_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        stego_file.save(filepath)
        
        try:
            img = Image.open(filepath)
            extracted_data = lsb_decode(img)
            
            if not extracted_data:
                raise ValueError("No hidden data found")
                
            metadata = extracted_data.decode('utf-8', errors='ignore')
            if not metadata.startswith("STEGO_PAYLOAD:"):
                raise ValueError("No valid payload found")
                
            _, p_type, p_name, encoded_data = metadata.split(':', 3)
            
            compressed = base64.b64decode(encoded_data)
            payload = zlib.decompress(compressed)
            
            output_filename = f"extracted_{p_name}"
            output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
            
            with open(output_path, 'wb') as f:
                f.write(payload)
                
            return render_template('result.html', 
                                   mode='extract',
                                   message=f"Payload Extracted: {p_name}",
                                   filename=output_filename)
                                   
        except Exception as e:
            flash(f"Error extracting payload: {str(e)}")
            return redirect(url_for('index'))
            
    flash("Invalid file type")
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['DOWNLOAD_FOLDER'], filename),
                     as_attachment=True)

if __name__ == '__main__':
    # Use PORT from environment for cloud deployment, default to 5678 for local
    port = int(os.environ.get('PORT', 5678))
    app.run(debug=True, host='0.0.0.0', port=port)

# Cloudflare Workers Handler
async def on_fetch(request, env):
    with app.test_client() as client:
        # Convert Cloudflare request to Flask request
        method = request.method
        url = request.url
        headers = {k: v for k, v in request.headers.items()}
        
        # Handle body if present
        body = await request.arrayBuffer()
        data = body.to_py().tobytes() if body else None
        
        response = client.open(url, method=method, headers=headers, data=data)
        
        # Convert Flask response to Cloudflare Response
        cf_headers = Headers.new()
        for k, v in response.headers.items():
            cf_headers.append(k, str(v))
            
        return Response.new(response.data, status=response.status_code, headers=cf_headers)