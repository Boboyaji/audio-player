import flet as ft
import os
import pygame
from pygame import mixer
import random
import json
from datetime import timedelta
from mutagen import File
import threading
import time

class ModernMusicPlayer:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Modern Music Player"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        
        # Initialize variables
        self.supported_formats = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
        self.playlist_items = []
        self.current_track_index = -1
        self.is_playing = False
        self.is_shuffled = False
        self.repeat_mode = 0  # 0: No repeat, 1: Repeat track, 2: Repeat playlist
        self.current_directory = None
        self.volume_level = 50
        
        # Initialize pygame mixer
        pygame.init()
        mixer.init()
        mixer.music.set_endevent(pygame.USEREVENT)
        mixer.music.set_volume(self.volume_level / 100)
        
        # Setup UI
        self.setup_ui()
        self.load_settings()
        
        # Start track progress and event monitoring thread
        self.should_update_progress = True
        threading.Thread(target=self.progress_updater, daemon=True).start()
        threading.Thread(target=self.event_monitor, daemon=True).start()

    def setup_ui(self):
        # App container
        self.app_layout = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                # Header with app title and menu
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text("Modern Music Player", size=22, weight=ft.FontWeight.BOLD),
                            ft.Spacer(),
                            ft.IconButton(
                                icon=ft.icons.FOLDER_OPEN,
                                tooltip="Open Directory",
                                on_click=self.open_directory_dialog
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    padding=15,
                    bgcolor=ft.colors.SURFACE_VARIANT
                ),
                
                # Current track info (shown when a track is playing)
                self.create_now_playing_view(),
                
                # Playlist view (main content)
                ft.Container(
                    content=self.create_playlist_view(),
                    expand=True,
                    padding=10
                ),
                
                # Player controls at bottom
                self.create_player_controls()
            ]
        )
        
        # Add everything to the page
        self.page.add(self.app_layout)
    
    def create_now_playing_view(self):
        self.now_playing_text = ft.Text("Not playing", size=16, weight=ft.FontWeight.BOLD)
        self.album_art = ft.Container(
            width=80,
            height=80,
            border_radius=10,
            bgcolor=ft.colors.SURFACE_VARIANT,
            content=ft.Icon(ft.icons.MUSIC_NOTE, size=40, color=ft.colors.ON_SURFACE_VARIANT)
        )
        
        return ft.Container(
            visible=False,  # Initially hidden
            content=ft.Row(
                controls=[
                    self.album_art,
                    ft.Column(
                        controls=[
                            self.now_playing_text,
                            ft.Text("", size=14, opacity=0.7, color=ft.colors.ON_SURFACE_VARIANT)
                        ],
                        spacing=5,
                        alignment=ft.MainAxisAlignment.CENTER,
                        expand=True
                    )
                ],
                spacing=20
            ),
            padding=15,
            bgcolor=ft.colors.SURFACE,
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.OUTLINE))
        )
    
    def create_playlist_view(self):
        self.playlist = ft.ListView(
            expand=True,
            spacing=2,
            padding=10,
            auto_scroll=False
        )
        
        self.empty_playlist_view = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.icons.PLAYLIST_PLAY, size=80, opacity=0.5),
                    ft.Text("Your playlist is empty", size=16, opacity=0.5),
                    ft.Text("Open a folder to add music", size=14, opacity=0.5),
                    ft.FilledButton(
                        "Open Directory",
                        icon=ft.icons.FOLDER_OPEN,
                        on_click=self.open_directory_dialog
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            ),
            alignment=ft.alignment.center,
            expand=True
        )
        
        return ft.Stack(
            [
                self.empty_playlist_view,
                self.playlist
            ]
        )
    
    def create_player_controls(self):
        # Progress bar and time labels
        self.current_time = ft.Text("00:00", size=12)
        self.total_time = ft.Text("00:00", size=12)
        self.progress_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            expand=True,
            on_change=self.progress_changed,
            on_change_end=self.seek_position
        )
        
        progress_row = ft.Row(
            controls=[
                self.current_time,
                self.progress_slider,
                self.total_time
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        # Control buttons
        self.shuffle_btn = ft.IconButton(
            icon=ft.icons.SHUFFLE,
            tooltip="Shuffle",
            on_click=self.toggle_shuffle,
            icon_color=ft.colors.ON_SURFACE_VARIANT
        )
        
        self.prev_btn = ft.IconButton(
            icon=ft.icons.SKIP_PREVIOUS,
            tooltip="Previous",
            on_click=lambda _: self.play_previous(),
            icon_size=30
        )
        
        self.play_btn = ft.IconButton(
            icon=ft.icons.PLAY_CIRCLE,
            tooltip="Play",
            on_click=lambda _: self.toggle_playback(),
            icon_size=48
        )
        
        self.next_btn = ft.IconButton(
            icon=ft.icons.SKIP_NEXT,
            tooltip="Next",
            on_click=lambda _: self.play_next(),
            icon_size=30
        )
        
        self.repeat_btn = ft.IconButton(
            icon=ft.icons.REPEAT,
            tooltip="Repeat",
            on_click=self.toggle_repeat,
            icon_color=ft.colors.ON_SURFACE_VARIANT
        )
        
        control_row = ft.Row(
            controls=[
                self.shuffle_btn,
                ft.Spacer(),
                self.prev_btn,
                self.play_btn,
                self.next_btn,
                ft.Spacer(),
                self.repeat_btn
            ],
            alignment=ft.MainAxisAlignment.CENTER
        )
        
        # Volume control
        self.volume_slider = ft.Slider(
            min=0,
            max=100,
            value=self.volume_level,
            width=100,
            on_change=self.set_volume
        )
        
        volume_row = ft.Row(
            controls=[
                ft.Icon(ft.icons.VOLUME_DOWN),
                self.volume_slider,
                ft.Icon(ft.icons.VOLUME_UP)
            ],
            alignment=ft.MainAxisAlignment.CENTER
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    progress_row,
                    control_row,
                    volume_row
                ],
                spacing=5
            ),
            padding=15,
            bgcolor=ft.colors.SURFACE,
            border=ft.border.only(top=ft.border.BorderSide(1, ft.colors.OUTLINE))
        )
    
    def open_directory_dialog(self, e=None):
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.path:
                self.load_directory(e.path)
        
        file_picker = ft.FilePicker(on_result=on_dialog_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.get_directory_path()
    
    def load_directory(self, directory):
        self.current_directory = directory
        self.playlist_items.clear()
        self.playlist.controls.clear()
        
        # Scan for music files
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(self.supported_formats):
                    path = os.path.join(root, file)
                    self.playlist_items.append(path)
                    
                    # Create playlist item
                    self.playlist.controls.append(
                        ft.Container(
                            content=ft.ListTile(
                                leading=ft.Icon(ft.icons.MUSIC_NOTE),
                                title=ft.Text(os.path.basename(file), overflow=ft.TextOverflow.ELLIPSIS),
                                subtitle=ft.Text(self.format_file_size(os.path.getsize(path)), 
                                               opacity=0.5, 
                                               size=12),
                                on_click=lambda _, path=path, idx=len(self.playlist_items)-1: self.play_track(idx)
                            ),
                            border_radius=5,
                            ink=True,
                            bgcolor=ft.colors.SURFACE,
                            padding=5
                        )
                    )
        
        # Update the UI
        self.empty_playlist_view.visible = len(self.playlist_items) == 0
        self.playlist.visible = len(self.playlist_items) > 0
        self.page.update()
        
        # Save settings
        self.save_settings()
    
    def format_file_size(self, size):
        """Format file size in bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"
    
    def toggle_playback(self):
        if self.is_playing:
            mixer.music.pause()
            self.is_playing = False
            self.play_btn.icon = ft.icons.PLAY_CIRCLE
            self.page.update()
        else:
            if self.current_track_index == -1 and self.playlist_items:
                self.current_track_index = 0
                self.play_track(self.current_track_index)
            else:
                mixer.music.unpause()
                self.is_playing = True
                self.play_btn.icon = ft.icons.PAUSE_CIRCLE
                self.page.update()
    
    def play_track(self, index):
        if 0 <= index < len(self.playlist_items):
            # Update selection in playlist
            self.current_track_index = index
            
            # Highlight the current track
            for i, item in enumerate(self.playlist.controls):
                if isinstance(item, ft.Container) and isinstance(item.content, ft.ListTile):
                    item.bgcolor = ft.colors.PRIMARY_CONTAINER if i == index else ft.colors.SURFACE
            
            # Load and play the track
            track_path = self.playlist_items[index]
            try:
                mixer.music.load(track_path)
                mixer.music.play()
                self.is_playing = True
                self.play_btn.icon = ft.icons.PAUSE_CIRCLE
                
                # Get track duration and metadata
                audio = File(track_path)
                duration = int(audio.info.length * 1000)  # Convert to milliseconds
                self.progress_slider.max = duration
                self.progress_slider.value = 0
                self.total_time.value = str(timedelta(seconds=int(audio.info.length)))[:-3]
                
                # Show now playing view
                self.now_playing_text.value = os.path.basename(track_path)
                file_parent = os.path.dirname(track_path)
                folder_name = os.path.basename(file_parent)
                self.now_playing_text.parent.controls[1].value = folder_name
                self.now_playing_text.parent.parent.parent.visible = True
                
                # Update UI
                self.page.update()
            except Exception as e:
                self.show_snack_bar(f"Error playing track: {str(e)}")
    
    def play_next(self):
        if self.playlist_items:
            if self.is_shuffled:
                self.current_track_index = random.randint(0, len(self.playlist_items)-1)
            else:
                self.current_track_index = (self.current_track_index + 1) % len(self.playlist_items)
            self.play_track(self.current_track_index)
    
    def play_previous(self):
        if self.playlist_items:
            # If we're more than 3 seconds into the track, restart it
            if mixer.music.get_pos() > 3000:
                mixer.music.play()
            else:
                if self.is_shuffled:
                    self.current_track_index = random.randint(0, len(self.playlist_items)-1)
                else:
                    self.current_track_index = (self.current_track_index - 1) % len(self.playlist_items)
                self.play_track(self.current_track_index)
    
    def toggle_shuffle(self, e):
        self.is_shuffled = not self.is_shuffled
        self.shuffle_btn.icon_color = ft.colors.PRIMARY if self.is_shuffled else ft.colors.ON_SURFACE_VARIANT
        self.page.update()
    
    def toggle_repeat(self, e):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        
        # Update icon based on repeat mode
        if self.repeat_mode == 0:  # No repeat
            self.repeat_btn.icon = ft.icons.REPEAT
            self.repeat_btn.icon_color = ft.colors.ON_SURFACE_VARIANT
        elif self.repeat_mode == 1:  # Repeat track
            self.repeat_btn.icon = ft.icons.REPEAT_ONE
            self.repeat_btn.icon_color = ft.colors.PRIMARY
        else:  # Repeat playlist
            self.repeat_btn.icon = ft.icons.REPEAT
            self.repeat_btn.icon_color = ft.colors.PRIMARY
        
        self.page.update()
    
    def set_volume(self, e):
        self.volume_level = int(e.control.value)
        mixer.music.set_volume(self.volume_level / 100)
    
    def progress_changed(self, e):
        # This is called during slider drag
        pass
    
    def seek_position(self, e):
        # This is called when slider drag ends
        position_ms = int(e.control.value)
        # pygame doesn't support precise seeking, so we restart and skip to position
        current_pos = mixer.music.get_pos()
        if abs(position_ms - current_pos) > 1000:  # Only seek if difference is significant
            current_track = self.playlist_items[self.current_track_index]
            mixer.music.load(current_track)
            mixer.music.play()
            mixer.music.set_pos(position_ms / 1000)  # Convert ms to seconds
    
    def progress_updater(self):
        """Update progress bar in a separate thread"""
        while self.should_update_progress:
            if self.is_playing:
                current_pos = mixer.music.get_pos()
                if current_pos > 0:  # Only update if we have a valid position
                    def update_ui():
                        self.progress_slider.value = current_pos
                        self.current_time.value = str(timedelta(milliseconds=current_pos))[:-3]
                        self.page.update()
                    
                    self.page.run_on_ui_thread(update_ui)
            time.sleep(0.1)  # Update 10 times per second
    
    def event_monitor(self):
        """Monitor pygame events in a separate thread"""
        while self.should_update_progress:
            for event in pygame.event.get():
                if event.type == pygame.USEREVENT:
                    # Track ended
                    def handle_track_end():
                        if self.repeat_mode == 1:  # Repeat track
                            self.play_track(self.current_track_index)
                        elif self.repeat_mode == 2 or (self.current_track_index < len(self.playlist_items)-1):
                            # Repeat playlist or still have tracks to play
                            self.play_next()
                        else:
                            # End of playlist with no repeat
                            self.is_playing = False
                            self.play_btn.icon = ft.icons.PLAY_CIRCLE
                            self.page.update()
                    
                    self.page.run_on_ui_thread(handle_track_end)
            time.sleep(0.1)
    
    def load_settings(self):
        try:
            if os.path.exists('player_settings.json'):
                with open('player_settings.json', 'r') as f:
                    settings = json.load(f)
                    self.volume_level = settings.get('volume', 50)
                    self.volume_slider.value = self.volume_level
                    mixer.music.set_volume(self.volume_level / 100)
                    
                    last_dir = settings.get('last_directory')
                    if last_dir and os.path.exists(last_dir):
                        self.load_directory(last_dir)
                    
                    self.page.update()
        except Exception as e:
            self.show_snack_bar(f"Error loading settings: {str(e)}")
    
    def save_settings(self):
        settings = {
            'volume': self.volume_level,
            'last_directory': self.current_directory or ''
        }
        try:
            with open('player_settings.json', 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            self.show_snack_bar(f"Error saving settings: {str(e)}")
    
    def show_snack_bar(self, message):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            action="OK",
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def on_close(self):
        self.save_settings()
        self.should_update_progress = False
        mixer.music.stop()

def main(page: ft.Page):
    app = ModernMusicPlayer(page)
    
    # Handle page close event
    page.on_close = app.on_close

ft.app(target=main)
