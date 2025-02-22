import sys
import os
from pathlib import Path
from datetime import timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QListWidget, QLabel, 
                            QSlider, QProgressBar, QFileDialog, QStyle, 
                            QSystemTrayIcon, QMenu, QSpinBox)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from mutagen import File
import random
import json

class ModernMusicPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Music Player")
        self.setMinimumSize(900, 600)
        
        # Initialize variables
        self.supported_formats = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
        self.playlist_items = []
        self.current_track_index = -1
        self.is_playing = False
        self.is_shuffled = False
        self.repeat_mode = 0  # 0: No repeat, 1: Repeat track, 2: Repeat playlist
        
        # Setup media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # Setup UI
        self.setup_ui()
        self.setup_connections()
        self.setup_tray()
        self.load_settings()
        
        # Start position update timer
        self.position_timer = QTimer()
        self.position_timer.setInterval(1000)
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.start()

    def setup_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Playlist
        self.playlist = QListWidget()
        self.playlist.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1a;
                color: white;
                font-size: 12px;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #404040;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.playlist)
        
        # Time labels
        time_layout = QHBoxLayout()
        self.current_time = QLabel("00:00")
        self.total_time = QLabel("00:00")
        
        # Progress bar
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #404040;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
        """)
        
        time_layout.addWidget(self.current_time)
        time_layout.addWidget(self.progress_slider)
        time_layout.addWidget(self.total_time)
        layout.addLayout(time_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        # Create buttons with icons
        self.prev_btn = QPushButton()
        self.play_btn = QPushButton()
        self.next_btn = QPushButton()
        self.shuffle_btn = QPushButton()
        self.repeat_btn = QPushButton()
        
        # Set icons
        style = self.style()
        self.prev_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.play_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.next_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.shuffle_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.repeat_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        
        # Add buttons to layout
        controls_layout.addStretch()
        for btn in [self.shuffle_btn, self.prev_btn, self.play_btn, self.next_btn, self.repeat_btn]:
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    border-radius: 20px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
            """)
            controls_layout.addWidget(btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_icon = QLabel()
        volume_icon.setPixmap(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume).pixmap(16, 16))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        
        volume_layout.addStretch()
        volume_layout.addWidget(volume_icon)
        volume_layout.addWidget(self.volume_slider)
        layout.addLayout(volume_layout)
        
        # Status bar
        self.statusBar().showMessage("Ready")

    def setup_connections(self):
        # Player signals
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.mediaStatusChanged.connect(self.media_status_changed)
        
        # Control buttons
        self.play_btn.clicked.connect(self.toggle_playback)
        self.prev_btn.clicked.connect(self.play_previous)
        self.next_btn.clicked.connect(self.play_next)
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        self.repeat_btn.clicked.connect(self.toggle_repeat)
        
        # Other controls
        self.playlist.itemDoubleClicked.connect(self.playlist_double_clicked)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.progress_slider.sliderMoved.connect(self.set_position)

    def setup_tray(self):
        # System tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        
        # Tray menu
        tray_menu = QMenu()
        play_action = tray_menu.addAction("Play/Pause")
        play_action.triggered.connect(self.toggle_playback)
        next_action = tray_menu.addAction("Next")
        next_action.triggered.connect(self.play_next)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def load_settings(self):
        try:
            if os.path.exists('player_settings.json'):
                with open('player_settings.json', 'r') as f:
                    settings = json.load(f)
                    self.volume_slider.setValue(settings.get('volume', 50))
                    last_directory = settings.get('last_directory')
                    if last_directory and os.path.exists(last_directory):
                        self.load_directory(last_directory)
        except Exception as e:
            self.statusBar().showMessage(f"Error loading settings: {str(e)}")

    def save_settings(self):
        settings = {
            'volume': self.volume_slider.value(),
            'last_directory': self.current_directory if hasattr(self, 'current_directory') else None
        }
        try:
            with open('player_settings.json', 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            self.statusBar().showMessage(f"Error saving settings: {str(e)}")

    def load_directory(self, directory):
        self.current_directory = directory
        self.playlist.clear()
        self.playlist_items.clear()
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(self.supported_formats):
                    path = os.path.join(root, file)
                    self.playlist_items.append(path)
                    self.playlist.addItem(os.path.basename(file))

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            if self.current_track_index == -1 and self.playlist_items:
                self.current_track_index = 0
            self.player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def play_track(self, index):
        if 0 <= index < len(self.playlist_items):
            self.current_track_index = index
            self.playlist.setCurrentRow(index)
            self.player.setSource(QUrl.fromLocalFile(self.playlist_items[index]))
            self.player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def play_next(self):
        if self.playlist_items:
            if self.is_shuffled:
                self.current_track_index = random.randint(0, len(self.playlist_items) - 1)
            else:
                self.current_track_index = (self.current_track_index + 1) % len(self.playlist_items)
            self.play_track(self.current_track_index)

    def play_previous(self):
        if self.playlist_items:
            if self.is_shuffled:
                self.current_track_index = random.randint(0, len(self.playlist_items) - 1)
            else:
                self.current_track_index = (self.current_track_index - 1) % len(self.playlist_items)
            self.play_track(self.current_track_index)

    def toggle_shuffle(self):
        self.is_shuffled = not self.is_shuffled
        self.shuffle_btn.setStyleSheet(
            "background-color: #606060;" if self.is_shuffled else "background-color: #404040;"
        )

    def toggle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        if self.repeat_mode == 0:
            self.repeat_btn.setStyleSheet("background-color: #404040;")
        elif self.repeat_mode == 1:
            self.repeat_btn.setStyleSheet("background-color: #606060;")
        else:
            self.repeat_btn.setStyleSheet("background-color: #808080;")

    def set_volume(self, value):
        self.audio_output.setVolume(value / 100)

    def set_position(self, position):
        self.player.setPosition(position)

    def position_changed(self, position):
        self.progress_slider.setValue(position)
        self.current_time.setText(str(timedelta(milliseconds=position))[:-7])

    def duration_changed(self, duration):
        self.progress_slider.setRange(0, duration)
        self.total_time.setText(str(timedelta(milliseconds=duration))[:-7])

    def media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.repeat_mode == 1:  # Repeat track
                self.play_track(self.current_track_index)
            elif self.repeat_mode == 2:  # Repeat playlist
                self.play_next()
            elif self.current_track_index < len(self.playlist_items) - 1:
                self.play_next()

    def playlist_double_clicked(self):
        index = self.playlist.currentRow()
        if index >= 0:
            self.play_track(index)

    def closeEvent(self, event):
        self.save_settings()
        self.player.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for better cross-platform appearance
    player = ModernMusicPlayer()
    player.show()
    sys.exit(app.exec())
