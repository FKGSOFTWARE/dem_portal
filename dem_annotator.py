import sys
import os
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QLabel, QToolBar,
    QPushButton, QProgressBar, QMessageBox, QScrollArea
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QPen, QColor, QIcon, QImage, QCursor, QBrush, QPainterPath
)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.drawing = False
        self.lastPoint = QPoint()
        self.startPoint = QPoint()
        self.endPoint = QPoint()
        self.freehand_points = []

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.lastPoint = self.mapToImage(event.pos())
            self.startPoint = self.lastPoint
            self.freehand_points = [self.startPoint]

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.endPoint = self.mapToImage(event.pos())
            if self.parent.current_tool == 'freehand':
                self.freehand_points.append(self.endPoint)
                self.parent.drawFreehand(self.lastPoint, self.endPoint)
                self.lastPoint = self.endPoint
            elif self.parent.current_tool in ['rectangle', 'circle']:
                self.parent.updateTemporaryShape(self.startPoint, self.endPoint)
            elif self.parent.current_tool == 'eraser':
                self.parent.erase(self.lastPoint, self.endPoint)
                self.lastPoint = self.endPoint

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            if self.parent.current_tool in ['rectangle', 'circle']:
                self.parent.finalizeShape(self.startPoint, self.endPoint)
            elif self.parent.current_tool == 'freehand':
                self.parent.finalizeFreehand(self.freehand_points)

    def wheelEvent(self, event):
        self.parent.zoomImage(event.angleDelta().y())

    def mapToImage(self, pos):
        # Get the position of the image within the label
        image_pos = self.pixmap().rect().topLeft()

        # Calculate the actual position on the image
        x = (pos.x() - image_pos.x()) / self.parent.scaleFactor
        y = (pos.y() - image_pos.y()) / self.parent.scaleFactor

        return QPoint(int(x), int(y))

