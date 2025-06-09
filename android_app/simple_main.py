"""
DALL-E Mobile App - Simple Version
This creates a basic Android app for DALL-E image generation
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.network.urlrequest import UrlRequest
from kivy.clock import Clock
import json
import base64
from datetime import datetime

class DalleApp(App):
    def build(self):
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Title
        title = Label(
            text='DALL-E Mobile',
            size_hint_y=None,
            height=50,
            font_size='24sp'
        )
        main_layout.add_widget(title)
        
        # API Key input
        self.api_key_input = TextInput(
            hint_text='Enter OpenAI API key',
            multiline=False,
            password=True,
            size_hint_y=None,
            height=50
        )
        main_layout.add_widget(self.api_key_input)
        
        # Prompt input
        self.prompt_input = TextInput(
            hint_text='Describe the image you want...',
            multiline=True,
            size_hint_y=None,
            height=100
        )
        main_layout.add_widget(self.prompt_input)
        
        # Generate button
        generate_btn = Button(
            text='Generate Image',
            size_hint_y=None,
            height=50,
            background_color=(0.2, 0.6, 1, 1)
        )
        generate_btn.bind(on_press=self.generate_image)
        main_layout.add_widget(generate_btn)
        
        # Status label
        self.status_label = Label(
            text='Ready',
            size_hint_y=None,
            height=30
        )
        main_layout.add_widget(self.status_label)
        
        # Image display
        self.image_widget = Image(
            source='',
            allow_stretch=True
        )
        main_layout.add_widget(self.image_widget)
        
        # Load saved API key if exists
        try:
            with open('api_key.txt', 'r') as f:
                self.api_key_input.text = f.read().strip()
        except:
            pass
        
        return main_layout
    
    def generate_image(self, instance):
        api_key = self.api_key_input.text.strip()
        prompt = self.prompt_input.text.strip()
        
        if not api_key:
            self.show_popup('Error', 'Please enter your API key')
            return
        
        if not prompt:
            self.show_popup('Error', 'Please enter a prompt')
            return
        
        # Save API key
        with open('api_key.txt', 'w') as f:
            f.write(api_key)
        
        # Update status
        self.status_label.text = 'Generating...'
        
        # API request
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        data = json.dumps({
            'model': 'dall-e-2',
            'prompt': prompt,
            'n': 1,
            'size': '512x512'
        })
        
        req = UrlRequest(
            'https://api.openai.com/v1/images/generations',
            req_body=data,
            req_headers=headers,
            on_success=self.on_success,
            on_error=self.on_error,
            on_failure=self.on_error
        )
    
    def on_success(self, req, result):
        try:
            image_url = result['data'][0]['url']
            
            # Download and display image
            UrlRequest(
                image_url,
                on_success=self.display_image,
                file_path=f'dalle_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            )
            
            self.status_label.text = 'Image generated!'
        except Exception as e:
            self.status_label.text = f'Error: {str(e)}'
    
    def display_image(self, req, result):
        self.image_widget.source = req.file_path
        self.image_widget.reload()
    
    def on_error(self, req, error):
        self.status_label.text = 'Error generating image'
        if hasattr(req, 'result') and req.result:
            try:
                error_msg = json.loads(req.result)
                self.show_popup('Error', error_msg.get('error', {}).get('message', 'Unknown error'))
            except:
                self.show_popup('Error', 'Failed to generate image')
    
    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.8, 0.3)
        )
        popup.open()

if __name__ == '__main__':
    DalleApp().run()
