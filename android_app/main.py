#!/usr/bin/env python3
"""
DALL-E Android App - Kivy Implementation
"""
import os
import sys
from pathlib import Path
import json
import requests
from datetime import datetime
import threading

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.utils import platform

# KivyMD for better UI
from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.list import OneLineListItem, MDList
from kivymd.uix.dialog import MDDialog
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.menu import MDDropdownMenu

import openai

# Platform specific imports
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    STORAGE_PATH = Path(primary_external_storage_path()) / "DALLE"
else:
    STORAGE_PATH = Path.home() / ".dalle_mobile"

STORAGE_PATH.mkdir(exist_ok=True)

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = None
        self.client = None
        self.setup_ui()
        self.load_api_key()
        
    def setup_ui(self):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Title
        title = MDLabel(
            text='DALL-E Mobile',
            theme_text_color='Primary',
            size_hint_y=None,
            height=50,
            font_style='H4',
            halign='center'
        )
        layout.add_widget(title)
        
        # Menu buttons
        btn_generate = MDRaisedButton(
            text='Generate Image',
            size_hint=(1, None),
            height=50,
            on_release=self.go_to_generate
        )
        layout.add_widget(btn_generate)
        
        btn_variations = MDRaisedButton(
            text='Create Variations',
            size_hint=(1, None),
            height=50,
            on_release=self.go_to_variations
        )
        layout.add_widget(btn_variations)
        
        btn_history = MDRaisedButton(
            text='View History',
            size_hint=(1, None),
            height=50,
            on_release=self.go_to_history
        )
        layout.add_widget(btn_history)
        
        btn_settings = MDRaisedButton(
            text='Settings',
            size_hint=(1, None),
            height=50,
            on_release=self.go_to_settings
        )
        layout.add_widget(btn_settings)
        
        # Add spacing
        layout.add_widget(Label())
        
        self.add_widget(layout)
    
    def load_api_key(self):
        key_file = STORAGE_PATH / "api_key.txt"
        if key_file.exists():
            self.api_key = key_file.read_text().strip()
            self.client = openai.OpenAI(api_key=self.api_key)
    
    def go_to_generate(self, instance):
        if not self.api_key:
            self.show_api_key_dialog()
        else:
            self.manager.current = 'generate'
    
    def go_to_variations(self, instance):
        if not self.api_key:
            self.show_api_key_dialog()
        else:
            self.manager.current = 'variations'
    
    def go_to_history(self, instance):
        self.manager.current = 'history'
    
    def go_to_settings(self, instance):
        self.manager.current = 'settings'
    
    def show_api_key_dialog(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        label = MDLabel(text='Enter your OpenAI API key:')
        content.add_widget(label)
        
        self.api_key_input = MDTextField(
            hint_text='sk-...',
            password=True,
            size_hint_y=None,
            height=40
        )
        content.add_widget(self.api_key_input)
        
        self.dialog = MDDialog(
            title='API Key Required',
            type='custom',
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text='CANCEL',
                    on_release=lambda x: self.dialog.dismiss()
                ),
                MDRaisedButton(
                    text='SAVE',
                    on_release=self.save_api_key
                )
            ]
        )
        self.dialog.open()
    
    def save_api_key(self, instance):
        api_key = self.api_key_input.text.strip()
        if api_key:
            key_file = STORAGE_PATH / "api_key.txt"
            key_file.write_text(api_key)
            self.api_key = api_key
            self.client = openai.OpenAI(api_key=api_key)
            self.dialog.dismiss()
            self.show_message("API key saved!")

    def show_message(self, message):
        dialog = MDDialog(
            text=message,
            buttons=[
                MDFlatButton(
                    text='OK',
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()

class GenerateScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setup_ui()
        
    def setup_ui(self):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Back button
        back_btn = MDFlatButton(
            text='< Back',
            on_release=lambda x: setattr(self.manager, 'current', 'main')
        )
        layout.add_widget(back_btn)
        
        # Title
        title = MDLabel(
            text='Generate Image',
            theme_text_color='Primary',
            size_hint_y=None,
            height=40,
            font_style='H5'
        )
        layout.add_widget(title)
        
        # Prompt input
        self.prompt_input = MDTextField(
            hint_text='Enter your prompt...',
            multiline=True,
            size_hint_y=None,
            height=100
        )
        layout.add_widget(self.prompt_input)
        
        # Model selection
        model_layout = BoxLayout(size_hint_y=None, height=50)
        model_layout.add_widget(MDLabel(text='Model:'))
        
        self.model_dalle2 = MDCheckbox(
            group='model',
            active=True,
            size_hint=(None, None),
            size=(48, 48)
        )
        model_layout.add_widget(self.model_dalle2)
        model_layout.add_widget(MDLabel(text='DALL-E 2'))
        
        self.model_dalle3 = MDCheckbox(
            group='model',
            size_hint=(None, None),
            size=(48, 48)
        )
        model_layout.add_widget(self.model_dalle3)
        model_layout.add_widget(MDLabel(text='DALL-E 3'))
        
        layout.add_widget(model_layout)
        
        # Generate button
        generate_btn = MDRaisedButton(
            text='Generate',
            size_hint=(1, None),
            height=50,
            on_release=self.generate_image
        )
        layout.add_widget(generate_btn)
        
        # Loading spinner
        self.spinner = MDSpinner(
            size_hint=(None, None),
            size=(46, 46),
            pos_hint={'center_x': 0.5},
            active=False
        )
        layout.add_widget(self.spinner)
        
        # Result image
        self.result_image = KivyImage(
            source='',
            size_hint=(1, 1),
            allow_stretch=True
        )
        layout.add_widget(self.result_image)
        
        self.add_widget(layout)
    
    def generate_image(self, instance):
        prompt = self.prompt_input.text.strip()
        if not prompt:
            self.show_error("Please enter a prompt")
            return
        
        # Show loading
        self.spinner.active = True
        instance.disabled = True
        
        # Generate in thread
        thread = threading.Thread(
            target=self._generate_thread,
            args=(prompt, instance)
        )
        thread.start()
    
    def _generate_thread(self, prompt, button):
        try:
            main_screen = self.manager.get_screen('main')
            client = main_screen.client
            
            model = "dall-e-2" if self.model_dalle2.active else "dall-e-3"
            
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size="1024x1024",
                n=1
            )
            
            # Download image
            image_url = response.data[0].url
            resp = requests.get(image_url)
            
            if resp.status_code == 200:
                # Save image
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = STORAGE_PATH / f"{model}_{timestamp}.png"
                
                with open(filename, 'wb') as f:
                    f.write(resp.content)
                
                # Update UI on main thread
                from kivy.clock import Clock
                Clock.schedule_once(
                    lambda dt: self._update_ui(str(filename), button),
                    0
                )
            
        except Exception as e:
            from kivy.clock import Clock
            Clock.schedule_once(
                lambda dt: self.show_error(str(e), button),
                0
            )
    
    def _update_ui(self, filename, button):
        self.spinner.active = False
        button.disabled = False
        self.result_image.source = filename
        self.result_image.reload()
        self.show_success("Image generated!")
    
    def show_error(self, message, button=None):
        if button:
            button.disabled = False
        self.spinner.active = False
        
        dialog = MDDialog(
            text=f"Error: {message}",
            buttons=[
                MDFlatButton(
                    text='OK',
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()
    
    def show_success(self, message):
        dialog = MDDialog(
            text=message,
            buttons=[
                MDFlatButton(
                    text='OK',
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()

class DalleMobileApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        
        # Request permissions on Android
        if platform == 'android':
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])
        
        # Create screen manager
        sm = ScreenManager()
        
        # Add screens
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(GenerateScreen(name='generate'))
        # Add more screens for variations, history, settings...
        
        return sm

if __name__ == '__main__':
    DalleMobileApp().run()
