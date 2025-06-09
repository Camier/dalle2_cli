#!/usr/bin/env python3
"""
DALL-E Web App - Works on any device with a browser
Mobile-friendly Progressive Web App (PWA)
"""
from flask import Flask, render_template, request, jsonify, send_file
import openai
import requests
import os
from pathlib import Path
from datetime import datetime
import base64
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Storage for generated images
UPLOAD_FOLDER = Path('static/generated')
UPLOAD_FOLDER.mkdir(exist_ok=True, parents=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        api_key = data.get('api_key')
        prompt = data.get('prompt')
        model = data.get('model', 'dall-e-2')
        
        if not api_key or not prompt:
            return jsonify({'error': 'Missing API key or prompt'}), 400
        
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Generate image
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size="1024x1024",
            n=1
        )
        
        # Download image
        image_url = response.data[0].url
        img_response = requests.get(image_url)
        
        if img_response.status_code == 200:
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{model}_{timestamp}.png"
            filepath = UPLOAD_FOLDER / filename
            
            with open(filepath, 'wb') as f:
                f.write(img_response.content)
            
            # Convert to base64 for immediate display
            img_base64 = base64.b64encode(img_response.content).decode()
            
            return jsonify({
                'success': True,
                'image': f"data:image/png;base64,{img_base64}",
                'filename': filename
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    return send_file(UPLOAD_FOLDER / filename, as_attachment=True)

if __name__ == '__main__':
    # Run on all interfaces for mobile access
    app.run(host='0.0.0.0', port=5000, debug=True)
