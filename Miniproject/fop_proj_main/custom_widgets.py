from PyQt6.QtWidgets import QApplication, QGraphicsBlurEffect, QVBoxLayout, QFrame, QLabel, QPushButton, QMainWindow, QMessageBox, QLineEdit, QStackedWidget, QDialog
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QSize, pyqtSignal
from PyQt6.QtWidgets import QFrame

class HoverCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent=None): 
        super().__init__(parent)
        
        self.anim = QPropertyAnimation(self, b"minimumSize")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.base_size = None

    def enterEvent(self, event):
        if self.base_size is None:
            self.base_size = self.size()
            
        self.anim.setStartValue(self.size())
        self.anim.setEndValue(QSize(self.base_size.width() + 10, self.base_size.height() + 10))
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.setStartValue(self.size())
        self.anim.setEndValue(self.base_size)
        self.anim.start()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        super().mouseReleaseEvent(event)