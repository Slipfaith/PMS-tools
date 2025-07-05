# gui/ui_constants.py
"""Shared GUI style constants."""

HEADER_FRAME_STYLE = """
QFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a90e2, stop:1 #357abd);
    border-radius: 8px;
    padding: 10px;
}
"""

TITLE_LABEL_STYLE = """
QLabel {
    color: white;
    font-size: 24px;
    font-weight: bold;
    background: transparent;
}
"""

DESC_LABEL_STYLE = """
QLabel {
    color: #e8f4fd;
    font-size: 14px;
    background: transparent;
}
"""

ADD_EXCEL_BUTTON_STYLE = """
QPushButton {
    background: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background: #45a049;
}
"""

START_BUTTON_STYLE = """
QPushButton {
    background: #4CAF50;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 16px;
    font-weight: bold;
}
QPushButton:hover {
    background: #45a049;
}
QPushButton:disabled {
    background: #cccccc;
    color: #666666;
}
"""

STOP_BUTTON_STYLE = """
QPushButton {
    background: #f44336;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 16px;
    font-weight: bold;
}
QPushButton:hover {
    background: #da190b;
}
QPushButton:disabled {
    background: #cccccc;
    color: #666666;
}
"""

PROGRESS_BAR_STYLE = """
QProgressBar {
    border: 2px solid #e0e0e0;
    border-radius: 15px;
    background: #f8f9fa;
    text-align: center;
    font-weight: bold;
    font-size: 13px;
    color: #333;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4CAF50, stop:1 #45a049);
    border-radius: 13px;
}
"""

STATUS_LABEL_STYLE = """
QLabel {
    font-size: 14px;
    color: #333;
    font-weight: bold;
    margin: 4px;
}
"""

PERCENT_LABEL_STYLE = """
QLabel {
    font-size: 16px;
    color: #4CAF50;
    font-weight: bold;
    margin: 4px;
}
"""

FILES_LABEL_STYLE = "font-size: 12px; color: #666; margin: 2px;"
