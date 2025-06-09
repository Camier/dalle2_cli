from flask import Flask, render_template, request, jsonify
import openai
import os
from pathlib import Path

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>DALL-E 2 Web Interface</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            input, button { padding: 10px; margin: 5px; }
            #result { margin-top: 20px; }
            img { max-width: 512px; margin: 10px; }
        </style>
    </head>
    <body>
        <h1>DALL-E 2 Image Generator</h1>
        <input type="text" id="apiKey" placeholder="OpenAI API Key" style="width: 300px;">
        <br>
        <input type="text" id="prompt" placeholder="Enter your prompt" style="width: 500px;">
        <button onclick="generateImage()">Generate</button>
        <div id="result"></div>
        
        <script>
            async function generateImage() {
                const apiKey = document.getElementById('apiKey').value;
                const prompt = document.getElementById('prompt').value;
                
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({api_key: apiKey, prompt: prompt})
                });
                
                const data = await response.json();
                if (data.images) {
                    document.getElementById('result').innerHTML = 
                        data.images.map(url => ).join('');
                } else {
                    document.getElementById('result').innerText = 'Error: ' + data.error;
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
        openai.api_key = data['api_key']
        
        response = openai.images.generate(
            model="dall-e-2",
            prompt=data['prompt'],
            size="512x512",
            n=1,
        )
        
        return jsonify({'images': [img.url for img in response.data]})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("Starting DALL-E 2 Web Interface...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
