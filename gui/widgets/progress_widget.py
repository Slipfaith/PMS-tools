# gui/widgets/progress_widget.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QProgressBar,
    QLabel, QGroupBox, QFrame
)
from PySide6.QtCore import Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont
from datetime import datetime, timedelta


class ProgressWidget(QWidget):
    """Виджет для отображения прогресса конвертации с анимацией"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

        # Для расчета времени
        self.start_time = None
        self.last_update_time = None

        # Счетчики для статистики
        self.successful_files = 0
        self.failed_files = 0
        self.processed_files = 0

        # Таймер для обновления времени
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_elapsed_time)

        # Инициализируем после создания UI
        self.reset()

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Группа прогресса
        progress_group = QGroupBox("📊 Прогресс конвертации")
        progress_layout = QVBoxLayout(progress_group)

        # Основной прогресс-бар
        self.main_progress = QProgressBar()
        self.main_progress.setMinimumHeight(25)
        self.main_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                background: #f5f5f5;
                text-align: center;
                font-weight: bold;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #45a049);
                border-radius: 10px;
            }
        """)
        progress_layout.addWidget(self.main_progress)

        # Информация о прогрессе
        info_layout = QHBoxLayout()

        # Текущий статус
        self.status_label = QLabel("Готов к работе")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #333;
                font-weight: bold;
            }
        """)
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        # Процент выполнения
        self.percent_label = QLabel("0%")
        self.percent_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #4CAF50;
                font-weight: bold;
            }
        """)
        info_layout.addWidget(self.percent_label)

        progress_layout.addLayout(info_layout)

        # Детальная информация
        details_layout = QHBoxLayout()

        # Файлы
        self.files_label = QLabel("Файлов: 0 / 0")
        self.files_label.setStyleSheet("font-size: 12px; color: #666;")
        details_layout.addWidget(self.files_label)

        details_layout.addStretch()

        # Время
        self.time_label = QLabel("Время: --:--")
        self.time_label.setStyleSheet("font-size: 12px; color: #666;")
        details_layout.addWidget(self.time_label)

        progress_layout.addLayout(details_layout)

        # Оценка времени
        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("font-size: 11px; color: #999; font-style: italic;")
        self.eta_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.eta_label)

        layout.addWidget(progress_group)

        # Статистика
        stats_group = QGroupBox("📈 Статистика")
        stats_layout = QVBoxLayout(stats_group)

        # Сетка статистики
        stats_grid = QHBoxLayout()

        # Успешно
        success_frame = self.create_stat_frame("✅", "Успешно", "0", "#4CAF50")
        stats_grid.addWidget(success_frame)
        self.success_label = success_frame.findChild(QLabel, "value")

        # Ошибки
        error_frame = self.create_stat_frame("❌", "Ошибок", "0", "#f44336")
        stats_grid.addWidget(error_frame)
        self.error_label = error_frame.findChild(QLabel, "value")

        # Скорость
        speed_frame = self.create_stat_frame("⚡", "Скорость", "0/мин", "#FF9800")
        stats_grid.addWidget(speed_frame)
        self.speed_label = speed_frame.findChild(QLabel, "value")

        stats_layout.addLayout(stats_grid)
        layout.addWidget(stats_group)

    def create_stat_frame(self, icon: str, title: str, value: str, color: str) -> QFrame:
        """Создает рамку для статистики"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                padding: 8px;
            }}
            QFrame:hover {{
                border-color: {color};
                background: #fafafa;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(4)

        # Иконка
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"font-size: 24px; color: {color};")
        layout.addWidget(icon_label)

        # Значение
        value_label = QLabel(value)
        value_label.setObjectName("value")  # Для поиска через findChild
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: {color};
            }}
        """)
        layout.addWidget(value_label)

        # Заголовок
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(title_label)

        return frame

    def reset(self):
        """Сбрасывает все значения"""
        if hasattr(self, 'main_progress'):
            self.main_progress.setValue(0)
        if hasattr(self, 'status_label'):
            self.status_label.setText("Готов к работе")
        if hasattr(self, 'percent_label'):
            self.percent_label.setText("0%")
        if hasattr(self, 'files_label'):
            self.files_label.setText("Файлов: 0 / 0")
        if hasattr(self, 'time_label'):
            self.time_label.setText("Время: --:--")
        if hasattr(self, 'eta_label'):
            self.eta_label.setText("")

        # Сбрасываем статистику
        self.successful_files = 0
        self.failed_files = 0
        self.processed_files = 0
        self.update_stats()

        # Сбрасываем время
        self.start_time = None
        self.last_update_time = None
        if hasattr(self, 'timer'):
            self.timer.stop()

    def update_progress(self, progress: int, message: str, current_file: int = 0, total_files: int = 0):
        """Обновляет основной прогресс"""
        # Анимированное обновление прогресс-бара
        self.animate_progress(progress)

        # Обновляем текст
        self.status_label.setText(message)
        self.percent_label.setText(f"{progress}%")

        # Обновляем файлы
        if total_files > 0:
            self.files_label.setText(f"Файлов: {current_file} / {total_files}")

        # Запускаем таймер при первом обновлении
        if self.start_time is None and progress > 0:
            self.start_time = datetime.now()
            self.timer.start(1000)  # Обновляем каждую секунду

        # Обновляем время последнего изменения
        if progress > 0:
            self.last_update_time = datetime.now()

        # Рассчитываем ETA
        self.calculate_eta(progress)

        # Останавливаем таймер при завершении
        if progress >= 100:
            self.timer.stop()

    def animate_progress(self, target_value: int):
        """Анимирует изменение прогресс-бара"""
        if not hasattr(self, 'main_progress'):
            return

        if not hasattr(self, 'progress_animation'):
            self.progress_animation = QPropertyAnimation(self.main_progress, b"value")
            self.progress_animation.setDuration(300)  # 300ms анимация
            self.progress_animation.setEasingCurve(QEasingCurve.OutCubic)

        current_value = self.main_progress.value()
        self.progress_animation.setStartValue(current_value)
        self.progress_animation.setEndValue(target_value)
        self.progress_animation.start()

    def update_elapsed_time(self):
        """Обновляет прошедшее время"""
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{minutes:02d}:{seconds:02d}"

            self.time_label.setText(f"Время: {time_str}")

    def calculate_eta(self, progress: int):
        """Рассчитывает оценку времени завершения"""
        if not self.start_time or progress <= 0:
            self.eta_label.setText("")
            return

        elapsed = datetime.now() - self.start_time
        elapsed_seconds = elapsed.total_seconds()

        if elapsed_seconds < 5:  # Слишком рано для оценки
            return

        # Рассчитываем оставшееся время
        rate = progress / elapsed_seconds  # процент в секунду
        if rate > 0:
            remaining_seconds = (100 - progress) / rate
            remaining_time = timedelta(seconds=int(remaining_seconds))

            # Форматируем оставшееся время
            hours, remainder = divmod(int(remaining_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                eta_str = f"Осталось: ~{hours}ч {minutes}м"
            elif minutes > 0:
                eta_str = f"Осталось: ~{minutes}м {seconds}с"
            else:
                eta_str = f"Осталось: ~{seconds}с"

            self.eta_label.setText(eta_str)

        # Обновляем скорость (файлов в минуту)
        if self.processed_files > 0:
            files_per_minute = (self.processed_files / elapsed_seconds) * 60
            self.speed_label.setText(f"{files_per_minute:.1f}/мин")

    def on_file_completed(self, success: bool):
        """Вызывается при завершении обработки файла"""
        self.processed_files += 1

        if success:
            self.successful_files += 1
        else:
            self.failed_files += 1

        self.update_stats()

    def update_stats(self):
        """Обновляет статистику"""
        if hasattr(self, 'success_label'):
            self.success_label.setText(str(self.successful_files))
        if hasattr(self, 'error_label'):
            self.error_label.setText(str(self.failed_files))

        # Обновляем скорость
        if hasattr(self, 'speed_label') and self.start_time and self.processed_files > 0:
            elapsed = datetime.now() - self.start_time
            elapsed_seconds = elapsed.total_seconds()
            if elapsed_seconds > 0:
                files_per_minute = (self.processed_files / elapsed_seconds) * 60
                self.speed_label.setText(f"{files_per_minute:.1f}/мин")

    def set_completion_status(self, success: bool, message: str = ""):
        """Устанавливает финальный статус"""
        if success:
            self.status_label.setText("✅ Конвертация завершена!")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #4CAF50;
                    font-weight: bold;
                }
            """)
            self.main_progress.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #4CAF50;
                    border-radius: 12px;
                    background: #f5f5f5;
                    text-align: center;
                    font-weight: bold;
                    font-size: 12px;
                }
                QProgressBar::chunk {
                    background: #4CAF50;
                    border-radius: 10px;
                }
            """)
        else:
            self.status_label.setText("❌ Конвертация завершена с ошибками")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #f44336;
                    font-weight: bold;
                }
            """)
            self.main_progress.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #f44336;
                    border-radius: 12px;
                    background: #f5f5f5;
                    text-align: center;
                    font-weight: bold;
                    font-size: 12px;
                }
                QProgressBar::chunk {
                    background: #f44336;
                    border-radius: 10px;
                }
            """)

        if message:
            self.eta_label.setText(message)

    def set_error_status(self, error_message: str):
        """Устанавливает статус ошибки"""
        self.status_label.setText("💥 Критическая ошибка")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #f44336;
                font-weight: bold;
            }
        """)
        self.eta_label.setText(f"Ошибка: {error_message}")
        self.timer.stop()