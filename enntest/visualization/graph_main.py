import os
import logging
import json
import threading
import easygui
import sys
import re

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QScrollArea, QGraphicsItemGroup
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsLineItem, QGraphicsPolygonItem
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsTextItem

from PyQt5.QtGui import QPen, QBrush, QFont, QPainterPath, QImage, QPainter, QTransform, QColor, QPixmap, \
    QWheelEvent, QMouseEvent
from PyQt5.QtCore import Qt, QPointF, QLineF

logging.basicConfig(level=logging.CRITICAL)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def PRINT_(*args):
    # # print(args)
    logging.info(args)


def load_module_func(module_name):
    mod = __import__(f"{module_name}", fromlist=[module_name])
    return mod


class stateCtrl:
    skip = None
    true = True
    false = False


class EmittingStream(QtCore.QObject):
    textWritten = QtCore.pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

    def flush(self):
        pass


class STREAM_WINDOW(QtWidgets.QMainWindow):
    """ 도형 control 정의"""
    global_font = QFont("Arial", 8)
    global_node_width = 80
    global_node_height = 50
    global_node2node_offset_width = 150
    global_node2node_offset_height = 20

    class MyGraphicsRectItem(QGraphicsRectItem):

        class SignalEmitter(QtCore.QObject):
            notification = QtCore.pyqtSignal(object)

        def __init__(self, stream_group, branch_idx, label, id_, width, height, node_info, instance_center_pos_x=0,
                     instance_center_pos_y=0,
                     overlap=False, *args,
                     **kwargs):
            # 사각형의 시작 위치 계산: 중심 위치에서 너비와 높이의 절반을 뺌
            start_x = instance_center_pos_x - width / 2
            start_y = instance_center_pos_y - height / 2

            super().__init__(start_x, start_y, width, height, *args, **kwargs)
            self.setAcceptHoverEvents(True)
            self.emitter = self.SignalEmitter()

            self.stream_group = stream_group
            self.id = id_
            self.name = label
            self.branch_idx = branch_idx

            self.enn_label_measured_value = node_info[id_]["outputs"][0]["width"]

            self.top_center_x = instance_center_pos_x
            self.top_center_y = instance_center_pos_y - height // 2

            self.bottom_center_x = instance_center_pos_x
            self.bottom_center_y = instance_center_pos_y + height // 2

            self.left_center_x = instance_center_pos_x - width // 2
            self.left_center_y = instance_center_pos_y

            self.right_center_x = instance_center_pos_x + width // 2
            self.right_center_y = instance_center_pos_y

            self.center_pos_x = instance_center_pos_x
            self.center_pos_y = instance_center_pos_y
            self.width = width
            self.height = height

            font = STREAM_WINDOW.global_font
            labelItem = QGraphicsTextItem(label, self)  # 변수 이름 변경(label -> labelItem) 중복 피하기 위해
            labelItem.setDefaultTextColor(Qt.black)
            labelItem.setFont(font)  # 이제 이 부분에서 에러가 발생하지 않아야 합니다.

            # 라벨 위치 조정 - 사각형의 상단 왼쪽 안쪽에 위치
            labelItem.setPos(start_x, start_y)  # 여백을 고려하여 라벨 위치 조정

            if overlap:
                self.setPen(QPen(Qt.DotLine))
            else:
                self.setPen(QPen(Qt.SolidLine))

        def mousePressEvent(self, event):
            self.emitter.notification.emit(self)

    class MyPathItem(QGraphicsItemGroup):
        def __init__(self, points, src_label=None, dst_label=None, arrow=False, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # 화살표 몸통을 그리기 위한 QPainterPath를 생성
            arrow_body = QPainterPath()
            start_point = points[0]
            arrow_body.moveTo(start_point[0], start_point[1])

            scr_label_pos_x = start_point[0]
            src_label_pos_y = start_point[1]
            dst_label_pos_x = 0
            dst_label_pos_y = 0
            for point in points[1:]:
                arrow_body.lineTo(point[0], point[1])
                dst_label_pos_x = point[0]
                dst_label_pos_y = point[1]

            arrow_body_item = QGraphicsPathItem(arrow_body)
            self.addToGroup(arrow_body_item)

            if src_label is not None:
                font = STREAM_WINDOW.global_font
                label = QGraphicsTextItem(src_label, self)
                label.setDefaultTextColor(Qt.black)
                label.setFont(font)

                label_height = label.boundingRect().height()
                label.setPos(scr_label_pos_x, src_label_pos_y - label_height)
                self.addToGroup(label)

            if dst_label is not None:
                font = STREAM_WINDOW.global_font
                label = QGraphicsTextItem(dst_label, self)
                label.setDefaultTextColor(Qt.black)
                label.setFont(font)

                label_height = label.boundingRect().height()
                label_width = label.boundingRect().width()
                label.setPos(dst_label_pos_x - label_width, dst_label_pos_y - label_height)
                self.addToGroup(label)

            if arrow:
                # 화살표 머리를 그리기 위한 QPainterPath를 생성
                arrow_head = QPainterPath()
                arrow_head_size = 5
                arrow_head.moveTo(0, 0)
                arrow_head.lineTo(-arrow_head_size, arrow_head_size)
                arrow_head.lineTo(-arrow_head_size, -arrow_head_size)
                arrow_head.lineTo(0, 0)

                direction = QLineF(points[-2][0], points[-2][1], points[-1][0], points[-1][1])

                # R_angle 계산 부분 수정
                R_angle = direction.angle()

                transform = QTransform()

                # transform.rotate() 부분 수정
                transform.rotate(-R_angle)
                arrow_head = transform.map(arrow_head)

                arrow_head = arrow_head.translated(points[-1][0], points[-1][1])

                arrow_head_item = QGraphicsPathItem(arrow_head)
                brush_color = QBrush(QColor("black"))  # 색상을 변경하려면 "black"을 원하는 색상으로 변경하세요.
                arrow_head_item.setBrush(brush_color)

                self.addToGroup(arrow_head_item)

    class Circle(QGraphicsEllipseItem):
        def __init__(self, x, y, r, label):
            super().__init__(x - r, y - r, 2 * r, 2 * r)
            self.setBrush(Qt.black)
            self.x = x
            self.y = y

            # 라벨 추가
            self.label = QGraphicsTextItem(label, self)
            self.label.setDefaultTextColor(Qt.white)
            self.label.setPos(x - self.label.boundingRect().width() / 2, y - self.label.boundingRect().height() / 2)

        def pos(self):
            # 노드의 중심점 반환
            return QPointF(self.rect().center())

    class ZoomableGraphicsView_Move_Individual_scene(QGraphicsView):
        def __init__(self, scene):
            super().__init__(scene)
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.setDragMode(QGraphicsView.ScrollHandDrag)  # 드래그 모드 설정

        def wheelEvent(self, event):
            zoomInFactor = 1.25
            zoomOutFactor = 1 / zoomInFactor

            if event.angleDelta().y() > 0:
                zoomFactor = zoomInFactor
            else:
                zoomFactor = zoomOutFactor

            self.scale(zoomFactor, zoomFactor)

    class ZoomableGraphicsView_Move_All_scene(QGraphicsView):
        def __init__(self, scene, views):
            super().__init__(scene)
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.other_views = views

        def wheelEvent(self, event: QWheelEvent):
            zoomInFactor = 1.25
            zoomOutFactor = 1 / zoomInFactor

            if event.angleDelta().y() > 0:
                zoomFactor = zoomInFactor
            else:
                zoomFactor = zoomOutFactor

            for view in self.other_views:
                view.scale(zoomFactor, zoomFactor)

        def mouseMoveEvent(self, event: QMouseEvent):
            super().mouseMoveEvent(event)

            # 드래그 이벤트를 다른 모든 view에 동기화합니다.
            if event.buttons() & Qt.LeftButton and self.dragMode() == QGraphicsView.ScrollHandDrag:
                for view in self.other_views:
                    view.horizontalScrollBar().setValue(self.horizontalScrollBar().value())
                    view.verticalScrollBar().setValue(self.verticalScrollBar().value())

    class NamedScene(QGraphicsScene):
        def __init__(self, name, parent=None):
            super().__init__(parent)
            self.name = name

    def __init__(self, left2right):
        super().__init__()

        """[solution] Error "QObject::startTimer: QTimer can only be used with threads started with QThread"""
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        """ call mdi main frame """
        self.ui = None
        self.setup_ui()

        """ contents of json file """
        self.json_config = dict
        self.json_config_path = None

        self.scene_Individual_Ctrl = False

        self.overall_elements_in_scene = None

        """ save """
        self.store_scene_item = []

        self.lock = threading.Lock()

        self.cnt = 0

        """ graph view direction """
        self.left2right = left2right
        self.test_information = None

    def setup_ui(self):
        rt = load_module_func(module_name="enntest.visualization.stream_window")
        self.ui = rt.Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("ENN Test Result Viewer")

    def closeEvent(self, event):
        answer = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Are you sure you want to exit?\nAll data will be lost.",
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if answer == QtWidgets.QMessageBox.Yes:
            PRINT_("Stream_MainWindow Closed")
            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event):
        pass
        # PRINT_("resizeEvent", event)

    def connectSlotSignal(self):
        PRINT_("connectSlotSignal")
        self.ui.json_pushButton.clicked.connect(self.load_stream_json)
        self.ui.savepushButton.clicked.connect(self.scene_saving)
        # self.ui.tabWidget.hide()

        """ sys.stdout redirection """
        sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)

        """ enn test"""
        self.ui.groupBox_2.hide()
        self.ui.groupBox.hide()
        self.ui.lineEdit.hide()
        self.ui.label_2.hide()
        self.ui.label.hide()
        self.ui.poslineEdit.hide()


    def normalOutputWritten(self, text):
        cursor = self.ui.logtextbrowser.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)

        cursor.movePosition(QtGui.QTextCursor.End)

        color_format = cursor.charFormat()
        if "warn" in text.lower():
            color_format.setForeground(QtCore.Qt.red)
        else:
            color_format.setForeground(QtCore.Qt.black)

        cursor.setCharFormat(color_format)
        cursor.insertText(text)

        self.ui.logtextbrowser.setTextCursor(cursor)
        self.ui.logtextbrowser.ensureCursorVisible()

    def get_os_type(self):
        if sys.platform.startswith('win'):
            return "Windows"
        elif sys.platform.startswith('linux'):
            return "Linux"
        elif sys.platform.startswith('darwin'):
            return "MacOS"
        else:
            return "Unknown"

    def scene_saving(self):
        file_path = easygui.diropenbox("Scene Saving ?")
        if file_path is not None:

            for scene in self.store_scene_item:
                if len(scene.items()) == 0:
                    print("Scene Not Selected")
                    continue

                if self.get_os_type() == "Windows":
                    # print("Scene rect:", scene.sceneRect())
                    # scene의 크기에 맞는 QImage 객체 생성                
                    image = QImage(scene.sceneRect().size().toSize(), QImage.Format_ARGB32)
                    painter = QPainter(image)
                    try:
                        scene.render(painter)
                        pixmap = QPixmap.fromImage(image)
                        savePath = os.path.join(file_path, rf"{scene.name}.png")
                        pixmap.save(savePath, "PNG")
                        print("Saved to: ", savePath)
                    finally:
                        painter.end()
                else:
                    # Get the bounding rectangle of the scene
                    scene_rect = scene.itemsBoundingRect()
                    if scene_rect.isNull():
                        print("Scene Bounding Rect is Null")
                        continue

                    # Create a QImage with the correct size
                    image = QImage(scene_rect.size().toSize(), QImage.Format_ARGB32)
                    image.fill(Qt.transparent)  # Fill the image with transparency

                    # Create a QPainter to render the scene into the image
                    painter = QPainter(image)
                    try:
                        # Translate the painter so the scene contents are rendered correctly
                        painter.translate(-scene_rect.topLeft())
                        scene.render(painter)
                        pixmap = QPixmap.fromImage(image)
                        savePath = os.path.join(file_path, f"{scene.name}.png")

                        if pixmap.save(savePath, "PNG"):
                            print(f"Saved to: {savePath}")
                        else:
                            print(f"Failed to save: {savePath}")
                    except Exception as e:
                        print(f"An error occurred while saving the scene: {e}")
                    finally:
                        painter.end()

    @staticmethod
    def clear_layout(layout):
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)

            # 항목 제거
            layout.removeItem(item)

            # 위젯이 있는 경우, 위젯도 삭제합니다.
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        QtWidgets.QApplication.processEvents()

    def print_Rec_Node_Information(self, object):

        # print(object.enn_label_measured_value)

        for item, value in object.enn_label_measured_value.items():
            if "best" in item:
                self.ui.best_lineEdit.setText(value)
            elif "worst" in item:
                self.ui.worst_lineEdit.setText(value)
            elif "median" in item:
                self.ui.median_lineEdit.setText(value)
            elif "%" in item:
                self.ui.nine_lineEdit.setText(value)
            elif "<avg>" in item:
                self.ui.avg_lineEdit.setText(value)
            elif "accum" in item:
                self.ui.avgaccum_lineEdit.setText(value)
            else:
                print("No Performance Item")

        with self.lock:
            for node_instance in self.overall_elements_in_scene.keys():
                if object.name == node_instance.name and object.stream_group == node_instance.stream_group:
                    pen_style = node_instance.pen().style()
                    if pen_style == Qt.DotLine:
                        node_instance.setPen(QPen(QColor(Qt.red), 1, Qt.DotLine))
                    else:
                        node_instance.setPen(QPen(QColor(Qt.red), 1, Qt.SolidLine))
                else:
                    pen_style = node_instance.pen().style()
                    if pen_style == Qt.DotLine:
                        node_instance.setPen(QPen(QColor(Qt.black), 1, Qt.DotLine))
                    else:
                        node_instance.setPen(QPen(QColor(Qt.black), 1, Qt.SolidLine))
            self.ui.lineEdit.setText(str(object.id))
            self.ui.namelineEdit.setText(object.name)
            pos = rf"{object.center_pos_x}, {object.center_pos_y}"
            self.ui.poslineEdit.setText(pos)

    @staticmethod
    def generate_scenario_ips(data):
        scenario_ips = []

        node_information = {}

        for ip in data['ips']:
            # .get() 메서드를 사용하여 'inputs'와 'outputs' 키가 없는 경우 빈 딕셔너리({})를 기본값으로 설정
            inputs = ip.get("inputs", {})
            outputs = ip.get("outputs", {})

            # 각 ip의 정보를 'node_information' 딕셔너리에 저장
            node_information[str(ip['id'])] = {
                'id': str(ip['id']),
                'name': str(ip['name']),
                'inputs': inputs,
                'outputs': outputs
            }

            if 'outputs' in ip:
                outputs = []
                for output in ip['outputs']:
                    if 'connected_ip' in output:
                        outputs.append({'connected_ip': str(output['connected_ip'])})
                if outputs:
                    scenario_ips.append(
                        {
                            'id': str(ip['id']),
                            'outputs': outputs
                        }
                    )

        return scenario_ips, node_information

    def DFS(self, graph, start_node, visited=None, path=[]):
        if visited is None:
            visited = []
        visited.append(start_node)
        path = path + [start_node]

        if start_node not in graph or not graph[start_node]:
            return [path]
        else:
            all_paths = []
            for next_node in graph[start_node]:
                if next_node not in visited:
                    new_paths = self.DFS(graph, next_node, visited[:], path)
                    all_paths.extend(new_paths)
            return all_paths

    def node2node_horizontal_direction(self, scene, src_node_instance, dst_node_instance, src_node, dst_node,
                                       node_info):

        """
        src에서 dst node로 나갈 때 어떤 dst로 나가는지 확인해서 output type과
        dst에서 받을 때 어떤 src에서 오는지 확인해서 해당 input type 확인
        """
        src_output_type = ''
        dst_input_type = ''
        src_output_size = ''
        dst_input_size = ''

        for output in node_info[src_node]["outputs"]:
            if int(dst_node) == output["connected_ip"]:
                src_output_type = output["type"]
                src_output_size = rf"{output['width']} {output['height']}"
                break

        for input_ in node_info[dst_node]["inputs"]:
            if int(src_node) == input_["connected_ip"]:
                dst_input_type = input_["type"]
                dst_input_size = rf"{input_['width']} {input_['height']}"
                break
        PRINT_(src_node, dst_node, src_output_type, dst_input_type)

        """ output, input type에 따라 화살표 모양 설정 """
        if src_output_type == "OTF" and dst_input_type == "OTF":
            # src 노드의 오른쪽 경계에서 dst 노드의 왼쪽 경계로 선을 연결하기 위한 좌표 계산
            if self.left2right:
                src_line_x = src_node_instance.right_center_x
                src_line_y = src_node_instance.right_center_y
                dst_line_x = dst_node_instance.left_center_x
                dst_line_y = dst_node_instance.left_center_y

            else:
                src_line_x = src_node_instance.bottom_center_x
                src_line_y = src_node_instance.bottom_center_y
                dst_line_x = dst_node_instance.top_center_x
                dst_line_y = dst_node_instance.top_center_y

            # 좌우 노드 사이에 선 그리기
            points = [(src_line_x, src_line_y), (dst_line_x, dst_line_y)]

            # for enn
            line = self.MyPathItem(points, src_label='', dst_label=dst_input_size, arrow=True)
            # line = self.MyPathItem(points, src_label=src_output_size, dst_label=dst_input_size, arrow=True)

            scene.addItem(line)

        elif src_output_type == "M2M" and dst_input_type == "M2M":
            # src의 output
            src_line_x = src_node_instance.right_center_x  # src 노드의 오른쪽 경계
            src_line_y = src_node_instance.right_center_y
            bending_x = src_line_x + STREAM_WINDOW.global_node2node_offset_width // 2 - 10
            bending_y = src_line_y

            points = [(src_line_x, src_line_y), (bending_x, bending_y)]
            line = self.MyPathItem(points, src_label=src_output_size, arrow=False)
            scene.addItem(line)

            src_line_x = bending_x
            src_line_y = bending_y

            dst_line_x = src_line_x  # src 노드의 오른쪽 경계
            dst_line_y = src_node_instance.bottom_center_y

            points = [(src_line_x, src_line_y), (dst_line_x, dst_line_y)]
            line = self.MyPathItem(points, arrow=True)
            scene.addItem(line)

            # dst의 input
            src_line_x = dst_node_instance.left_center_x - STREAM_WINDOW.global_node2node_offset_width // 2 + 10
            src_line_y = dst_node_instance.bottom_center_y
            bending_x = src_line_x
            bending_y = dst_node_instance.left_center_y

            points = [(src_line_x, src_line_y), (bending_x, bending_y)]
            line = self.MyPathItem(points, arrow=False)
            scene.addItem(line)

            src_line_x = bending_x
            src_line_y = bending_y
            dst_line_x = dst_node_instance.left_center_x  # dst 노드의 왼쪽 경계
            dst_line_y = dst_node_instance.left_center_y

            points = [(src_line_x, src_line_y), (dst_line_x, dst_line_y)]
            line = self.MyPathItem(points, dst_label=dst_input_size, arrow=True)
            scene.addItem(line)

    def node2node_vertical_direction(self, scene, current_branch_idx, src_node_instance, dst_node_instance, src_node,
                                     dst_node,
                                     node_track):

        if current_branch_idx < 1:
            return

        """ 위에서 아래로 선 그리기 """
        if src_node in node_track.keys():
            start_node_pos_x = node_track[src_node].bottom_center_x
            start_node_pos_y = node_track[src_node].bottom_center_y
            duplicated_node_idx = node_track[src_node].branch_idx

            dst_line_x = src_node_instance.top_center_x
            dst_line_y = src_node_instance.top_center_y

            """ 중복된 노드가 이전 노드 인지 아니면 자기 자신 노드 판단 해서 자기 자신 노드 라면 라인 연결 생략 """
            if not (duplicated_node_idx == current_branch_idx):
                points = [(start_node_pos_x, start_node_pos_y), (dst_line_x, dst_line_y)]
                line = self.MyPathItem(points, arrow=True)
                scene.addItem(line)

        """ 아래서 위로 선 그리기 """
        if dst_node in node_track.keys():
            dst_line_x = node_track[dst_node].bottom_center_x
            dst_line_y = node_track[dst_node].bottom_center_y
            duplicated_node_idx = node_track[dst_node].branch_idx

            start_node_pos_x = dst_node_instance.top_center_x
            start_node_pos_y = dst_node_instance.top_center_y

            """ 중복된 노드가 이전 노드 인지 아니면 자기 자신 노드 판단 해서 자기 자신 노드 라면 라인 연결 생략 """
            if not (duplicated_node_idx == current_branch_idx):
                points = [(start_node_pos_x, start_node_pos_y), (dst_line_x, dst_line_y)]
                line = self.MyPathItem(points, arrow=True)
                scene.addItem(line)

    def draw_node(self, scene, stream_name, scenario, node_info, all_node):
        existence = []
        node_track = {}

        if not self.left2right:
            STREAM_WINDOW.global_node_width = 250

        width = STREAM_WINDOW.global_node_width
        height = STREAM_WINDOW.global_node_height
        dX = width + STREAM_WINDOW.global_node2node_offset_width  # 원소 간의 가로 간격
        dY = height + STREAM_WINDOW.global_node2node_offset_height  # 원소 간의 세로 간격

        # label = scene.addText(
        #     f"NNC Model: {scenario['nnc_model']}\nInput Binary: {scenario['input_binary']}\nGolden Binary: {scenario['golden_binary']}\n\n")
        # for enntest
        label = scene.addText(f"{self.test_information}")

        label.setPos(-width // 2, 0)  # 레이블의 위치 설정
        font = STREAM_WINDOW.global_font
        label.setFont(font)

        # label의 바운딩 박스에서 높이를 얻음
        labelHeight = label.boundingRect().height()
        initialYOffset = labelHeight  # 레이블 아래에 추가될 노드들의 초기 Y 좌표 오프셋

        labelWidth = label.boundingRect().width()
        initialXOffset = labelWidth

        for branch_idx, path in enumerate(all_node):
            for node_idx, node in enumerate(path):
                # print(node_idx, node)

                if node not in existence:
                    existence.append(node)

                    src_node = node[0]
                    dst_node = node[1]

                    width = STREAM_WINDOW.global_node_width
                    height = STREAM_WINDOW.global_node_height
                    """ 
                    dst node가 존재하지 않으면 src, dst 모두 skip
                    예를 들어 ip 8에서 output connected node가 9라고 했는데 json을 보면 9번 노드가 없다.
                    """
                    if dst_node not in node_info.keys():
                        continue

                    """ src node의 name 정보 노드에 표시하기 위해 해당 노드가 속한 ip의 이름 추출 """
                    if src_node in node_info.keys():
                        label_name = node_info[src_node]["name"]
                    else:
                        label_name = "Node Not Existed"

                    """ src node가 이미 그려진 경우라면 이미 그려진 노드의 x 위치 정보를 이용"""
                    how_to_draw_duplicated_rec = 0

                    if src_node in node_track.keys():
                        if self.left2right:
                            src_pos_x = node_track[src_node].center_pos_x
                            src_pos_y = branch_idx * dY + initialYOffset  # 레이블 아래에 위치하도록 Y 좌표 조정
                        else:
                            src_pos_x = dst_pos_x  # branch_idx * dX + initialYOffset
                            src_pos_y = dst_pos_y  # node_track[src_node].center_pos_y  (node_idx + 1) * dY #src_pos_y
                            # + dY node_idx * dY  # -------------- 2

                        if branch_idx != 0 and node_track[src_node].branch_idx != branch_idx:
                            src_node_instance = self.MyGraphicsRectItem(stream_name, branch_idx, "", src_node,
                                                                        how_to_draw_duplicated_rec,
                                                                        how_to_draw_duplicated_rec,
                                                                        node_info,
                                                                        instance_center_pos_x=src_pos_x,
                                                                        instance_center_pos_y=src_pos_y, overlap=True)
                        else:
                            src_node_instance = self.MyGraphicsRectItem(stream_name, branch_idx, label_name, src_node,
                                                                        width,
                                                                        height,
                                                                        node_info,
                                                                        instance_center_pos_x=src_pos_x,
                                                                        instance_center_pos_y=src_pos_y, overlap=True)

                    else:
                        if self.left2right:
                            src_pos_x = node_idx * dX
                            src_pos_y = branch_idx * dY + initialYOffset  # 레이블 아래에 위치하도록 Y 좌표 조정
                        else:
                            src_pos_x = branch_idx * dX + initialXOffset
                            src_pos_y = node_idx * dY  # -------------------------------- 1

                        src_node_instance = self.MyGraphicsRectItem(stream_name, branch_idx, label_name, src_node,
                                                                    width,
                                                                    height,
                                                                    node_info,
                                                                    instance_center_pos_x=src_pos_x,
                                                                    instance_center_pos_y=src_pos_y)
                        node_track[src_node] = src_node_instance

                    src_node_instance.emitter.notification.connect(self.print_Rec_Node_Information)
                    scene.addItem(src_node_instance)

                    """ dst node의 name 정보 노드에 표시하기 위해 해당 노드가 속한 ip의 이름 추출 """
                    if dst_node in node_info.keys():
                        label_name = node_info[dst_node]["name"]
                    else:
                        label_name = "Node Not Existed"

                    """ dst node가 이미 그려진 경우라면 이미 그려진 노드의 x 위치 정보를 이용"""
                    if dst_node in node_track.keys():
                        if self.left2right:
                            dst_pos_x = node_track[dst_node].center_pos_x
                            dst_pos_y = branch_idx * dY + initialYOffset  # 레이블 아래에 위치하도록 Y 좌표 조정
                        else:
                            dst_pos_x = src_pos_x
                            dst_pos_y = src_pos_y + dY + 150

                            # src_pos_x = branch_idx * dX + initialXOffset  # 레이블 아래에 위치하도록 Y 좌표 조정
                            # src_pos_y = node_idx * dY + 200

                        if branch_idx != 0 and node_track[dst_node].branch_idx != branch_idx:
                            dst_node_instance = self.MyGraphicsRectItem(stream_name, branch_idx, "", dst_node,
                                                                        how_to_draw_duplicated_rec,
                                                                        how_to_draw_duplicated_rec,
                                                                        node_info,
                                                                        instance_center_pos_x=dst_pos_x,
                                                                        instance_center_pos_y=dst_pos_y, overlap=True)
                        else:
                            dst_node_instance = self.MyGraphicsRectItem(stream_name, branch_idx, label_name, dst_node,
                                                                        width,
                                                                        height,
                                                                        node_info,
                                                                        instance_center_pos_x=dst_pos_x,
                                                                        instance_center_pos_y=dst_pos_y, overlap=True)

                    else:
                        if self.left2right:
                            dst_pos_x = (node_idx + 1) * dX
                            dst_pos_y = branch_idx * dY + initialYOffset  # 레이블 아래에 위치하도록 Y 좌표 조정
                        else:
                            dst_pos_x = branch_idx * dX + initialXOffset
                            # dst_pos_x = src_pos_x #branch_idx * dX + initialXOffset
                            dst_pos_y = src_pos_y + dY + 50

                        dst_node_instance = self.MyGraphicsRectItem(stream_name, branch_idx, label_name, dst_node,
                                                                    width,
                                                                    height,
                                                                    node_info,
                                                                    instance_center_pos_x=dst_pos_x,
                                                                    instance_center_pos_y=dst_pos_y)
                        node_track[dst_node] = dst_node_instance

                    dst_node_instance.emitter.notification.connect(self.print_Rec_Node_Information)
                    scene.addItem(dst_node_instance)

                    """ Node to Node Line 으로 연결 """
                    self.node2node_horizontal_direction(scene, src_node_instance, dst_node_instance, src_node,
                                                        dst_node, node_info)

                    self.node2node_vertical_direction(scene, branch_idx, src_node_instance, dst_node_instance, src_node,
                                                      dst_node, node_track)

                    self.overall_elements_in_scene[src_node_instance] = src_node
                    self.overall_elements_in_scene[dst_node_instance] = dst_node

    def draw_node_edge(self, json_data=None):
        self.clear_layout(layout=self.ui.diagram_gridLayout)
        self.overall_elements_in_scene = {}
        self.store_scene_item = []

        if not self.scene_Individual_Ctrl:
            views = []

        for stream_idx, (stream_name, kpi_scenarios) in enumerate(json_data.items()):
            for scenario_idx, scenario in enumerate(kpi_scenarios):
                scene = self.NamedScene(rf"{stream_idx}_{scenario['input_binary']}_{scenario['golden_binary']}")

                if self.scene_Individual_Ctrl:
                    view = self.ZoomableGraphicsView_Move_Individual_scene(scene)
                else:
                    view = self.ZoomableGraphicsView_Move_All_scene(scene, views)
                    views.append(view)

                view.setViewportMargins(20, 20, 10, 0)  # 왼쪽, 위, 오른쪽, 아래 여백 설정

                if self.left2right:
                    view.setAlignment(Qt.AlignLeft)
                else:
                    view.setAlignment(Qt.AlignTop)

                # ==================================================================================================
                # 1. json에서 ips dict 부분만 추출 (scenario)해서 노드만 해당 노드의 output connected id 부분을 추출
                # 2. 1에서 추출한 노드 정보를 이용하여 DFS 이용해서 가능한 모든 path 추출
                # 3. 2에서 추출한 path에 대해서 (출발 노드, 도착 노드)와 같이 pair 형태로 저장 --> all_node

                # scenario DFS 돌리기 위해 format 변환
                scenario_ips, node_info = self.generate_scenario_ips(data=scenario)

                # scenario_ips 그래프 형태로 변환
                graph = {ips['id']: [output['connected_ip'] for output in ips['outputs']] for ips in scenario_ips}
                # print("graph")
                # print(graph)
                start = str(scenario["id"])
                all_paths = self.DFS(graph, start)
                # print(rf"stream Name: {stream_name},  scenario_name: {scenario['name']}, path: {all_paths}")

                # all_path 대해서 순서 쌍으로 변환
                all_node = []
                for path in all_paths:
                    temp = []
                    for j in range(len(path) - 1):
                        temp.append((path[j], path[j + 1]))
                    all_node.append(temp)
                # print(rf"stream Name: {stream_name},  scenario_name: {scenario['name']}, path: {all_node}")
                # ==================================================================================================
                self.draw_node(scene, stream_name, scenario, node_info, all_node)

                scroll = QScrollArea()
                scroll.setWidget(view)

                scroll.setWidgetResizable(True)

                if self.left2right:
                    self.ui.diagram_gridLayout.addWidget(scroll, scenario_idx + stream_idx + 1, 1, 1, 1)
                else:
                    self.ui.diagram_gridLayout.addWidget(scroll, 1, scenario_idx + stream_idx + 1, 1, 1)

                self.store_scene_item.append(scene)

    def json_format_converter(self, file_path, model='', input_binary='', golden_binary=''):
        self.ui.logtextbrowser.clear()

        # 빈 리스트를 만들어 데이터를 저장합니다.
        extracted_lines = []
        extracted_blocks = []

        info_inside_block = False
        start_extraction = False

        # 파일을 한 줄씩 읽어서 원하는 부분만 추출
        self.ui.logtextbrowser.clear()
        with open(file_path, 'r') as file:
            for line in file:
                modified_line = line.replace("=", "")
                print(modified_line)

                # 평가 모델, 입력 binary 정보 추출
                if line.strip().startswith('/*'):
                    info_inside_block = True

                # 블록 내부의 줄을 저장합니다.
                if info_inside_block:
                    extracted_lines.append(line.strip())

                # 블록의 끝을 찾습니다.
                if line.strip().endswith('*/'):
                    info_inside_block = False

                # <best>가 나오면 해당 부분부터 추출: 그래프로 그릴 layer로 추정 됨
                if '<best>' in line:
                    start_extraction = True

                if start_extraction:
                    extracted_blocks.append(line.strip())

                # [NN_PROF] === 형태가 나오면 이전 블록을 저장하고 더 이상 파일을 읽지 않습니다.
                if start_extraction and '[NN_PROF] ===' in line:
                    if extracted_blocks:
                        extracted_blocks = extracted_blocks[:-1]
                        info_inside_block = False
                        start_extraction = False
                        # break

        # 추출한 줄을 하나의 문자열로 합칩니다.
        self.test_information = '\n'.join(extracted_lines)
        self.test_information = "\n".join(self.test_information.split("\n")[1:-1])
        # 결과 출력
        # print(self.test_information)

        # 그래프로 그릴 블록만 dictionary로 추출
        ennresult_path = None
        if extracted_blocks:
            data = []
            for b in extracted_blocks:
                row = b.split()[1:]
                data.append(row)

            keys = data[0][:-1]  # '<best>', '<worst>', '<median>', '<90%>', '<avg>', '<avgaccum>'
            result = {}

            for row in data[1:]:
                label = row[-1].lstrip("_")
                values = row[:-1]
                result[label] = {keys[i]: values[i] for i in range(len(keys))}

            # 기존 EIST에서 개발한 스트림 윈도우 툴을 사용하고자 FORMAT만 변경
            ips = []
            for idx, (key, value) in enumerate(result.items()):
                if idx == 0:
                    ip = {
                        "id": idx,
                        "name": key,
                        "outputs": [
                            {
                                "type": "OTF",     #always should be OTF
                                "width": '',       # used
                                "height": '',      #not used
                                "connected_ip": idx + 1
                            }
                        ]
                    }
                else:
                    ip = {
                        "id": idx,
                        "name": key,
                        "inputs": [
                            {
                                "type": "OTF",
                                "width": '',
                                "height": '',
                                "connected_ip": idx - 1
                            }
                        ],
                        "outputs": [
                            {
                                "type": "OTF",
                                "width": '',
                                "height": '',
                                "connected_ip": idx + 1
                            }
                        ]
                    }
                ip["outputs"][0]["width"] = value
                ips.append(ip)

            converted_format = {
                "ENN_Test": [
                    {
                        "id": 0,
                        "nnc_model": "",   #not used
                        "input_binary": "", #not used
                        "golden_binary": "", #not used
                        "ips": 0
                    }
                ]
            }

            converted_format["ENN_Test"][0]["ips"] = ips

            file_path_without_extension, extension = os.path.splitext(file_path)

            # 확장자가 .txt인 경우 .json으로 변경
            if extension.lower() == ".txt":
                ennresult_path = file_path_without_extension + ".json"
            else:
                ennresult_path = file_path  # .txt 확장자가 아니면 그대로 반환

            with open(ennresult_path, 'w') as file:
                json.dump(converted_format, file, indent=4)
            return ennresult_path
        else:
            answer = QtWidgets.QMessageBox.information(self,
                                                       "Warning Message",
                                                       "File that you test is not a profile file\nRe-analyze with "
                                                       "'--profile summary'",
                                                       QtWidgets.QMessageBox.Ok)

            # if answer == QtWidgets.QMessageBox.Ok:
            #     PRINT_("Stream_MainWindow Closed")
            #     event.accept()
            #
            #
            # print("\n")
            # print("[Warning] : File that you test is not a profile file")
            return ennresult_path

    def load_stream_json(self):
        self.ui.logtextbrowser.clear()
        self.json_config_path = None
        self.json_config_path = easygui.fileopenbox(msg="Select a .txt file",
                                                    title="Open Text File",
                                                    default="*.txt",
                                                    filetypes=["*.txt"]
                                                    )
        if self.json_config_path is None:
            return

        self.json_config_path = self.json_format_converter(file_path=self.json_config_path)

        if self.json_config_path is not None:
            PRINT_("load_success")
            self.ui.name_lineEdit.setText(self.json_config_path)

            self.json_config = {}
            with open(self.json_config_path, "r") as f:
                self.json_config = json.load(f)

            PRINT_(self.json_config)

            self.draw_node_edge(json_data=self.json_config)
        else:
            self.ui.name_lineEdit.clear()
            print("[Warning] File that you selected is Not a profile file")

    def draw_enntest_result(self, output_json_file='', model='', input_binary='', golden_binary=''):

        self.ui.logtextbrowser.clear()
        self.json_config_path = None

        self.json_config_path = self.json_format_converter(file_path=output_json_file, model=model,
                                                           input_binary=input_binary, golden_binary=golden_binary)
        # self.json_config_path = output_json_file

        if self.json_config_path is not None:
            PRINT_("load_success")
            self.ui.name_lineEdit.setText(self.json_config_path)

            self.json_config = {}
            with open(self.json_config_path, "r") as f:
                self.json_config = json.load(f)

            PRINT_(self.json_config)

            self.draw_node_edge(json_data=self.json_config)
        else:
            self.ui.name_lineEdit.clear()
            PRINT_("load_fail")

        # #################################################################################################################


def graph_view(output_json_file, direction):
    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    ui = STREAM_WINDOW(left2right=direction)
    ui.showMaximized()
    ui.connectSlotSignal()

    # added for enntest test
    ui.draw_enntest_result(output_json_file=output_json_file, model="", input_binary="", golden_binary="")

    sys.exit(app.exec_())


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    ui = STREAM_WINDOW(left2right=False)
    ui.showMaximized()
    ui.show()
    ui.connectSlotSignal()
    sys.exit(app.exec_())
