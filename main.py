import tkinter as tk
from tkinter import filedialog
import pygame
from pygame import mixer
import os
import random
import json
from datetime import timedelta
from mutagen import File
import pystray
from PIL import Image, ImageDraw
import threading

class ModernMusicPlayer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Modern Music Player")
        self.geometry("900x600")
        self.minsize(900, 600)
        self.configure(bg='#2d2d2d')
        
        # Initialize variables
        self.supported_formats = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
        self.playlist_items = []
        self.current_track_index = -1
        self.is_playing = False
        self.is_shuffled = False
        self.repeat_mode = 0  # 0: No repeat, 1: Repeat track, 2: Repeat playlist
        self.current_directory = None
        
        # Initialize pygame mixer
        pygame.init()
        mixer.init()
        mixer.music.set_endevent(pygame.USEREVENT)
        
        # Setup UI
        self.setup_ui()
        self.setup_tray()
        self.load_settings()
        
        # Start position update timer
        self.update_progress()

    def setup_ui(self):
        main_frame = tk.Frame(self, bg='#2d2d2d')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Playlist
        self.playlist = tk.Listbox(main_frame, bg='#1a1a1a', fg='white', 
                                 font=('Arial', 12), selectbackground='#404040')
        self.playlist.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.playlist.bind('<Double-Button-1>', self.playlist_double_clicked)

        # Progress controls
        time_frame = tk.Frame(main_frame, bg='#2d2d2d')
        time_frame.pack(fill=tk.X, padx=5, pady=5)

        self.current_time = tk.Label(time_frame, text="00:00", bg='#2d2d2d', fg='white')
        self.current_time.pack(side=tk.LEFT)

        self.progress_slider = tk.Scale(time_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                      bg='#404040', troughcolor='#404040', 
                                      highlightbackground='#2d2d2d', sliderrelief='flat')
        self.progress_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_slider.bind("<ButtonRelease-1>", self.seek_position)

        self.total_time = tk.Label(time_frame, text="00:00", bg='#2d2d2d', fg='white')
        self.total_time.pack(side=tk.RIGHT)

        # Control buttons
        controls_frame = tk.Frame(main_frame, bg='#2d2d2d')
        controls_frame.pack(pady=5)

        button_style = {
            'bg': '#404040', 
            'fg': 'white', 
            'activebackground': '#505050',
            'borderwidth': 0,
            'highlightthickness': 0
        }

        self.shuffle_btn = tk.Button(controls_frame, text="Shuffle", **button_style,
                                    command=self.toggle_shuffle)
        self.shuffle_btn.pack(side=tk.LEFT, padx=2)

        self.prev_btn = tk.Button(controls_frame, text="Prev", **button_style,
                                command=self.play_previous)
        self.prev_btn.pack(side=tk.LEFT, padx=2)

        self.play_btn = tk.Button(controls_frame, text="Play", **button_style,
                                command=self.toggle_playback)
        self.play_btn.pack(side=tk.LEFT, padx=2)

        self.next_btn = tk.Button(controls_frame, text="Next", **button_style,
                                command=self.play_next)
        self.next_btn.pack(side=tk.LEFT, padx=2)

        self.repeat_btn = tk.Button(controls_frame, text="Repeat", **button_style,
                                  command=self.toggle_repeat)
        self.repeat_btn.pack(side=tk.LEFT, padx=2)

        # Volume control
        volume_frame = tk.Frame(main_frame, bg='#2d2d2d')
        volume_frame.pack(pady=5)

        self.volume_slider = tk.Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                    bg='#404040', troughcolor='#404040',
                                    command=self.set_volume)
        self.volume_slider.set(50)
        self.volume_slider.pack(side=tk.RIGHT, padx=5)

        tk.Label(volume_frame, text="Vol:", bg='#2d2d2d', fg='white').pack(side=tk.RIGHT)

        # Menu bar
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0, bg='#404040', fg='white')
        file_menu.add_command(label="Open Directory", command=self.open_directory)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

        # Status bar
        self.status_bar = tk.Label(self, text="Ready", bg='#404040', fg='white', anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_tray(self):
        def create_image():
            image = Image.new('RGB', (16, 16), 'black')
            draw = ImageDraw.Draw(image)
            draw.ellipse((0, 0, 15, 15), fill='green')
            return image

        menu = pystray.Menu(
            pystray.MenuItem('Play/Pause', lambda: self.after(0, self.toggle_playback)),
            pystray.MenuItem('Next', lambda: self.after(0, self.play_next)),
            pystray.MenuItem('Quit', lambda: self.after(0, self.quit_app))
        )

        self.tray_icon = pystray.Icon("music_player", create_image(), "Music Player", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def load_settings(self):
        try:
            if os.path.exists('player_settings.json'):
                with open('player_settings.json', 'r') as f:
                    settings = json.load(f)
                    self.volume_slider.set(settings.get('volume', 50))
                    mixer.music.set_volume(settings['volume'] / 100)
                    last_dir = settings.get('last_directory')
                    if last_dir and os.path.exists(last_dir):
                        self.load_directory(last_dir)
        except Exception as e:
            self.status_bar.config(text=f"Error loading settings: {str(e)}")

    def save_settings(self):
        settings = {
            'volume': self.volume_slider.get(),
            'last_directory': self.current_directory or ''
        }
        try:
            with open('player_settings.json', 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            self.status_bar.config(text=f"Error saving settings: {str(e)}")

    def open_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.load_directory(directory)

    def load_directory(self, directory):
        self.current_directory = directory
        self.playlist.delete(0, tk.END)
        self.playlist_items.clear()
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(self.supported_formats):
                    path = os.path.join(root, file)
                    self.playlist_items.append(path)
                    self.playlist.insert(tk.END, os.path.basename(file))

    def toggle_playback(self):
        if self.is_playing:
            mixer.music.pause()
            self.is_playing = False
            self.play_btn.config(text="Play")
        else:
            if self.current_track_index == -1 and self.playlist_items:
                self.current_track_index = 0
                self.play_track(0)
            else:
                mixer.music.unpause()
                self.is_playing = True
                self.play_btn.config(text="Pause")

    def play_track(self, index):
        if 0 <= index < len(self.playlist_items):
            self.current_track_index = index
            self.playlist.selection_clear(0, tk.END)
            self.playlist.selection_set(index)
            self.playlist.see(index)
            
            track_path = self.playlist_items[index]
            try:
                mixer.music.load(track_path)
                mixer.music.play()
                self.is_playing = True
                self.play_btn.config(text="Pause")
                
                # Get track duration
                audio = File(track_path)
                duration = int(audio.info.length * 1000)  # Convert to milliseconds
                self.progress_slider.config(to=duration)
                self.total_time.config(text=str(timedelta(seconds=int(audio.info.length)))[:-3])
            except Exception as e:
                self.status_bar.config(text=f"Error playing track: {str(e)}")

    def play_next(self):
        if self.playlist_items:
            if self.is_shuffled:
                self.current_track_index = random.randint(0, len(self.playlist_items)-1)
            else:
                self.current_track_index = (self.current_track_index + 1) % len(self.playlist_items)
            self.play_track(self.current_track_index)

    def play_previous(self):
        if self.playlist_items:
            if self.is_shuffled:
                self.current_track_index = random.randint(0, len(self.playlist_items)-1)
            else:
                self.current_track_index = (self.current_track_index - 1) % len(self.playlist_items)
            self.play_track(self.current_track_index)

    def toggle_shuffle(self):
        self.is_shuffled = not self.is_shuffled
        self.shuffle_btn.config(bg='#606060' if self.is_shuffled else '#404040')

    def toggle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        colors = ['#404040', '#606060', '#808080']
        self.repeat_btn.config(bg=colors[self.repeat_mode])

    def set_volume(self, val):
        mixer.music.set_volume(float(val) / 100)

    def seek_position(self, event):
        pos = self.progress_slider.get()
        mixer.music.set_pos(pos / 1000)

    def update_progress(self):
        # Handle pygame events
        for event in pygame.event.get():
            if event.type == pygame.USEREVENT:
                self.handle_track_end()

        # Update progress
        if self.is_playing:
            current_pos = mixer.music.get_pos()
            self.progress_slider.set(current_pos)
            self.current_time.config(text=str(timedelta(milliseconds=current_pos))[:-3])

        self.after(100, self.update_progress)

    def handle_track_end(self):
        if self.repeat_mode == 1:
            self.play_track(self.current_track_index)
        elif self.repeat_mode == 2 or self.current_track_index < len(self.playlist_items)-1:
            self.play_next()
        else:
            self.is_playing = False
            self.play_btn.config(text="Play")

    def playlist_double_clicked(self, event):
        index = self.playlist.nearest(event.y)
        if index >= 0:
            self.play_track(index)

    def quit_app(self):
        self.save_settings()
        mixer.music.stop()
        self.tray_icon.stop()
        self.destroy()

    def on_close(self):
        self.quit_app()

if __name__ == "__main__":
    app = ModernMusicPlayer()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