class Annotator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DEM Image Annotator")
        self.showMaximized()

        self.image_folder = 'images'
        self.output_folder = 'output'
        os.makedirs(self.output_folder, exist_ok=True)

        self.image_list = sorted([
            f for f in os.listdir(self.image_folder)
            if f.lower().endswith('.png')
        ])
        self.total_images = len(self.image_list)
        self.current_index = 0

        self.current_tool = 'freehand'  # Default tool
        self.undo_stack = []
        self.redo_stack = []
        self.brushColor = QColor(255, 255, 255, 255)  # White color for mask
        self.brushSize = 2

        self.scaleFactor = 1.0
        self.max_scale = 5.0  # Maximum zoom level
        self.min_scale = 0.1  # Minimum zoom level

        self.initUI()
        self.loadImage()

    def initUI(self):
        # Create toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Add actions to the toolbar
        circle_action = QAction("Circle", self)
        circle_action.setStatusTip("Draw Circle")
        circle_action.triggered.connect(self.selectCircle)
        toolbar.addAction(circle_action)

        rect_action = QAction("Rectangle", self)
        rect_action.setStatusTip("Draw Rectangle")
        rect_action.triggered.connect(self.selectRectangle)
        toolbar.addAction(rect_action)

        freehand_action = QAction("Freehand", self)
        freehand_action.setStatusTip("Freehand Draw")
        freehand_action.triggered.connect(self.selectFreehand)
        toolbar.addAction(freehand_action)

        eraser_action = QAction("Eraser", self)
        eraser_action.setStatusTip("Erase")
        eraser_action.triggered.connect(self.selectEraser)
        toolbar.addAction(eraser_action)

        undo_action = QAction("Undo", self)
        undo_action.setStatusTip("Undo Last Action")
        undo_action.triggered.connect(self.undo)
        toolbar.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setStatusTip("Redo Last Action")
        redo_action.triggered.connect(self.redo)
        toolbar.addAction(redo_action)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(self.total_images)
        self.progress_bar.setValue(self.current_index)
        toolbar.addWidget(self.progress_bar)

        # Done button
        done_button = QPushButton("Done")
        done_button.clicked.connect(self.saveAndNext)
        toolbar.addWidget(done_button)

        # Help button
        help_action = QAction("Help", self)
        help_action.setStatusTip("Help")
        help_action.triggered.connect(self.showHelp)
        toolbar.addAction(help_action)

        # Create scroll area
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.setCentralWidget(self.scrollArea)

        # Image label
        self.image_label = ImageLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMouseTracking(True)
        self.scrollArea.setWidget(self.image_label)

    def drawFreehand(self, start, end):
        painter = QPainter(self.mask_pixmap)
        pen = QPen(self.brushColor, self.brushSize, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(start, end)
        painter.end()
        self.updateImage()

    def finalizeFreehand(self, points):
        painter = QPainter(self.mask_pixmap)
        pen = QPen(self.brushColor, self.brushSize, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)
        painter.fillPath(path, QBrush(self.brushColor))
        painter.end()
        self.saveState()
        self.updateImage()

    def loadImage(self):
        if self.current_index >= self.total_images:
            QMessageBox.information(self, "Completed", "All images have been annotated.")
            self.close()
            return

        image_name = self.image_list[self.current_index]
        image_path = os.path.join(self.image_folder, image_name)
        self.image = Image.open(image_path).convert('RGB')

        qimage = QImage(self.image.tobytes("raw", "RGB"), self.image.width, self.image.height, QImage.Format_RGB888)
        self.pixmap = QPixmap.fromImage(qimage)

        self.mask_pixmap = QPixmap(self.pixmap.size())
        self.mask_pixmap.fill(Qt.transparent)

        self.undo_stack.clear()
        self.redo_stack.clear()
        self.saveState()

        self.scaleFactor = 1.0
        self.updateImage()
        self.updateProgressBar()

    def updateImage(self, temp=False):
        combined_pixmap = QPixmap(self.pixmap)
        painter = QPainter(combined_pixmap)
        if temp and hasattr(self, 'temp_pixmap'):
            painter.drawPixmap(0, 0, self.temp_pixmap)
        else:
            painter.drawPixmap(0, 0, self.mask_pixmap)
        painter.end()

        scaled_pixmap = combined_pixmap.scaled(
            self.pixmap.size() * self.scaleFactor,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)

        # Center the image in the label
        self.image_label.resize(self.scrollArea.size())

    def zoomImage(self, delta):
        if delta > 0:
            factor = 1.25
        else:
            factor = 0.8

        new_scale = self.scaleFactor * factor
        if self.min_scale <= new_scale <= self.max_scale:
            self.scaleFactor = new_scale
            self.updateImage()

        # Ensure the scroll area updates its scroll bars
        self.scrollArea.setWidgetResizable(False)
        self.scrollArea.setWidgetResizable(True)

    def updateProgressBar(self):
        self.progress_bar.setValue(self.current_index + 1)

    def saveState(self):
        self.undo_stack.append(self.mask_pixmap.copy())
        if len(self.undo_stack) > 20:  # Limit undo stack size
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.mask_pixmap = self.undo_stack[-1].copy()
            self.updateImage()
        else:
            QMessageBox.information(self, "Undo", "Nothing to undo.")

    def redo(self):
        if self.redo_stack:
            self.mask_pixmap = self.redo_stack.pop()
            self.undo_stack.append(self.mask_pixmap.copy())
            self.updateImage()
        else:
            QMessageBox.information(self, "Redo", "Nothing to redo.")

    def selectCircle(self):
        self.current_tool = 'circle'
        self.setCursor(Qt.CrossCursor)
        QMessageBox.information(self, "Tool Selected", "Circle tool selected.")

    def selectRectangle(self):
        self.current_tool = 'rectangle'
        self.setCursor(Qt.CrossCursor)
        QMessageBox.information(self, "Tool Selected", "Rectangle tool selected.")

    def selectFreehand(self):
        self.current_tool = 'freehand'
        self.setCursor(Qt.CrossCursor)
        QMessageBox.information(self, "Tool Selected", "Freehand tool selected.")

    def selectEraser(self):
        self.current_tool = 'eraser'
        self.setCursor(Qt.PointingHandCursor)
        QMessageBox.information(self, "Tool Selected", "Eraser tool selected.")

    def updateTemporaryShape(self, startPoint, endPoint):
        self.temp_pixmap = self.mask_pixmap.copy()
        painter = QPainter(self.temp_pixmap)
        pen = QPen(self.brushColor, self.brushSize, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(self.brushColor))
        if self.current_tool == 'rectangle':
            painter.drawRect(QRect(startPoint, endPoint))
        elif self.current_tool == 'circle':
            painter.drawEllipse(QRect(startPoint, endPoint))
        painter.end()
        self.updateImage(temp=True)

    def finalizeShape(self, startPoint, endPoint):
        painter = QPainter(self.mask_pixmap)
        pen = QPen(self.brushColor, self.brushSize, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(self.brushColor))
        if self.current_tool == 'rectangle':
            painter.drawRect(QRect(startPoint, endPoint))
        elif self.current_tool == 'circle':
            painter.drawEllipse(QRect(startPoint, endPoint))
        painter.end()
        self.saveState()
        self.updateImage()

    def saveAndNext(self):
        # Save mask
        image_name = self.image_list[self.current_index]
        mask_name = os.path.splitext(image_name)[0] + '_mask.png'
        mask_path = os.path.join(self.output_folder, mask_name)

        # Convert mask_pixmap to binary mask
        mask_image = self.mask_pixmap.toImage().convertToFormat(QImage.Format_Grayscale8)
        width = mask_image.width()
        height = mask_image.height()
        ptr = mask_image.bits()
        ptr.setsize(mask_image.byteCount())
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width))

        # Create binary mask
        binary_mask = (arr > 0).astype(np.uint8) * 255
        mask_image = Image.fromarray(binary_mask)
        mask_image.save(mask_path)

        # Move to next image
        self.current_index += 1
        self.loadImage()

    def erase(self, start, end):
        painter = QPainter(self.mask_pixmap)
        eraser = QPen(Qt.transparent, self.brushSize * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(eraser)
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.drawLine(start, end)
        painter.end()
        self.updateImage()

    def showHelp(self):
        help_text = """
        **DEM Image Annotator Help**

        - **Drawing Tools**:
          - *Circle*: Draw circles by clicking and dragging.
          - *Rectangle*: Draw rectangles by clicking and dragging.
          - *Freehand*: Draw freehand shapes by moving the cursor while holding the left mouse button.
          - *Eraser*: Erase annotations by drawing over them.
        - **Undo/Redo**:
          - Undo or redo the last action.
        - **Zoom and Pan**:
          - Zoom in/out using the mouse wheel.
          - Pan by clicking and dragging with the middle mouse button.
        - **Done Button**:
          - Click "Done" to save the current annotations and proceed to the next image.
        - **Progress Bar**:
          - Indicates your progress through the image set.

        For further assistance, contact the support team.
        """
        QMessageBox.information(self, "Help", help_text)

def main():
    app = QApplication(sys.argv)
    window = Annotator()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
