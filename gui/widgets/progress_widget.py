# gui/widgets/progress_widget.py - ИСПРАВЛЕННАЯ ВЕРСИЯ БЕЗ СКОРОСТИ

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QProgressBar,
    QLabel, QGroupBox, QFrame
)
from PySide6.QtCore import Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve, QMutex, QMutexLocker
from PySide6.QtGui import QFont
from gui.ui_constants import (
    PROGRESS_BAR_STYLE,
    STATUS_LABEL_STYLE,
    PERCENT_LABEL_STYLE,
    FILES_LABEL_STYLE,
)
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ProgressWidget(QWidget):
    """Виджет прогресса БЕЗ скорости"""

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.mutex = QMutex()

        # Время и статистика
        self.start_time = None
        self.last_update_time = None
        self.successful_files = 0
        self.failed_files = 0
        self.processed_files = 0
        self.current_file_index = 0
        self.total_files = 0

        # Анимация прогресса
        self.progress_animation = None

        # Инициализация
        self.reset()

    def setup_ui(self):
        """Настройка интерфейса БЕЗ скорости"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Группа прогресса
        progress_group = QGroupBox("📊 Прогресс конвертации")
        progress_layout = QVBoxLayout(progress_group)

        # Основной прогресс-бар
        self.main_progress = QProgressBar()
        self.main_progress.setMinimum(0)
        self.main_progress.setMaximum(100)
        self.main_progress.setValue(0)
        self.main_progress.setMinimumHeight(30)
        self.main_progress.setStyleSheet(PROGRESS_BAR_STYLE)
        progress_layout.addWidget(self.main_progress)

        # Информация о прогрессе
        info_layout = QHBoxLayout()

        # Текущий статус
        self.status_label = QLabel("Готов к работе")
        self.status_label.setStyleSheet(STATUS_LABEL_STYLE)
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        # Процент
        self.percent_label = QLabel("0%")
        self.percent_label.setStyleSheet(PERCENT_LABEL_STYLE)
        info_layout.addWidget(self.percent_label)

        progress_layout.addLayout(info_layout)

        # Детальная информация - ТОЛЬКО ФАЙЛЫ
        details_layout = QHBoxLayout()

        # Файлы
        self.files_label = QLabel("Файлов: 0 / 0")
        self.files_label.setStyleSheet(FILES_LABEL_STYLE)
        details_layout.addWidget(self.files_label)

        details_layout.addStretch()

        progress_layout.addLayout(details_layout)

        layout.addWidget(progress_group)

        # Статистика - УБРАЛИ СКОРОСТЬ
        stats_group = QGroupBox("📈 Статистика")
        stats_layout = QVBoxLayout(stats_group)

        stats_grid = QHBoxLayout()

        # Успешно
        success_frame = self.create_stat_frame("✅", "Успешно", "0", "#4CAF50")
        stats_grid.addWidget(success_frame)
        self.success_label = success_frame.findChild(QLabel, "value")

        # Ошибки
        error_frame = self.create_stat_frame("❌", "Ошибок", "0", "#f44336")
        stats_grid.addWidget(error_frame)
        self.error_label = error_frame.findChild(QLabel, "value")

        # УБРАЛИ СКОРОСТЬ ПОЛНОСТЬЮ

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
        value_label.setObjectName("value")
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
        """Полный сброс виджета"""
        with QMutexLocker(self.mutex):
            # Сбрасываем значения
            self.start_time = None
            self.last_update_time = None
            self.successful_files = 0
            self.failed_files = 0
            self.processed_files = 0
            self.current_file_index = 0
            self.total_files = 0

        # Обновляем UI
        self.main_progress.setValue(0)
        self.status_label.setText("Готов к работе")
        self.percent_label.setText("0%")
        self.files_label.setText("Файлов: 0 / 0")

        # Обновляем статистику
        if self.success_label:
            self.success_label.setText("0")
        if self.error_label:
            self.error_label.setText("0")

        # Сбрасываем стили
        self.reset_styles()

        logger.debug("Progress widget reset completed")

    def update_progress(self, progress: int, message: str, current_file: int = 0, total_files: int = 0):
        """Обновление прогресса"""
        logger.debug(f"Progress update: {progress}% - {message} ({current_file}/{total_files})")

        with QMutexLocker(self.mutex):
            # Обновляем счетчики
            self.current_file_index = current_file
            if total_files > 0:
                self.total_files = total_files

            # Стартуем время при первом обновлении
            if self.start_time is None and progress > 0:
                self.start_time = datetime.now()

            # Обновляем время последнего изменения
            if progress > 0:
                self.last_update_time = datetime.now()

        # Анимируем прогресс
        self.animate_progress(progress)

        # Обновляем labels
        self.status_label.setText(message)
        self.percent_label.setText(f"{progress}%")

        # Обновляем файлы
        if total_files > 0:
            self.files_label.setText(f"Файлов: {current_file} / {total_files}")

    def animate_progress(self, target_value: int):
        """Плавная анимация прогресса"""
        if not self.main_progress:
            return

        # Создаем анимацию
        if self.progress_animation is None:
            self.progress_animation = QPropertyAnimation(self.main_progress, b"value")
            self.progress_animation.setDuration(500)  # 500ms
            self.progress_animation.setEasingCurve(QEasingCurve.OutCubic)

        # Останавливаем текущую анимацию
        if self.progress_animation.state() == QPropertyAnimation.Running:
            self.progress_animation.stop()

        # Настраиваем новую анимацию
        current_value = self.main_progress.value()
        self.progress_animation.setStartValue(current_value)
        self.progress_animation.setEndValue(target_value)
        self.progress_animation.start()

    def on_file_completed(self, success: bool):
        """Обработка завершения файла"""
        with QMutexLocker(self.mutex):
            self.processed_files += 1

            if success:
                self.successful_files += 1
            else:
                self.failed_files += 1

        # Обновляем статистику
        self.update_stats()

        logger.debug(f"File completed: success={success}, processed={self.processed_files}")

    def update_stats(self):
        """Обновление статистики"""
        with QMutexLocker(self.mutex):
            success_count = self.successful_files
            error_count = self.failed_files

        # Обновляем UI
        if self.success_label:
            self.success_label.setText(str(success_count))
        if self.error_label:
            self.error_label.setText(str(error_count))

    def set_total_files(self, total: int):
        """Установка общего количества файлов"""
        with QMutexLocker(self.mutex):
            self.total_files = total

        self.files_label.setText(f"Файлов: 0 / {total}")
        logger.debug(f"Total files set to: {total}")

    def set_completion_status(self, success: bool, message: str = ""):
        """Финальный статус"""
        logger.info(f"Setting completion status: success={success}, message={message}")

        if success:
            self.status_label.setText("✅ Конвертация завершена!")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #4CAF50;
                    font-weight: bold;
                    margin: 4px;
                }
            """)
            self.main_progress.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #4CAF50;
                    border-radius: 15px;
                    background: #f8f9fa;
                    text-align: center;
                    font-weight: bold;
                    font-size: 13px;
                    color: #333;
                }
                QProgressBar::chunk {
                    background: #4CAF50;
                    border-radius: 13px;
                }
            """)
        else:
            self.status_label.setText("❌ Конвертация с ошибками")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #f44336;
                    font-weight: bold;
                    margin: 4px;
                }
            """)
            self.main_progress.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #f44336;
                    border-radius: 15px;
                    background: #f8f9fa;
                    text-align: center;
                    font-weight: bold;
                    font-size: 13px;
                    color: #333;
                }
                QProgressBar::chunk {
                    background: #f44336;
                    border-radius: 13px;
                }
            """)

    def set_error_status(self, error_message: str):
        """Статус ошибки"""
        logger.error(f"Setting error status: {error_message}")

        self.status_label.setText("💥 Критическая ошибка")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #f44336;
                font-weight: bold;
                margin: 4px;
            }
        """)

    def reset_styles(self):
        """Сброс стилей"""
        self.status_label.setStyleSheet(STATUS_LABEL_STYLE)

        self.main_progress.setStyleSheet(PROGRESS_BAR_STYLE)

    def get_current_stats(self) -> dict:
        """Получение текущей статистики"""
        with QMutexLocker(self.mutex):
            return {
                "successful_files": self.successful_files,
                "failed_files": self.failed_files,
                "processed_files": self.processed_files,
                "current_file_index": self.current_file_index,
                "total_files": self.total_files,
                "start_time": self.start_time.isoformat() if self.start_time else None
            }

    def closeEvent(self, event):
        """Закрытие виджета"""
        if self.progress_animation and self.progress_animation.state() == QPropertyAnimation.Running:
            self.progress_animation.stop()

        event.accept()
        logger.debug("Progress widget closed")