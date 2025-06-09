#!/usr/bin/env python3
"""
DALL-E Mobile Web App - Simple Version
Works on any phone with a browser!
"""
from flask import Flask, request, jsonify
import openai
import requests
import base64
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>DALL-E Mobile</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f0f0f0;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        input, textarea, select, button {
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            font-weight: bold;
            cursor: pointer;
        }
        button:disabled {
            background: #ccc;
        }
        #loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        #result img {
            width: 100%;
            border-radius: 8px;
            margin-top: 20px;
        }
        .error {
            color: red;
            margin-top: 10px;
        }
        .tip {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 DALL-E Mobile</h1>
        
        <input type="password" id="apiKey" placeholder="OpenAI API Key (sk-...)" />
        <div class="tip">Get from: platform.openai.com/api-keys</div>
        
        <select id="model">
            <option value="dall-e-2">DALL-E 2 (Fast & Cheap)</option>
            <option value="dall-e-3">DALL-E 3 (Best Quality)</option>
        </select>
        
        <textarea id="prompt" rows="4" placeholder="Describe the image you want..."></textarea>
        
        <button id="generateBtn" onclick="generateImage()">Generate Image</button>
        
        <div id="loading">
            <div class="spinner"></div>
            <p>Creating your image...</p>
        </div>
        
        <div id="error" class="error"></div>
        <div id="result"></div>
    </div>
    
    <script>
        // Load saved API key
        document.getElementById('apiKey').value = localStorage.getItem('dalleApiKey') || '';
        
        async function generateImage() {
            const apiKey = document.getElementById('apiKey').value;
            const model = document.getElementById('model').value;
            const prompt = document.getElementById('prompt').value;
            
            if (!apiKey || !prompt) {
                document.getElementById('error').textContent = 'Please enter API key and prompt';
                return;
            }
            
            // Save API key
            localStorage.setItem('dalleApiKey', apiKey);
            
            // UI state
            const btn = document.getElementById('generateBtn');
            const loading = document.getElementById('loading');
            const error = document.getElementById('error');
            const result = document.getElementById('result');
            
            btn.disabled = true;
            loading.style.display = 'block';
            error.textContent = '';
            result.innerHTML = '';
            
            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({apiKey, model, prompt})
                });
                
                const data = await response.json();
                
                if (data.error) {
                    error.textContent = 'Error: ' + data.error;
                } else {
                    result.innerHTML = '<img src="' + data.image + '" alt="Generated image" />';
                }
            } catch (e) {
                error.textContent = 'Network error: ' + e.message;
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
            }
        }
    </script>
</body>
</html>
    '''

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        client = openai.OpenAI(api_key=data['apiKey'])
        
        response = client.images.generate(
            model=data['model'],
            prompt=data['prompt'],
            size="1024x1024" if data['model'] == 'dall-e-3' else "512x512",
            n=1
        )
        
        return jsonify({'image': response.data[0].url})
        
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("\n🎨 DALL-E Mobile Web App")
    print("=" * 40)
    print("Starting server...")
    print("\nAccess from your phone:")
    print("1. Make sure phone is on same WiFi")
    print("2. Find your computer's IP address:")
    print("   - Windows: ipconfig")
    print("   - Linux/Mac: ifconfig or ip addr")
    print("3. On phone browser go to:")
    print("   http://YOUR-IP:5000")
    print("\nExample: http://192.168.1.100:5000")
    print("=" * 40)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
