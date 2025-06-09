import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageTk
import json
import subprocess
import sys

from ...data.database import DatabaseManager, GenerationRecord
from ...core.config_manager import ConfigManager
from ...utils.logger import logger


class ImageCard(ctk.CTkFrame):
    def __init__(self, parent, record: GenerationRecord, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.record = record
        self.image_path = Path(record.image_path)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Load and display image thumbnail
        try:
            if self.image_path.exists():
                pil_image = Image.open(self.image_path)
                pil_image.thumbnail((150, 150), Image.Resampling.LANCZOS)
                
                self.ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, 
                                             size=pil_image.size)
                
                self.image_label = ctk.CTkLabel(self, image=self.ctk_image, text="")
                self.image_label.pack(padx=5, pady=5)
            else:
                self.image_label = ctk.CTkLabel(self, text="Image\nNot Found", 
                                               width=150, height=150)
                self.image_label.pack(padx=5, pady=5)
        except Exception as e:
            self.image_label = ctk.CTkLabel(self, text="Error\nLoading", 
                                           width=150, height=150)
            self.image_label.pack(padx=5, pady=5)
        
        # Info frame
        info_frame = ctk.CTkFrame(self)
        info_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        # Prompt (truncated)
        prompt_text = self.record.prompt[:40] + "..." if len(self.record.prompt) > 40 else self.record.prompt
        prompt_label = ctk.CTkLabel(info_frame, text=prompt_text, 
                                   font=ctk.CTkFont(size=10), wraplength=140)
        prompt_label.pack(pady=2)
        
        # Generation info
        metadata = {}
        try:
            metadata = json.loads(self.record.metadata) if self.record.metadata else {}
        except:
            pass
        
        info_text = f"{self.record.generation_type.capitalize()}\n{self.record.size}\n${self.record.cost:.4f}"
        info_label = ctk.CTkLabel(info_frame, text=info_text, 
                                 font=ctk.CTkFont(size=9), text_color="gray")
        info_label.pack(pady=2)
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        # View button
        view_btn = ctk.CTkButton(buttons_frame, text="View", width=60, height=25,
                                font=ctk.CTkFont(size=10),
                                command=self.view_image)
        view_btn.pack(side="left", padx=2)
        
        # Save As button
        save_btn = ctk.CTkButton(buttons_frame, text="Save", width=60, height=25,
                                font=ctk.CTkFont(size=10),
                                command=self.save_image)
        save_btn.pack(side="right", padx=2)
    
    def view_image(self):
        if not self.image_path.exists():
            messagebox.showerror("Error", "Image file not found")
            return
        
        try:
            if sys.platform == "win32":
                subprocess.run(["start", str(self.image_path)], shell=True)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self.image_path)])
            else:
                subprocess.run(["xdg-open", str(self.image_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open image: {e}")
    
    def save_image(self):
        if not self.image_path.exists():
            messagebox.showerror("Error", "Image file not found")
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Save Image As",
            defaultextension=self.image_path.suffix,
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ],
            initialname=self.image_path.name
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(self.image_path, save_path)
                messagebox.showinfo("Success", f"Image saved to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")


class GalleryTab(ctk.CTkFrame):
    def __init__(self, parent, db_manager: DatabaseManager, config_manager: ConfigManager):
        super().__init__(parent)
        
        self.db_manager = db_manager
        self.config_manager = config_manager
        
        self.current_records = []
        self.current_page = 0
        self.records_per_page = 20
        
        self.create_widgets()
        self.load_images()
    
    def create_widgets(self):
        # Top controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.pack(fill="x", padx=10, pady=10)
        
        # Search
        search_frame = ctk.CTkFrame(controls_frame)
        search_frame.pack(side="left", padx=10, pady=10)
        
        search_label = ctk.CTkLabel(search_frame, text="Search:")
        search_label.pack(side="left", padx=5)
        
        self.search_entry = ctk.CTkEntry(search_frame, width=200, 
                                        placeholder_text="Search prompts...")
        self.search_entry.pack(side="left", padx=5)
        
        search_btn = ctk.CTkButton(search_frame, text="Search", width=80,
                                  command=self.search_images)
        search_btn.pack(side="left", padx=5)
        
        clear_btn = ctk.CTkButton(search_frame, text="Clear", width=60,
                                 command=self.clear_search)
        clear_btn.pack(side="left", padx=2)
        
        # Filters
        filter_frame = ctk.CTkFrame(controls_frame)
        filter_frame.pack(side="right", padx=10, pady=10)
        
        type_label = ctk.CTkLabel(filter_frame, text="Type:")
        type_label.pack(side="left", padx=5)
        
        self.type_filter = ctk.CTkComboBox(filter_frame, 
                                          values=["All", "generation", "variation", "edit", "batch"],
                                          command=self.filter_changed, width=120)
        self.type_filter.set("All")
        self.type_filter.pack(side="left", padx=5)
        
        size_label = ctk.CTkLabel(filter_frame, text="Size:")
        size_label.pack(side="left", padx=5)
        
        self.size_filter = ctk.CTkComboBox(filter_frame,
                                          values=["All", "1024x1024", "1024x1792", "1792x1024", "512x512", "256x256"],
                                          command=self.filter_changed, width=120)
        self.size_filter.set("All")
        self.size_filter.pack(side="left", padx=5)
        
        # Stats
        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.stats_label = ctk.CTkLabel(stats_frame, text="Loading statistics...")
        self.stats_label.pack(pady=10)
        
        # Navigation
        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.prev_btn = ctk.CTkButton(nav_frame, text="Previous", width=100,
                                     command=self.previous_page, state="disabled")
        self.prev_btn.pack(side="left", padx=10, pady=5)
        
        self.page_label = ctk.CTkLabel(nav_frame, text="Page 1 of 1")
        self.page_label.pack(side="left", expand=True)
        
        self.next_btn = ctk.CTkButton(nav_frame, text="Next", width=100,
                                     command=self.next_page, state="disabled")
        self.next_btn.pack(side="right", padx=10, pady=5)
        
        # Gallery grid
        self.gallery_scroll = ctk.CTkScrollableFrame(self, height=400)
        self.gallery_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Configure grid columns
        self.gallery_scroll.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
    
    def load_images(self, search_query: str = "", type_filter: str = "All", size_filter: str = "All"):
        try:
            # Get records based on filters
            if search_query:
                records = self.db_manager.search_generations(search_query, limit=1000)
            else:
                records = self.db_manager.get_generations(limit=1000)
            
            # Apply filters
            if type_filter != "All":
                records = [r for r in records if r.generation_type == type_filter]
            
            if size_filter != "All":
                records = [r for r in records if r.size == size_filter]
            
            self.current_records = records
            self.current_page = 0
            
            # Update stats
            self.update_stats()
            
            # Display current page
            self.display_page()
            
        except Exception as e:
            logger.error(f"Error loading images: {e}")
            messagebox.showerror("Error", f"Failed to load images: {e}")
    
    def display_page(self):
        # Clear current display
        for widget in self.gallery_scroll.winfo_children():
            widget.destroy()
        
        # Calculate page bounds
        start_idx = self.current_page * self.records_per_page
        end_idx = min(start_idx + self.records_per_page, len(self.current_records))
        
        if start_idx >= len(self.current_records):
            # No records to display
            no_images_label = ctk.CTkLabel(self.gallery_scroll, 
                                          text="No images found", 
                                          font=ctk.CTkFont(size=16))
            no_images_label.grid(row=0, column=0, columnspan=5, pady=50)
            return
        
        # Display images in grid
        records_to_show = self.current_records[start_idx:end_idx]
        
        for i, record in enumerate(records_to_show):
            row = i // 5
            col = i % 5
            
            try:
                image_card = ImageCard(self.gallery_scroll, record, width=160, height=220)
                image_card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            except Exception as e:
                logger.error(f"Error creating image card: {e}")
        
        # Update navigation
        self.update_navigation()
    
    def update_stats(self):
        try:
            stats = self.db_manager.get_generation_stats()
            
            total_images = len(self.current_records)
            total_cost = sum(r.cost for r in self.current_records)
            
            if self.current_records:
                avg_cost = total_cost / len(self.current_records)
                stats_text = f"Showing {total_images} images | Total cost: ${total_cost:.4f} | Average: ${avg_cost:.4f}"
            else:
                stats_text = "No images found"
            
            self.stats_label.configure(text=stats_text)
            
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
            self.stats_label.configure(text="Error loading statistics")
    
    def update_navigation(self):
        total_pages = (len(self.current_records) + self.records_per_page - 1) // self.records_per_page
        total_pages = max(1, total_pages)
        
        # Update page label
        self.page_label.configure(text=f"Page {self.current_page + 1} of {total_pages}")
        
        # Update button states
        self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")
    
    def search_images(self):
        query = self.search_entry.get().strip()
        type_filter = self.type_filter.get()
        size_filter = self.size_filter.get()
        
        self.load_images(query, type_filter, size_filter)
    
    def clear_search(self):
        self.search_entry.delete(0, 'end')
        self.type_filter.set("All")
        self.size_filter.set("All")
        self.load_images()
    
    def filter_changed(self, value=None):
        # Auto-apply filters when changed
        self.search_images()
    
    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()
    
    def next_page(self):
        total_pages = (len(self.current_records) + self.records_per_page - 1) // self.records_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.display_page()
    
    def refresh_gallery(self):
        """Refresh the gallery to show new images"""
        current_query = self.search_entry.get().strip()
        type_filter = self.type_filter.get()
        size_filter = self.size_filter.get()
        
        self.load_images(current_query, type_filter, size_filter)