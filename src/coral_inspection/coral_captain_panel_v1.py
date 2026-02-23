# # # #!/usr/bin/env python3
# # # # -*- coding: utf-8 -*-

# # # """
# # # Coral Captain Standalone GUI

# # # Standalone Qt + rospy dashboard for your coral LLM + executor stack.

# # # Features:
# # # - Prompt input -> /coral_captain/user_prompt
# # # - Prompt history (within session)
# # # - Mission memory summary              <- /coral_captain/memory_state
# # # - Approve & Execute button            -> /coral_action_executor/execute_plan (Trigger)
# # # - Emergency stop                      -> /bluerov2/hold_vehicle (uuv_control_msgs/Hold)
# # # - Vehicle State Dashboard             <- /bluerov2/pose_gt (depth, speed, heading, x, y)
# # # - XY mini-map (live track)            <- /bluerov2/pose_gt
# # # - Depth vs sample plot (matplotlib)   <- /bluerov2/pose_gt
# # # - Live cameras                        <- /bluerov2/bluerov2/camera_front/camera_image
# # #                                          /bluerov2/bluerov2/camera_down/camera_image
# # # - Executor log (filtered /rosout)     <- /rosout
# # # """

# # # import json
# # # import math
# # # import sys

# # # import rospy
# # # import numpy as np

# # # from std_msgs.msg import String as StringMsg
# # # from std_srvs.srv import Trigger, TriggerRequest
# # # from uuv_control_msgs.srv import Hold
# # # from nav_msgs.msg import Odometry
# # # from sensor_msgs.msg import Image
# # # from rosgraph_msgs.msg import Log as RosoutLog

# # # from python_qt_binding import QtWidgets, QtGui, QtCore

# # # try:
# # #     from tf.transformations import euler_from_quaternion
# # #     _HAS_TF = True
# # # except ImportError:
# # #     _HAS_TF = False

# # # try:
# # #     from cv_bridge import CvBridge
# # #     _HAS_BRIDGE = True
# # # except ImportError:
# # #     _HAS_BRIDGE = False

# # # # matplotlib (no global style, no seaborn)
# # # from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# # # from matplotlib.figure import Figure


# # # # ---------------------------------------------------------------------------
# # # # XY mini-map widget (dynamic scaling)
# # # # ---------------------------------------------------------------------------
# # # class XYMapWidget(QtWidgets.QWidget):
# # #     """
# # #     Simple 2D map that shows the ROV X/Y track in world coordinates.

# # #     - Tracks recent pose history.
# # #     - Dynamically scales the view so motion is clearly visible.
# # #     - Can optionally clamp to world_min/max (if provided).
# # #     """

# # #     def __init__(self, parent=None,
# # #                  min_x=None, max_x=None,
# # #                  min_y=None, max_y=None):
# # #         super(XYMapWidget, self).__init__(parent)
# # #         self._pose_history = []
# # #         self._max_history = 500
# # #         self._x = None
# # #         self._y = None

# # #         # Optional world bounds (used for clamping only, not fixed scale)
# # #         self._world_min_x = min_x
# # #         self._world_max_x = max_x
# # #         self._world_min_y = min_y
# # #         self._world_max_y = max_y

# # #     def minimumSizeHint(self):
# # #         return QtCore.QSize(160, 160)

# # #     def sizeHint(self):
# # #         return QtCore.QSize(220, 220)

# # #     def update_pose(self, x, y):
# # #         self._x = float(x)
# # #         self._y = float(y)
# # #         self._pose_history.append((self._x, self._y))
# # #         if len(self._pose_history) > self._max_history:
# # #             self._pose_history.pop(0)
# # #         self.update()

# # #     def paintEvent(self, event):
# # #         painter = QtGui.QPainter(self)
# # #         rect = self.rect()

# # #         painter.fillRect(rect, QtGui.QColor(245, 245, 245))

# # #         if not self._pose_history:
# # #             painter.setPen(QtGui.QColor(120, 120, 120))
# # #             painter.drawText(rect, QtCore.Qt.AlignCenter, "No pose yet")
# # #             return

# # #         w = rect.width()
# # #         h = rect.height()

# # #         xs = [p[0] for p in self._pose_history]
# # #         ys = [p[1] for p in self._pose_history]

# # #         min_x = min(xs)
# # #         max_x = max(xs)
# # #         min_y = min(ys)
# # #         max_y = max(ys)

# # #         # Clamp to world bounds if provided
# # #         if self._world_min_x is not None:
# # #             min_x = max(min_x, self._world_min_x)
# # #         if self._world_max_x is not None:
# # #             max_x = min(max_x, self._world_max_x)
# # #         if self._world_min_y is not None:
# # #             min_y = max(min_y, self._world_min_y)
# # #         if self._world_max_y is not None:
# # #             max_y = min(max_y, self._world_max_y)

# # #         # Ensure non-zero extents
# # #         if max_x - min_x < 1e-3:
# # #             max_x = min_x + 1.0
# # #         if max_y - min_y < 1e-3:
# # #             max_y = min_y + 1.0

# # #         # Padding
# # #         pad_x = 0.1 * (max_x - min_x)
# # #         pad_y = 0.1 * (max_y - min_y)
# # #         min_x -= pad_x
# # #         max_x += pad_x
# # #         min_y -= pad_y
# # #         max_y += pad_y

# # #         def world_to_screen(wx, wy):
# # #             nx = (wx - min_x) / (max_x - min_x)
# # #             ny = (wy - min_y) / (max_y - min_y)
# # #             sx = rect.left() + nx * (w - 10) + 5
# # #             sy = rect.top() + (1.0 - ny) * (h - 10) + 5
# # #             return int(sx), int(sy)

# # #         painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

# # #         # Grid
# # #         painter.setPen(QtGui.QPen(QtGui.QColor(210, 210, 210), 1))
# # #         for i in range(1, 4):
# # #             x = rect.left() + i * rect.width() / 4.0
# # #             y = rect.top() + i * rect.height() / 4.0
# # #             painter.drawLine(int(x), rect.top(), int(x), rect.bottom())
# # #             painter.drawLine(rect.left(), int(y), rect.right(), int(y))

# # #         # Path
# # #         painter.setPen(QtGui.QPen(QtGui.QColor(0, 120, 215), 2))
# # #         for i in range(1, len(self._pose_history)):
# # #             x1, y1 = world_to_screen(*self._pose_history[i - 1])
# # #             x2, y2 = world_to_screen(*self._pose_history[i])
# # #             painter.drawLine(x1, y1, x2, y2)

# # #         # Current position
# # #         if self._x is not None and self._y is not None:
# # #             cx, cy = world_to_screen(self._x, self._y)
# # #             painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 180, 150)))
# # #             painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 1))
# # #             r = 5
# # #             painter.drawEllipse(QtCore.QPoint(cx, cy), r, r)

# # #         # Axis labels
# # #         painter.setPen(QtGui.QColor(80, 80, 80))
# # #         label_rect_x = QtCore.QRect(rect.left(), rect.bottom() - 18, rect.width(), 16)
# # #         painter.drawText(label_rect_x, QtCore.Qt.AlignCenter, "X (m)")
# # #         label_rect_y = QtCore.QRect(rect.left() + 4, rect.top(), 40, rect.height())
# # #         painter.drawText(label_rect_y, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, "Y (m)")


# # # # ---------------------------------------------------------------------------
# # # # Image viewer widget (auto-fit, no wheel zoom, fixed size)
# # # # ---------------------------------------------------------------------------
# # # class ImageViewWidget(QtWidgets.QLabel):
# # #     """
# # #     Simple image viewer:

# # #     - Shows the latest frame.
# # #     - Fixed size (so the layout is stable).
# # #     - Automatically rescales inside that fixed box.
# # #     - No wheel zoom (wheel events ignored).
# # #     """

# # #     def __init__(self, parent=None):
# # #         super(ImageViewWidget, self).__init__(parent)
# # #         self._qimage = None
# # #         self._pixmap = None

# # #         self.setAlignment(QtCore.Qt.AlignCenter)
# # #         self.setFrameShape(QtWidgets.QFrame.Box)

# # #         # FIXED SIZE for camera views
# # #         self.setFixedSize(360, 220)
# # #         size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed,
# # #                                             QtWidgets.QSizePolicy.Fixed)
# # #         self.setSizePolicy(size_policy)

# # #     def set_image(self, qimage: QtGui.QImage):
# # #         if qimage is None or qimage.isNull():
# # #             return
# # #         self._qimage = qimage
# # #         self._pixmap = QtGui.QPixmap.fromImage(qimage)
# # #         self._update_view()

# # #     def _update_view(self):
# # #         if self._pixmap is None or self._pixmap.isNull():
# # #             self.setPixmap(QtGui.QPixmap())
# # #             self.setText("No image")
# # #             return

# # #         self.setText("")
# # #         scaled = self._pixmap.scaled(
# # #             self.size(),
# # #             QtCore.Qt.KeepAspectRatio,
# # #             QtCore.Qt.SmoothTransformation
# # #         )
# # #         self.setPixmap(scaled)

# # #     def resizeEvent(self, event):
# # #         super(ImageViewWidget, self).resizeEvent(event)
# # #         self._update_view()

# # #     def wheelEvent(self, event: QtGui.QWheelEvent):
# # #         event.ignore()  # disable zoom


# # # # ---------------------------------------------------------------------------
# # # # Depth vs sample plot using matplotlib
# # # # ---------------------------------------------------------------------------
# # # class DepthPlotCanvas(FigureCanvas):
# # #     """
# # #     Simple scrolling depth-vs-sample plot.

# # #     x-axis = sample index (0, 1, 2, ...)
# # #     y-axis = depth in meters (positive down).
# # #     """

# # #     def __init__(self, parent=None, max_points=300):
# # #         self._fig = Figure(figsize=(3, 2))
# # #         self._ax = self._fig.add_subplot(111)
# # #         self._ax.set_xlabel("Samples")
# # #         self._ax.set_ylabel("Depth (m)")
# # #         self._ax.invert_yaxis()
# # #         self._ax.grid(True)

# # #         super(DepthPlotCanvas, self).__init__(self._fig)
# # #         self.setParent(parent)

# # #         self._max_points = max_points
# # #         self._xs = []
# # #         self._ys = []
# # #         (self._line,) = self._ax.plot([], [])  # default colors

# # #     def add_sample(self, depth: float):
# # #         idx = self._xs[-1] + 1 if self._xs else 0
# # #         self._xs.append(idx)
# # #         self._ys.append(depth)

# # #         # Keep only the last max_points
# # #         if len(self._xs) > self._max_points:
# # #             self._xs = self._xs[-self._max_points:]
# # #             self._ys = self._ys[-self._max_points:]

# # #         self._line.set_data(self._xs, self._ys)
# # #         self._ax.relim()
# # #         self._ax.autoscale_view()
# # #         self.draw_idle()


# # # # ---------------------------------------------------------------------------
# # # # Main GUI widget (no rqt Plugin, just QWidget)
# # # # ---------------------------------------------------------------------------
# # # class CoralCaptainWidget(QtWidgets.QWidget):
# # #     # Signals for data coming from ROS threads
# # #     front_image_signal = QtCore.Signal(QtGui.QImage)
# # #     down_image_signal = QtCore.Signal(QtGui.QImage)
# # #     pose_signal = QtCore.Signal(float, float, float, float, float)  # x, y, depth, speed, heading
# # #     exec_log_signal = QtCore.Signal(str)

# # #     def __init__(self, parent=None):
# # #         super(CoralCaptainWidget, self).__init__(parent)

# # #         # Parameters (read from ROS params so behaviour matches plugin)
# # #         self._pose_topic = rospy.get_param("~pose_topic", "/bluerov2/pose_gt")
# # #         self._front_cam_topic = rospy.get_param(
# # #             "~front_cam_topic", "/bluerov2/bluerov2/camera_front/camera_image"
# # #         )
# # #         self._down_cam_topic = rospy.get_param(
# # #             "~down_cam_topic", "/bluerov2/bluerov2/camera_down/camera_image"
# # #         )

# # #         # Optional world bounds for XY map (used for clamping, not fixed axes)
# # #         self._world_min_x = rospy.get_param("~world_min_x", None)
# # #         self._world_max_x = rospy.get_param("~world_max_x", None)
# # #         self._world_min_y = rospy.get_param("~world_min_y", None)
# # #         self._world_max_y = rospy.get_param("~world_max_y", None)

# # #         # Service names (configurable)
# # #         self._exec_service_name = rospy.get_param(
# # #             "~execute_service", "/coral_action_executor/execute_plan"
# # #         )
# # #         self._hold_service_name = rospy.get_param(
# # #             "~hold_service", "/bluerov2/hold_vehicle"
# # #         )

# # #         # Internal state (textual data)
# # #         self._llm_status_raw = None
# # #         self._exec_status_raw = None
# # #         self._memory_raw = None

# # #         # Internal state (images)
# # #         self._front_qimage = None
# # #         self._down_qimage = None
# # #         self._front_bytes = None
# # #         self._down_bytes = None

# # #         # ROS pubs/subs/clients
# # #         self._prompt_pub = rospy.Publisher(
# # #             "/coral_captain/user_prompt", StringMsg, queue_size=10
# # #         )

# # #         self._llm_status_sub = rospy.Subscriber(
# # #             "/coral_captain/llm_status", StringMsg, self._on_llm_status, queue_size=10
# # #         )

# # #         self._exec_status_sub = rospy.Subscriber(
# # #             "/coral_captain/execution_status", StringMsg,
# # #             self._on_exec_status, queue_size=10
# # #         )

# # #         self._memory_sub = rospy.Subscriber(
# # #             "/coral_captain/memory_state", StringMsg,
# # #             self._on_memory_state, queue_size=10
# # #         )

# # #         self._odom_sub = rospy.Subscriber(
# # #             self._pose_topic, Odometry, self._on_odom, queue_size=1
# # #         )

# # #         # Executor log from /rosout
# # #         self._rosout_sub = rospy.Subscriber(
# # #             "/rosout", RosoutLog, self._on_rosout_log, queue_size=100
# # #         )

# # #         if _HAS_BRIDGE:
# # #             self._bridge = CvBridge()
# # #             rospy.loginfo("[CoralCaptainGUI] cv_bridge OK, subscribing to cameras:")
# # #             rospy.loginfo("  front_cam_topic = %s", self._front_cam_topic)
# # #             rospy.loginfo("  down_cam_topic  = %s", self._down_cam_topic)

# # #             self._front_cam_sub = rospy.Subscriber(
# # #                 self._front_cam_topic, Image, self._on_front_image, queue_size=1
# # #             )
# # #             self._down_cam_sub = rospy.Subscriber(
# # #                 self._down_cam_topic, Image, self._on_down_image, queue_size=1
# # #             )
# # #         else:
# # #             self._bridge = None
# # #             self._front_cam_sub = None
# # #             self._down_cam_sub = None
# # #             rospy.logwarn("[CoralCaptainGUI] cv_bridge not available; camera views disabled.")

# # #         # Service clients
# # #         self._exec_client = None       # execute plan (Trigger)
# # #         self._hold_client = None       # emergency stop (Hold)

# # #         # Build UI & styling
# # #         self._build_ui()
# # #         self._apply_stylesheet()

# # #         # Size
# # #         self.setWindowTitle("Coral Captain")
# # #         self.setWindowIcon(QtGui.QIcon.fromTheme("applications-science"))
# # #         self.setMinimumSize(1200, 650)

# # #         # Connect signals (ROS threads -> GUI thread)
# # #         self.front_image_signal.connect(self._set_front_image)
# # #         self.down_image_signal.connect(self._set_down_image)
# # #         self.pose_signal.connect(self._set_pose)
# # #         self.exec_log_signal.connect(self._append_exec_log)

# # #         # Timer for textual UI (status & memory)
# # #         self._timer = QtCore.QTimer(self)
# # #         self._timer.timeout.connect(self._on_timer_tick)
# # #         self._timer.start(100)  # 10 Hz

# # #     # ------------------------------------------------------------------
# # #     # UI construction (2x3 grid)
# # #     # ------------------------------------------------------------------
# # #     def _build_ui(self):
# # #         # Grid layout: 2 rows x 3 columns
# # #         grid = QtWidgets.QGridLayout(self)
# # #         grid.setContentsMargins(6, 6, 6, 6)
# # #         grid.setSpacing(8)

# # #         # ====== Top-left: Mission Console ======
# # #         mission_box = QtWidgets.QGroupBox("Mission Console")
# # #         mission_layout = QtWidgets.QVBoxLayout(mission_box)
# # #         mission_layout.setContentsMargins(6, 6, 6, 6)
# # #         mission_layout.setSpacing(4)

# # #         history_label = QtWidgets.QLabel("Prompt history (this mission):")
# # #         self._prompt_history = QtWidgets.QPlainTextEdit()
# # #         self._prompt_history.setReadOnly(True)
# # #         self._prompt_history.setPlaceholderText("Sent prompts will appear here...")
# # #         self._prompt_history.setMinimumHeight(80)

# # #         prompt_label = QtWidgets.QLabel("LLM Prompt:")
# # #         self._prompt_edit = QtWidgets.QLineEdit()
# # #         self._prompt_edit.setPlaceholderText(
# # #             "E.g., \"Survey coral bed A, then circle site B and return home.\""
# # #         )
# # #         self._prompt_edit.returnPressed.connect(self._on_send_prompt)

# # #         btn_row = QtWidgets.QHBoxLayout()
# # #         self._btn_send = QtWidgets.QPushButton("Send Prompt")
# # #         self._btn_send.clicked.connect(self._on_send_prompt)

# # #         self._btn_clear = QtWidgets.QPushButton("Clear")
# # #         self._btn_clear.clicked.connect(self._on_clear_prompt)

# # #         self._btn_execute = QtWidgets.QPushButton("Approve & Execute Plan")
# # #         self._btn_execute.clicked.connect(self._on_execute_plan)

# # #         self._btn_emergency_stop = QtWidgets.QPushButton("EMERGENCY STOP")
# # #         self._btn_emergency_stop.setObjectName("emergencyStopButton")
# # #         self._btn_emergency_stop.clicked.connect(self._on_emergency_stop)

# # #         btn_row.addWidget(self._btn_send)
# # #         btn_row.addWidget(self._btn_clear)
# # #         btn_row.addWidget(self._btn_execute)
# # #         btn_row.addWidget(self._btn_emergency_stop)

# # #         mission_layout.addWidget(history_label)
# # #         mission_layout.addWidget(self._prompt_history)
# # #         mission_layout.addWidget(prompt_label)
# # #         mission_layout.addWidget(self._prompt_edit)
# # #         mission_layout.addLayout(btn_row)

# # #         # ====== Top-middle: Mission Memory ======
# # #         memory_box = QtWidgets.QGroupBox("Mission Memory")
# # #         memory_layout = QtWidgets.QVBoxLayout(memory_box)

# # #         summary_label = QtWidgets.QLabel("Summary:")
# # #         self._memory_summary = QtWidgets.QPlainTextEdit()
# # #         self._memory_summary.setReadOnly(True)
# # #         self._memory_summary.setPlaceholderText(
# # #             "Visited sites, completed actions, photos, events..."
# # #         )

# # #         memory_layout.addWidget(summary_label)
# # #         memory_layout.addWidget(self._memory_summary)

# # #         # ====== Top-right: Front Camera ======
# # #         front_cam_box = QtWidgets.QGroupBox("Front camera")
# # #         front_cam_layout = QtWidgets.QVBoxLayout(front_cam_box)
# # #         self._front_cam_view = ImageViewWidget()
# # #         front_cam_layout.addWidget(self._front_cam_view, alignment=QtCore.Qt.AlignCenter)

# # #         # ====== Bottom-left: Executor Log ======
# # #         log_box = QtWidgets.QGroupBox("Executor Log")
# # #         log_layout = QtWidgets.QVBoxLayout(log_box)

# # #         self._exec_log = QtWidgets.QPlainTextEdit()
# # #         self._exec_log.setReadOnly(True)

# # #         log_layout.addWidget(self._exec_log)

# # #         # ====== Bottom-middle: Vehicle State & XY Position & Depth Plot ======
# # #         vehicle_box = QtWidgets.QGroupBox("Vehicle State  /  XY Position / Depth")
# # #         vehicle_layout = QtWidgets.QVBoxLayout(vehicle_box)

# # #         labels_row = QtWidgets.QGridLayout()
# # #         self._depth_label = QtWidgets.QLabel("Depth: — m")
# # #         self._speed_label = QtWidgets.QLabel("Speed: — m/s")
# # #         self._heading_label = QtWidgets.QLabel("Heading: — °")
# # #         self._position_label = QtWidgets.QLabel("Pos: (x=—, y=—)")

# # #         labels_row.addWidget(self._depth_label,   0, 0)
# # #         labels_row.addWidget(self._speed_label,   0, 1)
# # #         labels_row.addWidget(self._heading_label, 1, 0)
# # #         labels_row.addWidget(self._position_label,1, 1)

# # #         vehicle_layout.addLayout(labels_row)

# # #         self._xy_widget = XYMapWidget(
# # #             min_x=self._world_min_x,
# # #             max_x=self._world_max_x,
# # #             min_y=self._world_min_y,
# # #             max_y=self._world_max_y
# # #         )
# # #         vehicle_layout.addWidget(self._xy_widget)

# # #         # Depth vs sample plot
# # #         self._depth_canvas = DepthPlotCanvas()
# # #         vehicle_layout.addWidget(self._depth_canvas)

# # #         # ====== Bottom-right: Downward Camera ======
# # #         down_cam_box = QtWidgets.QGroupBox("Downward camera")
# # #         down_cam_layout = QtWidgets.QVBoxLayout(down_cam_box)
# # #         self._down_cam_view = ImageViewWidget()
# # #         down_cam_layout.addWidget(self._down_cam_view, alignment=QtCore.Qt.AlignCenter)

# # #         # ---- Place all 6 boxes into a 2x3 grid ----
# # #         grid.addWidget(mission_box,   0, 0)
# # #         grid.addWidget(memory_box,    0, 1)
# # #         grid.addWidget(front_cam_box, 0, 2)

# # #         grid.addWidget(log_box,       1, 0)
# # #         grid.addWidget(vehicle_box,   1, 1)
# # #         grid.addWidget(down_cam_box,  1, 2)

# # #         grid.setRowStretch(0, 1)
# # #         grid.setRowStretch(1, 1)
# # #         grid.setColumnStretch(0, 1)
# # #         grid.setColumnStretch(1, 1)
# # #         grid.setColumnStretch(2, 1)

# # #     # ------------------------------------------------------------------
# # #     # Styling
# # #     # ------------------------------------------------------------------
# # #     def _apply_stylesheet(self):
# # #         self.setStyleSheet("""
# # #             QWidget {
# # #                 background-color: #f3f5f7;
# # #                 color: #202020;
# # #                 font-size: 12px;
# # #             }
# # #             QGroupBox {
# # #                 border: 1px solid #c0c0c0;
# # #                 border-radius: 6px;
# # #                 margin-top: 10px;
# # #                 font-weight: bold;
# # #                 font-size: 13px;
# # #                 background-color: #ffffff;
# # #             }
# # #             QGroupBox::title {
# # #                 subcontrol-origin: margin;
# # #                 subcontrol-position: top left;
# # #                 padding: 2px 8px 0 8px;
# # #             }
# # #             QPushButton {
# # #                 background-color: #ffffff;
# # #                 border: 1px solid #b0b0b0;
# # #                 padding: 4px 10px;
# # #                 border-radius: 4px;
# # #             }
# # #             QPushButton:hover {
# # #                 background-color: #e6f0ff;
# # #             }
# # #             QPushButton:pressed {
# # #                 background-color: #cadbff;
# # #             }
# # #             QPushButton#emergencyStopButton {
# # #                 background-color: #ff4a4a;
# # #                 border: 1px solid #b00000;
# # #                 color: #ffffff;
# # #                 font-weight: bold;
# # #             }
# # #             QPushButton#emergencyStopButton:hover {
# # #                 background-color: #ff7070;
# # #             }
# # #             QPushButton#emergencyStopButton:pressed {
# # #                 background-color: #e00000;
# # #             }
# # #             QPlainTextEdit, QTextEdit {
# # #                 background-color: #ffffff;
# # #                 border: 1px solid #c0c0c0;
# # #             }
# # #             QLineEdit {
# # #                 background-color: #ffffff;
# # #                 border: 1px solid #c0c0c0;
# # #                 padding: 3px 6px;
# # #             }
# # #             QLabel {
# # #                 font-size: 11px;
# # #             }
# # #         """)

# # #         self._btn_send.setIcon(QtGui.QIcon.fromTheme("mail-send"))
# # #         self._btn_clear.setIcon(QtGui.QIcon.fromTheme("edit-clear"))
# # #         self._btn_execute.setIcon(QtGui.QIcon.fromTheme("media-playback-start"))

# # #     # ------------------------------------------------------------------
# # #     # Timer tick – update text UI
# # #     # ------------------------------------------------------------------
# # #     def _on_timer_tick(self):
# # #         self._update_exec_status_view()
# # #         self._update_memory_view()

# # #     # ------------------------------------------------------------------
# # #     # Button callbacks
# # #     # ------------------------------------------------------------------
# # #     def _on_send_prompt(self):
# # #         text = self._prompt_edit.text().strip()
# # #         if not text:
# # #             QtWidgets.QMessageBox.warning(
# # #                 self, "Empty prompt", "Please enter a prompt first."
# # #             )
# # #             return

# # #         msg = StringMsg(data=text)
# # #         self._prompt_pub.publish(msg)
# # #         self._llm_status_raw = "planning: " + text

# # #         rospy.loginfo("[CoralCaptainGUI] Prompt sent: %s", text)
# # #         self._prompt_history.appendPlainText(f"> {text}")
# # #         self._prompt_edit.clear()

# # #     def _on_clear_prompt(self):
# # #         self._prompt_edit.clear()

# # #     def _on_execute_plan(self):
# # #         if self._exec_client is None:
# # #             try:
# # #                 rospy.loginfo("[CoralCaptainGUI] Waiting for execute service: %s",
# # #                               self._exec_service_name)
# # #                 rospy.wait_for_service(self._exec_service_name, timeout=1.0)
# # #                 self._exec_client = rospy.ServiceProxy(self._exec_service_name, Trigger)
# # #             except rospy.ROSException:
# # #                 QtWidgets.QMessageBox.critical(
# # #                     self,
# # #                     "Executor not available",
# # #                     "Service '{}' not available.".format(self._exec_service_name)
# # #                 )
# # #                 return

# # #         try:
# # #             resp = self._exec_client(TriggerRequest())
# # #         except Exception as e:
# # #             QtWidgets.QMessageBox.critical(
# # #                 self,
# # #                 "Execution failed",
# # #                 "Service call failed: {}".format(e)
# # #             )
# # #             return

# # #         if resp.success:
# # #             msg = resp.message or "Plan execution started."
# # #             self.exec_log_signal.emit("[GUI] execute_plan: " + msg)
# # #         else:
# # #             QtWidgets.QMessageBox.warning(
# # #                 self,
# # #                 "Execution error",
# # #                 resp.message or "Plan execution failed."
# # #             )

# # #     def _on_emergency_stop(self):
# # #         """Call uuv_control_msgs/Hold on self._hold_service_name."""
# # #         if self._hold_client is None:
# # #             try:
# # #                 rospy.loginfo("[CoralCaptainGUI] Waiting for hold service (Hold): %s",
# # #                               self._hold_service_name)
# # #                 rospy.wait_for_service(self._hold_service_name, timeout=3.0)
# # #                 self._hold_client = rospy.ServiceProxy(self._hold_service_name, Hold)
# # #             except rospy.ROSException:
# # #                 QtWidgets.QMessageBox.critical(
# # #                     self,
# # #                     "Emergency stop unavailable",
# # #                     "Service '{}' (uuv_control_msgs/Hold) not available.".format(
# # #                         self._hold_service_name
# # #                     )
# # #                 )
# # #                 return

# # #         try:
# # #             resp = self._hold_client()
# # #             ok = bool(getattr(resp, "success", True))
# # #             msg = getattr(resp, "message", "")
# # #         except Exception as e:
# # #             QtWidgets.QMessageBox.critical(
# # #                 self,
# # #                 "Emergency stop failed",
# # #                 "Service call failed: {}".format(e)
# # #             )
# # #             return

# # #         if ok:
# # #             self.exec_log_signal.emit(
# # #                 "[EMERGENCY] hold_vehicle (Hold) called successfully: {}".format(
# # #                     msg or ""
# # #                 )
# # #             )
# # #         else:
# # #             QtWidgets.QMessageBox.warning(
# # #                 self,
# # #                 "Emergency stop error",
# # #                 msg or "Vehicle hold/stop command reported failure."
# # #             )
# # #             self.exec_log_signal.emit(
# # #                 "[EMERGENCY] hold_vehicle (Hold) FAILED: {}".format(msg)
# # #             )

# # #     # ------------------------------------------------------------------
# # #     # ROS callbacks – only update state / emit signals
# # #     # ------------------------------------------------------------------
# # #     def _on_llm_status(self, msg):
# # #         self._llm_status_raw = msg.data

# # #     def _on_exec_status(self, msg):
# # #         self._exec_status_raw = msg.data

# # #     def _on_memory_state(self, msg):
# # #         self._memory_raw = msg.data

# # #     def _on_odom(self, msg):
# # #         z = msg.pose.pose.position.z
# # #         depth = -z

# # #         v = msg.twist.twist.linear
# # #         speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)

# # #         heading_deg = float('nan')
# # #         if _HAS_TF:
# # #             q = msg.pose.pose.orientation
# # #             quat = [q.x, q.y, q.z, q.w]
# # #             try:
# # #                 _, _, yaw = euler_from_quaternion(quat)
# # #                 heading_deg = (math.degrees(yaw) + 360.0) % 360.0
# # #             except Exception:
# # #                 heading_deg = float('nan')

# # #         x = msg.pose.pose.position.x
# # #         y = msg.pose.pose.position.y

# # #         self.pose_signal.emit(x, y, depth, speed, heading_deg)

# # #     def _on_front_image(self, msg):
# # #         if self._bridge is None:
# # #             return
# # #         try:
# # #             try:
# # #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
# # #             except Exception:
# # #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

# # #             if cv_img.ndim == 2:
# # #                 cv_img = np.stack([cv_img] * 3, axis=-1)

# # #             rgb = cv_img[:, :, ::-1]  # BGR -> RGB
# # #             h, w, ch = rgb.shape
# # #             bytes_per_line = ch * w
# # #             self._front_bytes = rgb.tobytes()
# # #             qimg = QtGui.QImage(
# # #                 self._front_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
# # #             )
# # #             self.front_image_signal.emit(qimg)

# # #         except Exception as e:
# # #             rospy.logwarn("[CoralCaptainGUI] Error converting front image: %s", e)

# # #     def _on_down_image(self, msg):
# # #         if self._bridge is None:
# # #             return
# # #         try:
# # #             try:
# # #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
# # #             except Exception:
# # #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

# # #             if cv_img.ndim == 2:
# # #                 cv_img = np.stack([cv_img] * 3, axis=-1)

# # #             rgb = cv_img[:, :, ::-1]
# # #             h, w, ch = rgb.shape
# # #             bytes_per_line = ch * w
# # #             self._down_bytes = rgb.tobytes()
# # #             qimg = QtGui.QImage(
# # #                 self._down_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
# # #             )
# # #             self.down_image_signal.emit(qimg)

# # #         except Exception as e:
# # #             rospy.logwarn("[CoralCaptainGUI] Error converting down image: %s", e)

# # #     def _on_rosout_log(self, msg: RosoutLog):
# # #         text = msg.msg or ""
# # #         if not text:
# # #             return

# # #         # Focus on relevant components
# # #         if ("[executor]" not in text and
# # #                 "[actions]" not in text and
# # #                 "[mission_memory]" not in text and
# # #                 "Plan published:" not in text):
# # #             return

# # #         self.exec_log_signal.emit(text)

# # #     # ------------------------------------------------------------------
# # #     # Slots in GUI thread
# # #     # ------------------------------------------------------------------
# # #     @QtCore.Slot(QtGui.QImage)
# # #     def _set_front_image(self, qimg):
# # #         self._front_qimage = qimg
# # #         if self._front_qimage is not None:
# # #             self._front_cam_view.set_image(self._front_qimage)
# # #         else:
# # #             self._front_cam_view.setText("No front camera image")

# # #     @QtCore.Slot(QtGui.QImage)
# # #     def _set_down_image(self, qimg):
# # #         self._down_qimage = qimg
# # #         if self._down_qimage is not None:
# # #             self._down_cam_view.set_image(self._down_qimage)
# # #         else:
# # #             self._down_cam_view.setText("No downward camera image")

# # #     @QtCore.Slot(float, float, float, float, float)
# # #     def _set_pose(self, x, y, depth, speed, heading_deg):
# # #         self._depth_label.setText(f"Depth: {depth:.1f} m")
# # #         self._speed_label.setText(f"Speed: {speed:.2f} m/s")
# # #         if math.isnan(heading_deg):
# # #             self._heading_label.setText("Heading: (N/A)")
# # #         else:
# # #             self._heading_label.setText(f"Heading: {heading_deg:.1f} °")
# # #         self._position_label.setText(f"Pos: (x={x:.1f}, y={y:.1f})")
# # #         self._xy_widget.update_pose(x, y)

# # #         if hasattr(self, "_depth_canvas"):
# # #             self._depth_canvas.add_sample(depth)

# # #     @QtCore.Slot(str)
# # #     def _append_exec_log(self, text):
# # #         if not text.strip():
# # #             return
# # #         self._exec_log.appendPlainText(text)

# # #     # ------------------------------------------------------------------
# # #     # UI update helpers
# # #     # ------------------------------------------------------------------
# # #     def _update_exec_status_view(self):
# # #         if self._exec_status_raw is None:
# # #             return

# # #         raw = self._exec_status_raw.strip()
# # #         if not raw:
# # #             return

# # #         state = "unknown"
# # #         try:
# # #             obj = json.loads(raw)
# # #             state = obj.get("state", "unknown")
# # #         except Exception:
# # #             state = raw

# # #         executing = state in ("executing", "executing_step")
# # #         self._btn_execute.setEnabled(not executing)

# # #         # self._btn_execute.setEnabled(!executing if False else not executing)

# # #     def _update_memory_view(self):
# # #         if self._memory_raw is None:
# # #             return

# # #         raw = self._memory_raw.strip()
# # #         if not raw:
# # #             return

# # #         try:
# # #             obj = json.loads(raw)
# # #         except Exception:
# # #             obj = None

# # #         summary = self._build_memory_summary(obj) if obj is not None else "(unable to parse memory JSON)"
# # #         self._memory_summary.setPlainText(summary)

# # #     # ------------------------------------------------------------------
# # #     # Memory summary helper
# # #     # ------------------------------------------------------------------
# # #     def _build_memory_summary(self, mem):
# # #         if not isinstance(mem, dict):
# # #             return "(invalid memory structure)"

# # #         visited = mem.get("visited_sites", [])
# # #         completed = mem.get("completed_actions", [])
# # #         photos = mem.get("photos_taken", [])
# # #         last_event = mem.get("last_event", "")
# # #         replan_events = mem.get("replan_events", [])

# # #         lines = []

# # #         if visited:
# # #             lines.append("Visited sites: " + ", ".join(map(str, visited)))
# # #         else:
# # #             lines.append("Visited sites: none yet")

# # #         if completed:
# # #             lines.append(f"Completed actions: {len(completed)}")
# # #             tail = completed[-3:]
# # #             descs = []
# # #             for c in tail:
# # #                 if isinstance(c, dict):
# # #                     a = c.get("action", "?")
# # #                     args = c.get("args", {}) if isinstance(c.get("args", {}), dict) else {}
# # #                     site = None
# # #                     if isinstance(args, dict):
# # #                         site = args.get("site") or args.get("footprint")
# # #                     if site:
# # #                         descs.append(f"{a}(site={site})")
# # #                     else:
# # #                         descs.append(a)
# # #                 else:
# # #                     descs.append(str(c))
# # #             lines.append("Recent: " + ", ".join(descs))
# # #         else:
# # #             lines.append("Completed actions: none yet")

# # #         if photos:
# # #             last = photos[-1]
# # #             if isinstance(last, dict):
# # #                 label = last.get("label", "?")
# # #             else:
# # #                 label = str(last)
# # #             lines.append(f"Photos taken: {len(photos)} (last: {label})")
# # #         else:
# # #             lines.append("Photos taken: none yet")

# # #         if last_event:
# # #             lines.append(f"Last event: {last_event}")

# # #         if replan_events:
# # #             lines.append(f"Replans triggered: {len(replan_events)}")

# # #         return "\n".join(lines)

# # #     # ------------------------------------------------------------------
# # #     # Cleanup
# # #     # ------------------------------------------------------------------
# # #     def shutdown(self):
# # #         for sub in [
# # #             self._llm_status_sub,
# # #             self._exec_status_sub,
# # #             self._memory_sub,
# # #             self._odom_sub,
# # #             self._rosout_sub,
# # #             getattr(self, "_front_cam_sub", None),
# # #             getattr(self, "_down_cam_sub", None),
# # #         ]:
# # #             try:
# # #                 if sub is not None:
# # #                     sub.unregister()
# # #             except Exception:
# # #                 pass

# # #         try:
# # #             self._prompt_pub.unregister()
# # #         except Exception:
# # #             pass

# # #         self._exec_client = None
# # #         self._hold_client = None


# # # # ---------------------------------------------------------------------------
# # # # Main entry point
# # # # ---------------------------------------------------------------------------
# # # def main():
# # #     rospy.init_node("coral_captain_gui", anonymous=True)

# # #     app = QtWidgets.QApplication(sys.argv)
# # #     widget = CoralCaptainWidget()
# # #     widget.show()

# # #     def on_quit():
# # #         rospy.loginfo("[CoralCaptainGUI] Shutting down GUI")
# # #         widget.shutdown()
# # #         rospy.signal_shutdown("GUI closed")

# # #     app.aboutToQuit.connect(on_quit)

# # #     sys.exit(app.exec_())


# # # if __name__ == "__main__":
# # #     main()



# # # v2

# # #!/usr/bin/env python3
# # # -*- coding: utf-8 -*-

# # """
# # Coral Captain Standalone GUI

# # Standalone Qt + rospy dashboard for your coral LLM + executor stack.

# # Features:
# # - Prompt input -> /coral_captain/user_prompt
# # - Prompt history (within session)
# # - Mission memory summary              <- /coral_captain/memory_state
# # - Approve & Execute button            -> /coral_action_executor/execute_plan (Trigger)
# # - Emergency stop                      -> /bluerov2/hold_vehicle (uuv_control_msgs/Hold)
# # - Vehicle State Dashboard             <- /bluerov2/pose_gt (depth, speed, heading, x, y)
# # - Depth vs sample plot (matplotlib)   <- /bluerov2/pose_gt
# # - X/Y vs sample plot (matplotlib)     <- /bluerov2/pose_gt
# # - Live cameras                        <- /bluerov2/bluerov2/camera_front/camera_image
# #                                          /bluerov2/bluerov2/camera_down/camera_image
# # - Executor log (filtered /rosout)     <- /rosout
# # """

# # import json
# # import math
# # import sys

# # import rospy
# # import numpy as np

# # from std_msgs.msg import String as StringMsg
# # from std_srvs.srv import Trigger, TriggerRequest
# # from uuv_control_msgs.srv import Hold
# # from nav_msgs.msg import Odometry
# # from sensor_msgs.msg import Image
# # from rosgraph_msgs.msg import Log as RosoutLog

# # from python_qt_binding import QtWidgets, QtGui, QtCore

# # try:
# #     from tf.transformations import euler_from_quaternion
# #     _HAS_TF = True
# # except ImportError:
# #     _HAS_TF = False

# # try:
# #     from cv_bridge import CvBridge
# #     _HAS_BRIDGE = True
# # except ImportError:
# #     _HAS_BRIDGE = False

# # # matplotlib (no global style, no seaborn)
# # from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# # from matplotlib.figure import Figure


# # # ---------------------------------------------------------------------------
# # # Image viewer widget (auto-fit, no wheel zoom, fixed size)
# # # ---------------------------------------------------------------------------
# # class ImageViewWidget(QtWidgets.QLabel):
# #     """
# #     Simple image viewer:

# #     - Shows the latest frame.
# #     - Fixed size (so the layout is stable).
# #     - Automatically rescales inside that fixed box.
# #     - No wheel zoom (wheel events ignored).
# #     """

# #     def __init__(self, parent=None):
# #         super(ImageViewWidget, self).__init__(parent)
# #         self._qimage = None
# #         self._pixmap = None

# #         self.setAlignment(QtCore.Qt.AlignCenter)
# #         self.setFrameShape(QtWidgets.QFrame.Box)

# #         # FIXED SIZE for camera views
# #         self.setFixedSize(360, 220)
# #         size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed,
# #                                             QtWidgets.QSizePolicy.Fixed)
# #         self.setSizePolicy(size_policy)

# #     def set_image(self, qimage: QtGui.QImage):
# #         if qimage is None or qimage.isNull():
# #             return
# #         self._qimage = qimage
# #         self._pixmap = QtGui.QPixmap.fromImage(qimage)
# #         self._update_view()

# #     def _update_view(self):
# #         if self._pixmap is None or self._pixmap.isNull():
# #             self.setPixmap(QtGui.QPixmap())
# #             self.setText("No image")
# #             return

# #         self.setText("")
# #         scaled = self._pixmap.scaled(
# #             self.size(),
# #             QtCore.Qt.KeepAspectRatio,
# #             QtCore.Qt.SmoothTransformation
# #         )
# #         self.setPixmap(scaled)

# #     def resizeEvent(self, event):
# #         super(ImageViewWidget, self).resizeEvent(event)
# #         self._update_view()

# #     def wheelEvent(self, event: QtGui.QWheelEvent):
# #         event.ignore()  # disable zoom


# # # ---------------------------------------------------------------------------
# # # Depth vs sample plot using matplotlib
# # # ---------------------------------------------------------------------------
# # class DepthPlotCanvas(FigureCanvas):
# #     """
# #     Simple scrolling depth-vs-sample plot.

# #     x-axis = sample index (0, 1, 2, ...)
# #     y-axis = depth in meters (positive down).
# #     """

# #     def __init__(self, parent=None, max_points=300):
# #         self._fig = Figure(figsize=(3, 2))
# #         self._ax = self._fig.add_subplot(111)
# #         self._ax.set_xlabel("Samples")
# #         self._ax.set_ylabel("Depth (m)")
# #         self._ax.invert_yaxis()
# #         self._ax.grid(True)

# #         super(DepthPlotCanvas, self).__init__(self._fig)
# #         self.setParent(parent)

# #         self._max_points = max_points
# #         self._xs = []
# #         self._ys = []
# #         (self._line,) = self._ax.plot([], [])  # default colors

# #     def add_sample(self, depth: float):
# #         idx = self._xs[-1] + 1 if self._xs else 0
# #         self._xs.append(idx)
# #         self._ys.append(depth)

# #         # Keep only the last max_points
# #         if len(self._xs) > self._max_points:
# #             self._xs = self._xs[-self._max_points:]
# #             self._ys = self._ys[-self._max_points:]

# #         self._line.set_data(self._xs, self._ys)
# #         self._ax.relim()
# #         self._ax.autoscale_view()
# #         self.draw_idle()


# # # ---------------------------------------------------------------------------
# # # X/Y vs sample plot using matplotlib
# # # ---------------------------------------------------------------------------
# # class XYTimePlotCanvas(FigureCanvas):
# #     """
# #     Scrolling plot of x and y vs sample index.

# #     - x-axis: sample index (0,1,2,...)
# #     - y-axis: position in meters
# #     - Two lines: x(k), y(k)
# #     """

# #     def __init__(self, parent=None, max_points=300):
# #         self._fig = Figure(figsize=(3, 2))
# #         self._ax = self._fig.add_subplot(111)
# #         self._ax.set_xlabel("Samples")
# #         self._ax.set_ylabel("Position (m)")
# #         self._ax.grid(True)

# #         super(XYTimePlotCanvas, self).__init__(self._fig)
# #         self.setParent(parent)

# #         self._max_points = max_points
# #         self._samples = []
# #         self._xs = []
# #         self._ys = []

# #         (self._line_x,) = self._ax.plot([], [], label="x")
# #         (self._line_y,) = self._ax.plot([], [], label="y")
# #         self._ax.legend(loc="upper right", fontsize=8)

# #     def add_sample(self, x: float, y: float):
# #         idx = self._samples[-1] + 1 if self._samples else 0
# #         self._samples.append(idx)
# #         self._xs.append(float(x))
# #         self._ys.append(float(y))

# #         if len(self._samples) > self._max_points:
# #             self._samples = self._samples[-self._max_points:]
# #             self._xs = self._xs[-self._max_points:]
# #             self._ys = self._ys[-self._max_points:]

# #         self._line_x.set_data(self._samples, self._xs)
# #         self._line_y.set_data(self._samples, self._ys)

# #         self._ax.relim()
# #         self._ax.autoscale_view()
# #         self.draw_idle()


# # # ---------------------------------------------------------------------------
# # # Main GUI widget (no rqt Plugin, just QWidget)
# # # ---------------------------------------------------------------------------
# # class CoralCaptainWidget(QtWidgets.QWidget):
# #     # Signals for data coming from ROS threads
# #     front_image_signal = QtCore.Signal(QtGui.QImage)
# #     down_image_signal = QtCore.Signal(QtGui.QImage)
# #     pose_signal = QtCore.Signal(float, float, float, float, float)  # x, y, depth, speed, heading
# #     exec_log_signal = QtCore.Signal(str)

# #     def __init__(self, parent=None):
# #         super(CoralCaptainWidget, self).__init__(parent)

# #         # Parameters (read from ROS params so behaviour matches plugin)
# #         self._pose_topic = rospy.get_param("~pose_topic", "/bluerov2/pose_gt")
# #         self._front_cam_topic = rospy.get_param(
# #             "~front_cam_topic", "/bluerov2/bluerov2/camera_front/camera_image"
# #         )
# #         self._down_cam_topic = rospy.get_param(
# #             "~down_cam_topic", "/bluerov2/bluerov2/camera_down/camera_image"
# #         )

# #         # Service names (configurable)
# #         self._exec_service_name = rospy.get_param(
# #             "~execute_service", "/coral_action_executor/execute_plan"
# #         )
# #         self._hold_service_name = rospy.get_param(
# #             "~hold_service", "/bluerov2/hold_vehicle"
# #         )

# #         # Internal state (textual data)
# #         self._llm_status_raw = None
# #         self._exec_status_raw = None
# #         self._memory_raw = None

# #         # Internal state (images)
# #         self._front_qimage = None
# #         self._down_qimage = None
# #         self._front_bytes = None
# #         self._down_bytes = None

# #         # ROS pubs/subs/clients
# #         self._prompt_pub = rospy.Publisher(
# #             "/coral_captain/user_prompt", StringMsg, queue_size=10
# #         )

# #         self._llm_status_sub = rospy.Subscriber(
# #             "/coral_captain/llm_status", StringMsg, self._on_llm_status, queue_size=10
# #         )

# #         self._exec_status_sub = rospy.Subscriber(
# #             "/coral_captain/execution_status", StringMsg,
# #             self._on_exec_status, queue_size=10
# #         )

# #         self._memory_sub = rospy.Subscriber(
# #             "/coral_captain/memory_state", StringMsg,
# #             self._on_memory_state, queue_size=10
# #         )

# #         self._odom_sub = rospy.Subscriber(
# #             self._pose_topic, Odometry, self._on_odom, queue_size=1
# #         )

# #         # Executor log from /rosout
# #         self._rosout_sub = rospy.Subscriber(
# #             "/rosout", RosoutLog, self._on_rosout_log, queue_size=100
# #         )

# #         if _HAS_BRIDGE:
# #             self._bridge = CvBridge()
# #             rospy.loginfo("[CoralCaptainGUI] cv_bridge OK, subscribing to cameras:")
# #             rospy.loginfo("  front_cam_topic = %s", self._front_cam_topic)
# #             rospy.loginfo("  down_cam_topic  = %s", self._down_cam_topic)

# #             self._front_cam_sub = rospy.Subscriber(
# #                 self._front_cam_topic, Image, self._on_front_image, queue_size=1
# #             )
# #             self._down_cam_sub = rospy.Subscriber(
# #                 self._down_cam_topic, Image, self._on_down_image, queue_size=1
# #             )
# #         else:
# #             self._bridge = None
# #             self._front_cam_sub = None
# #             self._down_cam_sub = None
# #             rospy.logwarn("[CoralCaptainGUI] cv_bridge not available; camera views disabled.")

# #         # Service clients
# #         self._exec_client = None       # execute plan (Trigger)
# #         self._hold_client = None       # emergency stop (Hold)

# #         # Build UI & styling
# #         self._build_ui()
# #         self._apply_stylesheet()

# #         # Size
# #         self.setWindowTitle("Coral Captain")
# #         self.setWindowIcon(QtGui.QIcon.fromTheme("applications-science"))
# #         self.setMinimumSize(1200, 650)

# #         # Connect signals (ROS threads -> GUI thread)
# #         self.front_image_signal.connect(self._set_front_image)
# #         self.down_image_signal.connect(self._set_down_image)
# #         self.pose_signal.connect(self._set_pose)
# #         self.exec_log_signal.connect(self._append_exec_log)

# #         # Timer for textual UI (status & memory)
# #         self._timer = QtCore.QTimer(self)
# #         self._timer.timeout.connect(self._on_timer_tick)
# #         self._timer.start(100)  # 10 Hz

# #     # ------------------------------------------------------------------
# #     # UI construction (2x3 grid)
# #     # ------------------------------------------------------------------
# #     def _build_ui(self):
# #         # Grid layout: 2 rows x 3 columns
# #         grid = QtWidgets.QGridLayout(self)
# #         grid.setContentsMargins(6, 6, 6, 6)
# #         grid.setSpacing(8)

# #         # ====== Top-left: Mission Console ======
# #         mission_box = QtWidgets.QGroupBox("Mission Console")
# #         mission_layout = QtWidgets.QVBoxLayout(mission_box)
# #         mission_layout.setContentsMargins(6, 6, 6, 6)
# #         mission_layout.setSpacing(4)

# #         history_label = QtWidgets.QLabel("Prompt history (this mission):")
# #         self._prompt_history = QtWidgets.QPlainTextEdit()
# #         self._prompt_history.setReadOnly(True)
# #         self._prompt_history.setPlaceholderText("Sent prompts will appear here...")
# #         self._prompt_history.setMinimumHeight(80)

# #         prompt_label = QtWidgets.QLabel("LLM Prompt:")
# #         self._prompt_edit = QtWidgets.QLineEdit()
# #         self._prompt_edit.setPlaceholderText(
# #             "E.g., \"Survey coral bed A, then circle site B and return home.\""
# #         )
# #         self._prompt_edit.returnPressed.connect(self._on_send_prompt)

# #         btn_row = QtWidgets.QHBoxLayout()
# #         self._btn_send = QtWidgets.QPushButton("Send Prompt")
# #         self._btn_send.clicked.connect(self._on_send_prompt)

# #         self._btn_clear = QtWidgets.QPushButton("Clear")
# #         self._btn_clear.clicked.connect(self._on_clear_prompt)

# #         self._btn_execute = QtWidgets.QPushButton("Approve & Execute Plan")
# #         self._btn_execute.clicked.connect(self._on_execute_plan)

# #         self._btn_emergency_stop = QtWidgets.QPushButton("EMERGENCY STOP")
# #         self._btn_emergency_stop.setObjectName("emergencyStopButton")
# #         self._btn_emergency_stop.clicked.connect(self._on_emergency_stop)

# #         btn_row.addWidget(self._btn_send)
# #         btn_row.addWidget(self._btn_clear)
# #         btn_row.addWidget(self._btn_execute)
# #         btn_row.addWidget(self._btn_emergency_stop)

# #         mission_layout.addWidget(history_label)
# #         mission_layout.addWidget(self._prompt_history)
# #         mission_layout.addWidget(prompt_label)
# #         mission_layout.addWidget(self._prompt_edit)
# #         mission_layout.addLayout(btn_row)

# #         # ====== Top-middle: Mission Memory ======
# #         memory_box = QtWidgets.QGroupBox("Mission Memory")
# #         memory_layout = QtWidgets.QVBoxLayout(memory_box)

# #         summary_label = QtWidgets.QLabel("Summary:")
# #         self._memory_summary = QtWidgets.QPlainTextEdit()
# #         self._memory_summary.setReadOnly(True)
# #         self._memory_summary.setPlaceholderText(
# #             "Visited sites, completed actions, photos, events..."
# #         )

# #         memory_layout.addWidget(summary_label)
# #         memory_layout.addWidget(self._memory_summary)

# #         # ====== Top-right: Front Camera ======
# #         front_cam_box = QtWidgets.QGroupBox("Front camera")
# #         front_cam_layout = QtWidgets.QVBoxLayout(front_cam_box)
# #         self._front_cam_view = ImageViewWidget()
# #         front_cam_layout.addWidget(self._front_cam_view, alignment=QtCore.Qt.AlignCenter)

# #         # ====== Bottom-left: Executor Log ======
# #         log_box = QtWidgets.QGroupBox("Executor Log")
# #         log_layout = QtWidgets.QVBoxLayout(log_box)

# #         self._exec_log = QtWidgets.QPlainTextEdit()
# #         self._exec_log.setReadOnly(True)

# #         log_layout.addWidget(self._exec_log)

# #         # ====== Bottom-middle: Vehicle State & Plots ======
# #         vehicle_box = QtWidgets.QGroupBox("Vehicle State / Depth / X-Y vs Samples")
# #         vehicle_layout = QtWidgets.QVBoxLayout(vehicle_box)

# #         labels_row = QtWidgets.QGridLayout()
# #         self._depth_label = QtWidgets.QLabel("Depth: — m")
# #         self._speed_label = QtWidgets.QLabel("Speed: — m/s")
# #         self._heading_label = QtWidgets.QLabel("Heading: — °")
# #         self._position_label = QtWidgets.QLabel("Pos: (x=—, y=—)")

# #         labels_row.addWidget(self._depth_label,   0, 0)
# #         labels_row.addWidget(self._speed_label,   0, 1)
# #         labels_row.addWidget(self._heading_label, 1, 0)
# #         labels_row.addWidget(self._position_label,1, 1)

# #         vehicle_layout.addLayout(labels_row)

# #         # Depth vs sample plot
# #         self._depth_canvas = DepthPlotCanvas()
# #         vehicle_layout.addWidget(self._depth_canvas)

# #         # X/Y vs sample plot
# #         self._xy_time_canvas = XYTimePlotCanvas()
# #         vehicle_layout.addWidget(self._xy_time_canvas)

# #         # ====== Bottom-right: Downward Camera ======
# #         down_cam_box = QtWidgets.QGroupBox("Downward camera")
# #         down_cam_layout = QtWidgets.QVBoxLayout(down_cam_box)
# #         self._down_cam_view = ImageViewWidget()
# #         down_cam_layout.addWidget(self._down_cam_view, alignment=QtCore.Qt.AlignCenter)

# #         # ---- Place all 6 boxes into a 2x3 grid ----
# #         grid.addWidget(mission_box,   0, 0)
# #         grid.addWidget(memory_box,    0, 1)
# #         grid.addWidget(front_cam_box, 0, 2)

# #         grid.addWidget(log_box,       1, 0)
# #         grid.addWidget(vehicle_box,   1, 1)
# #         grid.addWidget(down_cam_box,  1, 2)

# #         grid.setRowStretch(0, 1)
# #         grid.setRowStretch(1, 1)
# #         grid.setColumnStretch(0, 1)
# #         grid.setColumnStretch(1, 1)
# #         grid.setColumnStretch(2, 1)

# #     # ------------------------------------------------------------------
# #     # Styling
# #     # ------------------------------------------------------------------
# #     def _apply_stylesheet(self):
# #         self.setStyleSheet("""
# #             QWidget {
# #                 background-color: #f3f5f7;
# #                 color: #202020;
# #                 font-size: 12px;
# #             }
# #             QGroupBox {
# #                 border: 1px solid #c0c0c0;
# #                 border-radius: 6px;
# #                 margin-top: 10px;
# #                 font-weight: bold;
# #                 font-size: 13px;
# #                 background-color: #ffffff;
# #             }
# #             QGroupBox::title {
# #                 subcontrol-origin: margin;
# #                 subcontrol-position: top left;
# #                 padding: 2px 8px 0 8px;
# #             }
# #             QPushButton {
# #                 background-color: #ffffff;
# #                 border: 1px solid #b0b0b0;
# #                 padding: 4px 10px;
# #                 border-radius: 4px;
# #             }
# #             QPushButton:hover {
# #                 background-color: #e6f0ff;
# #             }
# #             QPushButton:pressed {
# #                 background-color: #cadbff;
# #             }
# #             QPushButton#emergencyStopButton {
# #                 background-color: #ff4a4a;
# #                 border: 1px solid #b00000;
# #                 color: #ffffff;
# #                 font-weight: bold;
# #             }
# #             QPushButton#emergencyStopButton:hover {
# #                 background-color: #ff7070;
# #             }
# #             QPushButton#emergencyStopButton:pressed {
# #                 background-color: #e00000;
# #             }
# #             QPlainTextEdit, QTextEdit {
# #                 background-color: #ffffff;
# #                 border: 1px solid #c0c0c0;
# #             }
# #             QLineEdit {
# #                 background-color: #ffffff;
# #                 border: 1px solid #c0c0c0;
# #                 padding: 3px 6px;
# #             }
# #             QLabel {
# #                 font-size: 11px;
# #             }
# #         """)

# #         self._btn_send.setIcon(QtGui.QIcon.fromTheme("mail-send"))
# #         self._btn_clear.setIcon(QtGui.QIcon.fromTheme("edit-clear"))
# #         self._btn_execute.setIcon(QtGui.QIcon.fromTheme("media-playback-start"))

# #     # ------------------------------------------------------------------
# #     # Timer tick – update text UI
# #     # ------------------------------------------------------------------
# #     def _on_timer_tick(self):
# #         self._update_exec_status_view()
# #         self._update_memory_view()

# #     # ------------------------------------------------------------------
# #     # Button callbacks
# #     # ------------------------------------------------------------------
# #     def _on_send_prompt(self):
# #         text = self._prompt_edit.text().strip()
# #         if not text:
# #             QtWidgets.QMessageBox.warning(
# #                 self, "Empty prompt", "Please enter a prompt first."
# #             )
# #             return

# #         msg = StringMsg(data=text)
# #         self._prompt_pub.publish(msg)
# #         self._llm_status_raw = "planning: " + text

# #         rospy.loginfo("[CoralCaptainGUI] Prompt sent: %s", text)
# #         self._prompt_history.appendPlainText(f"> {text}")
# #         self._prompt_edit.clear()

# #     def _on_clear_prompt(self):
# #         self._prompt_edit.clear()

# #     def _on_execute_plan(self):
# #         if self._exec_client is None:
# #             try:
# #                 rospy.loginfo("[CoralCaptainGUI] Waiting for execute service: %s",
# #                               self._exec_service_name)
# #                 rospy.wait_for_service(self._exec_service_name, timeout=1.0)
# #                 self._exec_client = rospy.ServiceProxy(self._exec_service_name, Trigger)
# #             except rospy.ROSException:
# #                 QtWidgets.QMessageBox.critical(
# #                     self,
# #                     "Executor not available",
# #                     "Service '{}' not available.".format(self._exec_service_name)
# #                 )
# #                 return

# #         try:
# #             resp = self._exec_client(TriggerRequest())
# #         except Exception as e:
# #             QtWidgets.QMessageBox.critical(
# #                 self,
# #                 "Execution failed",
# #                 "Service call failed: {}".format(e)
# #             )
# #             return

# #         if resp.success:
# #             msg = resp.message or "Plan execution started."
# #             self.exec_log_signal.emit("[GUI] execute_plan: " + msg)
# #         else:
# #             QtWidgets.QMessageBox.warning(
# #                 self,
# #                 "Execution error",
# #                 resp.message or "Plan execution failed."
# #             )

# #     def _on_emergency_stop(self):
# #         """Call uuv_control_msgs/Hold on self._hold_service_name."""
# #         if self._hold_client is None:
# #             try:
# #                 rospy.loginfo("[CoralCaptainGUI] Waiting for hold service (Hold): %s",
# #                               self._hold_service_name)
# #                 rospy.wait_for_service(self._hold_service_name, timeout=3.0)
# #                 self._hold_client = rospy.ServiceProxy(self._hold_service_name, Hold)
# #             except rospy.ROSException:
# #                 QtWidgets.QMessageBox.critical(
# #                     self,
# #                     "Emergency stop unavailable",
# #                     "Service '{}' (uuv_control_msgs/Hold) not available.".format(
# #                         self._hold_service_name
# #                     )
# #                 )
# #                 return

# #         try:
# #             resp = self._hold_client()
# #             ok = bool(getattr(resp, "success", True))
# #             msg = getattr(resp, "message", "")
# #         except Exception as e:
# #             QtWidgets.QMessageBox.critical(
# #                 self,
# #                 "Emergency stop failed",
# #                 "Service call failed: {}".format(e)
# #             )
# #             return

# #         if ok:
# #             self.exec_log_signal.emit(
# #                 "[EMERGENCY] hold_vehicle (Hold) called successfully: {}".format(
# #                     msg or ""
# #                 )
# #             )
# #         else:
# #             QtWidgets.QMessageBox.warning(
# #                 self,
# #                 "Emergency stop error",
# #                 msg or "Vehicle hold/stop command reported failure."
# #             )
# #             self.exec_log_signal.emit(
# #                 "[EMERGENCY] hold_vehicle (Hold) FAILED: {}".format(msg)
# #             )

# #     # ------------------------------------------------------------------
# #     # ROS callbacks – only update state / emit signals
# #     # ------------------------------------------------------------------
# #     def _on_llm_status(self, msg):
# #         self._llm_status_raw = msg.data

# #     def _on_exec_status(self, msg):
# #         self._exec_status_raw = msg.data

# #     def _on_memory_state(self, msg):
# #         self._memory_raw = msg.data

# #     def _on_odom(self, msg):
# #         z = msg.pose.pose.position.z
# #         depth = -z

# #         v = msg.twist.twist.linear
# #         speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)

# #         heading_deg = float('nan')
# #         if _HAS_TF:
# #             q = msg.pose.pose.orientation
# #             quat = [q.x, q.y, q.z, q.w]
# #             try:
# #                 _, _, yaw = euler_from_quaternion(quat)
# #                 heading_deg = (math.degrees(yaw) + 360.0) % 360.0
# #             except Exception:
# #                 heading_deg = float('nan')

# #         x = msg.pose.pose.position.x
# #         y = msg.pose.pose.position.y

# #         self.pose_signal.emit(x, y, depth, speed, heading_deg)

# #     def _on_front_image(self, msg):
# #         if self._bridge is None:
# #             return
# #         try:
# #             try:
# #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
# #             except Exception:
# #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

# #             if cv_img.ndim == 2:
# #                 cv_img = np.stack([cv_img] * 3, axis=-1)

# #             rgb = cv_img[:, :, ::-1]  # BGR -> RGB
# #             h, w, ch = rgb.shape
# #             bytes_per_line = ch * w
# #             self._front_bytes = rgb.tobytes()
# #             qimg = QtGui.QImage(
# #                 self._front_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
# #             )
# #             self.front_image_signal.emit(qimg)

# #         except Exception as e:
# #             rospy.logwarn("[CoralCaptainGUI] Error converting front image: %s", e)

# #     def _on_down_image(self, msg):
# #         if self._bridge is None:
# #             return
# #         try:
# #             try:
# #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
# #             except Exception:
# #                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

# #             if cv_img.ndim == 2:
# #                 cv_img = np.stack([cv_img] * 3, axis=-1)

# #             rgb = cv_img[:, :, ::-1]
# #             h, w, ch = rgb.shape
# #             bytes_per_line = ch * w
# #             self._down_bytes = rgb.tobytes()
# #             qimg = QtGui.QImage(
# #                 self._down_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
# #             )
# #             self.down_image_signal.emit(qimg)

# #         except Exception as e:
# #             rospy.logwarn("[CoralCaptainGUI] Error converting down image: %s", e)

# #     def _on_rosout_log(self, msg: RosoutLog):
# #         text = msg.msg or ""
# #         if not text:
# #             return

# #         # Focus on relevant components
# #         if ("[executor]" not in text and
# #                 "[actions]" not in text and
# #                 "[mission_memory]" not in text and
# #                 "Plan published:" not in text):
# #             return

# #         self.exec_log_signal.emit(text)

# #     # ------------------------------------------------------------------
# #     # Slots in GUI thread
# #     # ------------------------------------------------------------------
# #     @QtCore.Slot(QtGui.QImage)
# #     def _set_front_image(self, qimg):
# #         self._front_qimage = qimg
# #         if self._front_qimage is not None:
# #             self._front_cam_view.set_image(self._front_qimage)
# #         else:
# #             self._front_cam_view.setText("No front camera image")

# #     @QtCore.Slot(QtGui.QImage)
# #     def _set_down_image(self, qimg):
# #         self._down_qimage = qimg
# #         if self._down_qimage is not None:
# #             self._down_cam_view.set_image(self._down_qimage)
# #         else:
# #             self._down_cam_view.setText("No downward camera image")

# #     @QtCore.Slot(float, float, float, float, float)
# #     def _set_pose(self, x, y, depth, speed, heading_deg):
# #         self._depth_label.setText(f"Depth: {depth:.1f} m")
# #         self._speed_label.setText(f"Speed: {speed:.2f} m/s")
# #         if math.isnan(heading_deg):
# #             self._heading_label.setText("Heading: (N/A)")
# #         else:
# #             self._heading_label.setText(f"Heading: {heading_deg:.1f} °")
# #         self._position_label.setText(f"Pos: (x={x:.1f}, y={y:.1f})")

# #         if hasattr(self, "_depth_canvas"):
# #             self._depth_canvas.add_sample(depth)
# #         if hasattr(self, "_xy_time_canvas"):
# #             self._xy_time_canvas.add_sample(x, y)

# #     @QtCore.Slot(str)
# #     def _append_exec_log(self, text):
# #         if not text.strip():
# #             return
# #         self._exec_log.appendPlainText(text)

# #     # ------------------------------------------------------------------
# #     # UI update helpers
# #     # ------------------------------------------------------------------
# #     def _update_exec_status_view(self):
# #         if self._exec_status_raw is None:
# #             return

# #         raw = self._exec_status_raw.strip()
# #         if not raw:
# #             return

# #         state = "unknown"
# #         try:
# #             obj = json.loads(raw)
# #             state = obj.get("state", "unknown")
# #         except Exception:
# #             state = raw

# #         executing = state in ("executing", "executing_step")
# #         self._btn_execute.setEnabled(not executing)

# #     def _update_memory_view(self):
# #         if self._memory_raw is None:
# #             return

# #         raw = self._memory_raw.strip()
# #         if not raw:
# #             return

# #         try:
# #             obj = json.loads(raw)
# #         except Exception:
# #             obj = None

# #         summary = self._build_memory_summary(obj) if obj is not None else "(unable to parse memory JSON)"
# #         self._memory_summary.setPlainText(summary)

# #     # ------------------------------------------------------------------
# #     # Memory summary helper
# #     # ------------------------------------------------------------------
# #     def _build_memory_summary(self, mem):
# #         if not isinstance(mem, dict):
# #             return "(invalid memory structure)"

# #         visited = mem.get("visited_sites", [])
# #         completed = mem.get("completed_actions", [])
# #         photos = mem.get("photos_taken", [])
# #         last_event = mem.get("last_event", "")
# #         replan_events = mem.get("replan_events", [])

# #         lines = []

# #         if visited:
# #             lines.append("Visited sites: " + ", ".join(map(str, visited)))
# #         else:
# #             lines.append("Visited sites: none yet")

# #         if completed:
# #             lines.append(f"Completed actions: {len(completed)}")
# #             tail = completed[-3:]
# #             descs = []
# #             for c in tail:
# #                 if isinstance(c, dict):
# #                     a = c.get("action", "?")
# #                     args = c.get("args", {}) if isinstance(c.get("args", {}), dict) else {}
# #                     site = None
# #                     if isinstance(args, dict):
# #                         site = args.get("site") or args.get("footprint")
# #                     if site:
# #                         descs.append(f"{a}(site={site})")
# #                     else:
# #                         descs.append(a)
# #                 else:
# #                     descs.append(str(c))
# #             lines.append("Recent: " + ", ".join(descs))
# #         else:
# #             lines.append("Completed actions: none yet")

# #         if photos:
# #             last = photos[-1]
# #             if isinstance(last, dict):
# #                 label = last.get("label", "?")
# #             else:
# #                 label = str(last)
# #             lines.append(f"Photos taken: {len(photos)} (last: {label})")
# #         else:
# #             lines.append("Photos taken: none yet")

# #         if last_event:
# #             lines.append(f"Last event: {last_event}")

# #         if replan_events:
# #             lines.append(f"Replans triggered: {len(replan_events)}")

# #         return "\n".join(lines)

# #     # ------------------------------------------------------------------
# #     # Cleanup
# #     # ------------------------------------------------------------------
# #     def shutdown(self):
# #         for sub in [
# #             self._llm_status_sub,
# #             self._exec_status_sub,
# #             self._memory_sub,
# #             self._odom_sub,
# #             self._rosout_sub,
# #             getattr(self, "_front_cam_sub", None),
# #             getattr(self, "_down_cam_sub", None),
# #         ]:
# #             try:
# #                 if sub is not None:
# #                     sub.unregister()
# #             except Exception:
# #                 pass

# #         try:
# #             self._prompt_pub.unregister()
# #         except Exception:
# #             pass

# #         self._exec_client = None
# #         self._hold_client = None


# # # ---------------------------------------------------------------------------
# # # Main entry point
# # # ---------------------------------------------------------------------------
# # def main():
# #     rospy.init_node("coral_captain_gui", anonymous=True)

# #     app = QtWidgets.QApplication(sys.argv)
# #     widget = CoralCaptainWidget()
# #     widget.show()

# #     def on_quit():
# #         rospy.loginfo("[CoralCaptainGUI] Shutting down GUI")
# #         widget.shutdown()
# #         rospy.signal_shutdown("GUI closed")

# #     app.aboutToQuit.connect(on_quit)

# #     sys.exit(app.exec_())


# # if __name__ == "__main__":
# #     main()

# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# """
# Coral Captain Standalone GUI

# Standalone Qt + rospy dashboard for your coral LLM + executor stack.

# Features:
# - Prompt input -> /coral_captain/user_prompt
# - Prompt history (within session)
# - Mission memory summary              <- /coral_captain/memory_state
# - Approve & Execute button            -> /coral_action_executor/execute_plan (Trigger)
# - Emergency stop                      -> /bluerov2/hold_vehicle (uuv_control_msgs/Hold)
# - Vehicle State Dashboard             <- /bluerov2/pose_gt (depth, speed, heading, x, y)
# - Depth vs sample plot (matplotlib)   <- /bluerov2/pose_gt
# - X/Y vs sample plot (matplotlib)     <- /bluerov2/pose_gt
# - Plan-view XY map with coral sites   <- /bluerov2/pose_gt
# - Live cameras                        <- /bluerov2/bluerov2/camera_front/camera_image
#                                          /bluerov2/bluerov2/camera_down/camera_image
# - Executor log (filtered /rosout)     <- /rosout
# """

# import json
# import math
# import sys

# import rospy
# import numpy as np

# from std_msgs.msg import String as StringMsg
# from std_srvs.srv import Trigger, TriggerRequest
# from uuv_control_msgs.srv import Hold
# from nav_msgs.msg import Odometry
# from sensor_msgs.msg import Image
# from rosgraph_msgs.msg import Log as RosoutLog

# from python_qt_binding import QtWidgets, QtGui, QtCore

# try:
#     from tf.transformations import euler_from_quaternion
#     _HAS_TF = True
# except ImportError:
#     _HAS_TF = False

# try:
#     from cv_bridge import CvBridge
#     _HAS_BRIDGE = True
# except ImportError:
#     _HAS_BRIDGE = False

# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.figure import Figure
# from matplotlib.patches import Rectangle, Circle, Ellipse


# # ---------------------------------------------------------------------------
# # Image viewer widget (auto-fit, no wheel zoom, fixed size)
# # ---------------------------------------------------------------------------
# class ImageViewWidget(QtWidgets.QLabel):
#     def __init__(self, parent=None):
#         super(ImageViewWidget, self).__init__(parent)
#         self._qimage = None
#         self._pixmap = None

#         self.setAlignment(QtCore.Qt.AlignCenter)
#         self.setFrameShape(QtWidgets.QFrame.Box)

#         # FIXED SIZE for camera views
#         self.setFixedSize(360, 220)
#         size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed,
#                                             QtWidgets.QSizePolicy.Fixed)
#         self.setSizePolicy(size_policy)

#     def set_image(self, qimage: QtGui.QImage):
#         if qimage is None or qimage.isNull():
#             return
#         self._qimage = qimage
#         self._pixmap = QtGui.QPixmap.fromImage(qimage)
#         self._update_view()

#     def _update_view(self):
#         if self._pixmap is None or self._pixmap.isNull():
#             self.setPixmap(QtGui.QPixmap())
#             self.setText("No image")
#             return

#         self.setText("")
#         scaled = self._pixmap.scaled(
#             self.size(),
#             QtCore.Qt.KeepAspectRatio,
#             QtCore.Qt.SmoothTransformation
#         )
#         self.setPixmap(scaled)

#     def resizeEvent(self, event):
#         super(ImageViewWidget, self).resizeEvent(event)
#         self._update_view()

#     def wheelEvent(self, event: QtGui.QWheelEvent):
#         event.ignore()  # disable zoom


# # ---------------------------------------------------------------------------
# # Depth vs sample plot using matplotlib
# # ---------------------------------------------------------------------------
# class DepthPlotCanvas(FigureCanvas):
#     def __init__(self, parent=None, max_points=300):
#         self._fig = Figure(figsize=(3, 2))
#         self._ax = self._fig.add_subplot(111)
#         self._ax.set_title("Depth vs Samples")
#         self._ax.set_xlabel("Samples")
#         self._ax.set_ylabel("Depth (m)")
#         self._ax.invert_yaxis()
#         self._ax.grid(True)

#         super(DepthPlotCanvas, self).__init__(self._fig)
#         self.setParent(parent)

#         self._max_points = max_points
#         self._xs = []
#         self._ys = []
#         (self._line,) = self._ax.plot([], [])

#     def add_sample(self, depth: float):
#         idx = self._xs[-1] + 1 if self._xs else 0
#         self._xs.append(idx)
#         self._ys.append(depth)

#         if len(self._xs) > self._max_points:
#             self._xs = self._xs[-self._max_points:]
#             self._ys = self._ys[-self._max_points:]

#         self._line.set_data(self._xs, self._ys)
#         self._ax.relim()
#         self._ax.autoscale_view()
#         self.draw_idle()


# # ---------------------------------------------------------------------------
# # X/Y vs sample plot using matplotlib
# # ---------------------------------------------------------------------------
# class XYTimePlotCanvas(FigureCanvas):
#     def __init__(self, parent=None, max_points=300):
#         self._fig = Figure(figsize=(3, 2))
#         self._ax = self._fig.add_subplot(111)
#         self._ax.set_title("X/Y vs Samples")
#         self._ax.set_xlabel("Samples")
#         self._ax.set_ylabel("Position (m)")
#         self._ax.grid(True)

#         super(XYTimePlotCanvas, self).__init__(self._fig)
#         self.setParent(parent)

#         self._max_points = max_points
#         self._samples = []
#         self._xs = []
#         self._ys = []

#         (self._line_x,) = self._ax.plot([], [], label="x")
#         (self._line_y,) = self._ax.plot([], [], label="y")
#         self._ax.legend(loc="upper right", fontsize=8)

#     def add_sample(self, x: float, y: float):
#         idx = self._samples[-1] + 1 if self._samples else 0
#         self._samples.append(idx)
#         self._xs.append(float(x))
#         self._ys.append(float(y))

#         if len(self._samples) > self._max_points:
#             self._samples = self._samples[-self._max_points:]
#             self._xs = self._xs[-self._max_points:]
#             self._ys = self._ys[-self._max_points:]

#         self._line_x.set_data(self._samples, self._xs)
#         self._line_y.set_data(self._samples, self._ys)

#         self._ax.relim()
#         self._ax.autoscale_view()
#         self.draw_idle()


# # ---------------------------------------------------------------------------
# # Plan-view XY map using matplotlib (with coral sites + grid)
# # ---------------------------------------------------------------------------
# class XYPlanCanvas(FigureCanvas):
#     """
#     Plan-view XY track with environment:

#     - Fixed grid from -20..120 in X and Y (20 m spacing)
#     - Coral sites A, B, C, D drawn as in the reference figure
#     - Robot trajectory line + current-position marker
#     """

#     def __init__(self, parent=None, max_points=2000):
#         self._fig = Figure(figsize=(3, 2))
#         self._ax = self._fig.add_subplot(111)
#         self._ax.set_title("XY Plan View")
#         self._ax.set_xlabel("X (m)")
#         self._ax.set_ylabel("Y (m)")
#         self._ax.grid(False)  # we'll draw our own grid so it matches your figure
#         self._ax.set_aspect("equal", adjustable="box")

#         super(XYPlanCanvas, self).__init__(self._fig)
#         self.setParent(parent)

#         self._max_points = max_points
#         self._xs = []
#         self._ys = []

#         # Draw static environment
#         self._draw_environment()

#         # Dynamic elements: trajectory line + current position
#         (self._line,) = self._ax.plot([], [], linewidth=1.5)
#         self._marker = self._ax.plot([], [], "o", markersize=5)[0]

#     def _draw_environment(self):
#         # World bounds for this map
#         x_min, x_max = -20.0, 120.0
#         y_min, y_max = -20.0, 120.0
#         self._ax.set_xlim(x_min, x_max)
#         self._ax.set_ylim(y_min, y_max)

#         # 20 m gridlines
#         for x in range(-20, 121, 20):
#             self._ax.axvline(x, linewidth=0.4, color="#d0e0f0", zorder=0)
#         for y in range(-20, 121, 20):
#             self._ax.axhline(y, linewidth=0.4, color="#d0e0f0", zorder=0)

#         # Site centers
#         sites = {
#             "A": (0.0, 0.0),
#             "B": (80.0, 0.0),
#             "C": (0.0, 80.0),
#             "D": (80.0, 80.0),
#         }

#         # A: rectangle 34 x 32
#         cx, cy = sites["A"]
#         rect_A = Rectangle((cx - 17.0, cy - 16.0), 34.0, 32.0,
#                            fill=False, edgecolor="black", linewidth=1.0)
#         self._ax.add_patch(rect_A)
#         self._ax.text(cx, cy, "A", ha="center", va="center")

#         # B: circle Ø15
#         cx, cy = sites["B"]
#         circ_B = Circle((cx, cy), 7.5, fill=False, edgecolor="black", linewidth=1.0)
#         self._ax.add_patch(circ_B)
#         self._ax.text(cx, cy, "B", ha="center", va="center")

#         # C: ellipse 21 x 6, rotated 90°
#         cx, cy = sites["C"]
#         ell_C = Ellipse((cx, cy), width=21.0, height=6.0, angle=90,
#                         fill=False, edgecolor="black", linewidth=1.0)
#         self._ax.add_patch(ell_C)
#         self._ax.text(cx, cy, "C", ha="center", va="center")

#         # D: small square 5 x 5
#         cx, cy = sites["D"]
#         rect_D = Rectangle((cx - 2.5, cy - 2.5), 5.0, 5.0,
#                            fill=False, edgecolor="black", linewidth=1.0)
#         self._ax.add_patch(rect_D)
#         self._ax.text(cx, cy, "D", ha="center", va="center")

#         # Keep border visible
#         self._ax.set_xlim(x_min, x_max)
#         self._ax.set_ylim(y_min, y_max)

#     def add_sample(self, x: float, y: float):
#         self._xs.append(float(x))
#         self._ys.append(float(y))

#         if len(self._xs) > self._max_points:
#             self._xs = self._xs[-self._max_points:]
#             self._ys = self._ys[-self._max_points:]

#         # Update trajectory
#         self._line.set_data(self._xs, self._ys)

#         # Current position marker
#         self._marker.set_data([self._xs[-1]], [self._ys[-1]])

#         self._ax.figure.canvas.draw_idle()


# # ---------------------------------------------------------------------------
# # Main GUI widget
# # ---------------------------------------------------------------------------
# class CoralCaptainWidget(QtWidgets.QWidget):
#     front_image_signal = QtCore.Signal(QtGui.QImage)
#     down_image_signal = QtCore.Signal(QtGui.QImage)
#     pose_signal = QtCore.Signal(float, float, float, float, float)
#     exec_log_signal = QtCore.Signal(str)

#     def __init__(self, parent=None):
#         super(CoralCaptainWidget, self).__init__(parent)

#         # Parameters
#         self._pose_topic = rospy.get_param("~pose_topic", "/bluerov2/pose_gt")
#         self._front_cam_topic = rospy.get_param(
#             "~front_cam_topic", "/bluerov2/bluerov2/camera_front/camera_image"
#         )
#         self._down_cam_topic = rospy.get_param(
#             "~down_cam_topic", "/bluerov2/bluerov2/camera_down/camera_image"
#         )

#         self._exec_service_name = rospy.get_param(
#             "~execute_service", "/coral_action_executor/execute_plan"
#         )
#         self._hold_service_name = rospy.get_param(
#             "~hold_service", "/bluerov2/hold_vehicle"
#         )

#         # Internal state (textual data)
#         self._llm_status_raw = None
#         self._exec_status_raw = None
#         self._memory_raw = None

#         # Internal state (images)
#         self._front_qimage = None
#         self._down_qimage = None
#         self._front_bytes = None
#         self._down_bytes = None

#         # ROS pubs/subs/clients
#         self._prompt_pub = rospy.Publisher(
#             "/coral_captain/user_prompt", StringMsg, queue_size=10
#         )

#         self._llm_status_sub = rospy.Subscriber(
#             "/coral_captain/llm_status", StringMsg, self._on_llm_status, queue_size=10
#         )

#         self._exec_status_sub = rospy.Subscriber(
#             "/coral_captain/execution_status", StringMsg,
#             self._on_exec_status, queue_size=10
#         )

#         self._memory_sub = rospy.Subscriber(
#             "/coral_captain/memory_state", StringMsg,
#             self._on_memory_state, queue_size=10
#         )

#         self._odom_sub = rospy.Subscriber(
#             self._pose_topic, Odometry, self._on_odom, queue_size=1
#         )

#         self._rosout_sub = rospy.Subscriber(
#             "/rosout", RosoutLog, self._on_rosout_log, queue_size=100
#         )

#         if _HAS_BRIDGE:
#             self._bridge = CvBridge()
#             rospy.loginfo("[CoralCaptainGUI] cv_bridge OK, subscribing to cameras:")
#             rospy.loginfo("  front_cam_topic = %s", self._front_cam_topic)
#             rospy.loginfo("  down_cam_topic  = %s", self._down_cam_topic)

#             self._front_cam_sub = rospy.Subscriber(
#                 self._front_cam_topic, Image, self._on_front_image, queue_size=1
#             )
#             self._down_cam_sub = rospy.Subscriber(
#                 self._down_cam_topic, Image, self._on_down_image, queue_size=1
#             )
#         else:
#             self._bridge = None
#             self._front_cam_sub = None
#             self._down_cam_sub = None
#             rospy.logwarn("[CoralCaptainGUI] cv_bridge not available; camera views disabled.")

#         # Service clients
#         self._exec_client = None
#         self._hold_client = None

#         # Build UI & styling
#         self._build_ui()
#         self._apply_stylesheet()

#         self.setWindowTitle("Coral Captain")
#         self.setWindowIcon(QtGui.QIcon.fromTheme("applications-science"))
#         self.setMinimumSize(1200, 650)

#         # Connect signals
#         self.front_image_signal.connect(self._set_front_image)
#         self.down_image_signal.connect(self._set_down_image)
#         self.pose_signal.connect(self._set_pose)
#         self.exec_log_signal.connect(self._append_exec_log)

#         # Timer for textual UI
#         self._timer = QtCore.QTimer(self)
#         self._timer.timeout.connect(self._on_timer_tick)
#         self._timer.start(100)

#     # ------------------------------------------------------------------
#     # UI construction
#     # ------------------------------------------------------------------
#     def _build_ui(self):
#         grid = QtWidgets.QGridLayout(self)
#         grid.setContentsMargins(6, 6, 6, 6)
#         grid.setSpacing(8)

#         # Mission console
#         mission_box = QtWidgets.QGroupBox("Mission Console")
#         mission_layout = QtWidgets.QVBoxLayout(mission_box)
#         mission_layout.setContentsMargins(6, 6, 6, 6)
#         mission_layout.setSpacing(4)

#         history_label = QtWidgets.QLabel("Prompt history (this mission):")
#         self._prompt_history = QtWidgets.QPlainTextEdit()
#         self._prompt_history.setReadOnly(True)
#         self._prompt_history.setPlaceholderText("Sent prompts will appear here...")
#         self._prompt_history.setMinimumHeight(80)

#         prompt_label = QtWidgets.QLabel("LLM Prompt:")
#         self._prompt_edit = QtWidgets.QLineEdit()
#         self._prompt_edit.setPlaceholderText(
#             "E.g., \"Survey coral bed A, then circle site B and return home.\""
#         )
#         self._prompt_edit.returnPressed.connect(self._on_send_prompt)

#         btn_row = QtWidgets.QHBoxLayout()
#         self._btn_send = QtWidgets.QPushButton("Send Prompt")
#         self._btn_send.clicked.connect(self._on_send_prompt)

#         self._btn_clear = QtWidgets.QPushButton("Clear")
#         self._btn_clear.clicked.connect(self._on_clear_prompt)

#         self._btn_execute = QtWidgets.QPushButton("Approve & Execute Plan")
#         self._btn_execute.clicked.connect(self._on_execute_plan)

#         self._btn_emergency_stop = QtWidgets.QPushButton("EMERGENCY STOP")
#         self._btn_emergency_stop.setObjectName("emergencyStopButton")
#         self._btn_emergency_stop.clicked.connect(self._on_emergency_stop)

#         btn_row.addWidget(self._btn_send)
#         btn_row.addWidget(self._btn_clear)
#         btn_row.addWidget(self._btn_execute)
#         btn_row.addWidget(self._btn_emergency_stop)

#         mission_layout.addWidget(history_label)
#         mission_layout.addWidget(self._prompt_history)
#         mission_layout.addWidget(prompt_label)
#         mission_layout.addWidget(self._prompt_edit)
#         mission_layout.addLayout(btn_row)

#         # Mission memory
#         memory_box = QtWidgets.QGroupBox("Mission Memory")
#         memory_layout = QtWidgets.QVBoxLayout(memory_box)

#         summary_label = QtWidgets.QLabel("Summary:")
#         self._memory_summary = QtWidgets.QPlainTextEdit()
#         self._memory_summary.setReadOnly(True)
#         self._memory_summary.setPlaceholderText(
#             "Visited sites, completed actions, photos, events..."
#         )

#         memory_layout.addWidget(summary_label)
#         memory_layout.addWidget(self._memory_summary)

#         # Front camera
#         front_cam_box = QtWidgets.QGroupBox("Front camera")
#         front_cam_layout = QtWidgets.QVBoxLayout(front_cam_box)
#         self._front_cam_view = ImageViewWidget()
#         front_cam_layout.addWidget(self._front_cam_view, alignment=QtCore.Qt.AlignCenter)

#         # Executor log
#         log_box = QtWidgets.QGroupBox("Executor Log")
#         log_layout = QtWidgets.QVBoxLayout(log_box)
#         self._exec_log = QtWidgets.QPlainTextEdit()
#         self._exec_log.setReadOnly(True)
#         log_layout.addWidget(self._exec_log)

#         # Vehicle state & plots
#         vehicle_box = QtWidgets.QGroupBox("Vehicle State / Depth / Trajectory")
#         vehicle_layout = QtWidgets.QVBoxLayout(vehicle_box)

#         labels_row = QtWidgets.QGridLayout()
#         self._depth_label = QtWidgets.QLabel("Depth: — m")
#         self._speed_label = QtWidgets.QLabel("Speed: — m/s")
#         self._heading_label = QtWidgets.QLabel("Heading: — °")
#         self._position_label = QtWidgets.QLabel("Pos: (x=—, y=—)")

#         labels_row.addWidget(self._depth_label,   0, 0)
#         labels_row.addWidget(self._speed_label,   0, 1)
#         labels_row.addWidget(self._heading_label, 1, 0)
#         labels_row.addWidget(self._position_label,1, 1)
#         vehicle_layout.addLayout(labels_row)

#         # Depth plot
#         self._depth_canvas = DepthPlotCanvas()
#         self._depth_canvas.setMinimumHeight(160)
#         vehicle_layout.addWidget(self._depth_canvas)

#         # Plan-view + X/Y vs samples side by side
#         plots_row = QtWidgets.QHBoxLayout()
#         self._xy_plan_canvas = XYPlanCanvas()
#         self._xy_plan_canvas.setMinimumSize(260, 180)
#         self._xy_time_canvas = XYTimePlotCanvas()
#         self._xy_time_canvas.setMinimumSize(260, 180)
#         plots_row.addWidget(self._xy_plan_canvas, stretch=1)
#         plots_row.addWidget(self._xy_time_canvas, stretch=1)
#         vehicle_layout.addLayout(plots_row)

#         # Downward camera
#         down_cam_box = QtWidgets.QGroupBox("Downward camera")
#         down_cam_layout = QtWidgets.QVBoxLayout(down_cam_box)
#         self._down_cam_view = ImageViewWidget()
#         down_cam_layout.addWidget(self._down_cam_view, alignment=QtCore.Qt.AlignCenter)

#         # Add to main grid
#         grid.addWidget(mission_box,   0, 0)
#         grid.addWidget(memory_box,    0, 1)
#         grid.addWidget(front_cam_box, 0, 2)
#         grid.addWidget(log_box,       1, 0)
#         grid.addWidget(vehicle_box,   1, 1)
#         grid.addWidget(down_cam_box,  1, 2)

#         grid.setRowStretch(0, 1)
#         grid.setRowStretch(1, 1)
#         grid.setColumnStretch(0, 1)
#         grid.setColumnStretch(1, 1)
#         grid.setColumnStretch(2, 1)

#     # ------------------------------------------------------------------
#     # Styling
#     # ------------------------------------------------------------------
#     def _apply_stylesheet(self):
#         self.setStyleSheet("""
#             QWidget {
#                 background-color: #f3f5f7;
#                 color: #202020;
#                 font-size: 12px;
#             }
#             QGroupBox {
#                 border: 1px solid #c0c0c0;
#                 border-radius: 6px;
#                 margin-top: 10px;
#                 font-weight: bold;
#                 font-size: 13px;
#                 background-color: #ffffff;
#             }
#             QGroupBox::title {
#                 subcontrol-origin: margin;
#                 subcontrol-position: top left;
#                 padding: 2px 8px 0 8px;
#             }
#             QPushButton {
#                 background-color: #ffffff;
#                 border: 1px solid #b0b0b0;
#                 padding: 4px 10px;
#                 border-radius: 4px;
#             }
#             QPushButton:hover {
#                 background-color: #e6f0ff;
#             }
#             QPushButton:pressed {
#                 background-color: #cadbff;
#             }
#             QPushButton#emergencyStopButton {
#                 background-color: #ff4a4a;
#                 border: 1px solid #b00000;
#                 color: #ffffff;
#                 font-weight: bold;
#             }
#             QPushButton#emergencyStopButton:hover {
#                 background-color: #ff7070;
#             }
#             QPushButton#emergencyStopButton:pressed {
#                 background-color: #e00000;
#             }
#             QPlainTextEdit, QTextEdit {
#                 background-color: #ffffff;
#                 border: 1px solid #c0c0c0;
#             }
#             QLineEdit {
#                 background-color: #ffffff;
#                 border: 1px solid #c0c0c0;
#                 padding: 3px 6px;
#             }
#             QLabel {
#                 font-size: 11px;
#             }
#         """)

#         self._btn_send.setIcon(QtGui.QIcon.fromTheme("mail-send"))
#         self._btn_clear.setIcon(QtGui.QIcon.fromTheme("edit-clear"))
#         self._btn_execute.setIcon(QtGui.QIcon.fromTheme("media-playback-start"))

#     # ------------------------------------------------------------------
#     # Timer tick – update text UI
#     # ------------------------------------------------------------------
#     def _on_timer_tick(self):
#         self._update_exec_status_view()
#         self._update_memory_view()

#     # ------------------------------------------------------------------
#     # Button callbacks
#     # ------------------------------------------------------------------
#     def _on_send_prompt(self):
#         text = self._prompt_edit.text().strip()
#         if not text:
#             QtWidgets.QMessageBox.warning(
#                 self, "Empty prompt", "Please enter a prompt first."
#             )
#             return

#         msg = StringMsg(data=text)
#         self._prompt_pub.publish(msg)
#         self._llm_status_raw = "planning: " + text

#         rospy.loginfo("[CoralCaptainGUI] Prompt sent: %s", text)
#         self._prompt_history.appendPlainText(f"> {text}")
#         self._prompt_edit.clear()

#     def _on_clear_prompt(self):
#         self._prompt_edit.clear()

#     def _on_execute_plan(self):
#         if self._exec_client is None:
#             try:
#                 rospy.loginfo("[CoralCaptainGUI] Waiting for execute service: %s",
#                               self._exec_service_name)
#                 rospy.wait_for_service(self._exec_service_name, timeout=1.0)
#                 self._exec_client = rospy.ServiceProxy(self._exec_service_name, Trigger)
#             except rospy.ROSException:
#                 QtWidgets.QMessageBox.critical(
#                     self,
#                     "Executor not available",
#                     "Service '{}' not available.".format(self._exec_service_name)
#                 )
#                 return

#         try:
#             resp = self._exec_client(TriggerRequest())
#         except Exception as e:
#             QtWidgets.QMessageBox.critical(
#                 self,
#                 "Execution failed",
#                 "Service call failed: {}".format(e)
#             )
#             return

#         if resp.success:
#             msg = resp.message or "Plan execution started."
#             self.exec_log_signal.emit("[GUI] execute_plan: " + msg)
#         else:
#             QtWidgets.QMessageBox.warning(
#                 self,
#                 "Execution error",
#                 resp.message or "Plan execution failed."
#             )

#     def _on_emergency_stop(self):
#         if self._hold_client is None:
#             try:
#                 rospy.loginfo("[CoralCaptainGUI] Waiting for hold service (Hold): %s",
#                               self._hold_service_name)
#                 rospy.wait_for_service(self._hold_service_name, timeout=3.0)
#                 self._hold_client = rospy.ServiceProxy(self._hold_service_name, Hold)
#             except rospy.ROSException:
#                 QtWidgets.QMessageBox.critical(
#                     self,
#                     "Emergency stop unavailable",
#                     "Service '{}' (uuv_control_msgs/Hold) not available.".format(
#                         self._hold_service_name
#                     )
#                 )
#                 return

#         try:
#             resp = self._hold_client()
#             ok = bool(getattr(resp, "success", True))
#             msg = getattr(resp, "message", "")
#         except Exception as e:
#             QtWidgets.QMessageBox.critical(
#                 self,
#                 "Emergency stop failed",
#                 "Service call failed: {}".format(e)
#             )
#             return

#         if ok:
#             self.exec_log_signal.emit(
#                 "[EMERGENCY] hold_vehicle (Hold) called successfully: {}".format(
#                     msg or ""
#                 )
#             )
#         else:
#             QtWidgets.QMessageBox.warning(
#                 self,
#                 "Emergency stop error",
#                 msg or "Vehicle hold/stop command reported failure."
#             )
#             self.exec_log_signal.emit(
#                 "[EMERGENCY] hold_vehicle (Hold) FAILED: {}".format(msg)
#             )

#     # ------------------------------------------------------------------
#     # ROS callbacks
#     # ------------------------------------------------------------------
#     def _on_llm_status(self, msg):
#         self._llm_status_raw = msg.data

#     def _on_exec_status(self, msg):
#         self._exec_status_raw = msg.data

#     def _on_memory_state(self, msg):
#         self._memory_raw = msg.data

#     def _on_odom(self, msg):
#         z = msg.pose.pose.position.z
#         depth = -z

#         v = msg.twist.twist.linear
#         speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)

#         heading_deg = float('nan')
#         if _HAS_TF:
#             q = msg.pose.pose.orientation
#             quat = [q.x, q.y, q.z, q.w]
#             try:
#                 _, _, yaw = euler_from_quaternion(quat)
#                 heading_deg = (math.degrees(yaw) + 360.0) % 360.0
#             except Exception:
#                 heading_deg = float('nan')

#         x = msg.pose.pose.position.x
#         y = msg.pose.pose.position.y

#         self.pose_signal.emit(x, y, depth, speed, heading_deg)

#     def _on_front_image(self, msg):
#         if self._bridge is None:
#             return
#         try:
#             try:
#                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
#             except Exception:
#                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

#             if cv_img.ndim == 2:
#                 cv_img = np.stack([cv_img] * 3, axis=-1)

#             rgb = cv_img[:, :, ::-1]
#             h, w, ch = rgb.shape
#             bytes_per_line = ch * w
#             self._front_bytes = rgb.tobytes()
#             qimg = QtGui.QImage(
#                 self._front_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
#             )
#             self.front_image_signal.emit(qimg)

#         except Exception as e:
#             rospy.logwarn("[CoralCaptainGUI] Error converting front image: %s", e)

#     def _on_down_image(self, msg):
#         if self._bridge is None:
#             return
#         try:
#             try:
#                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
#             except Exception:
#                 cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

#             if cv_img.ndim == 2:
#                 cv_img = np.stack([cv_img] * 3, axis=-1)

#             rgb = cv_img[:, :, ::-1]
#             h, w, ch = rgb.shape
#             bytes_per_line = ch * w
#             self._down_bytes = rgb.tobytes()
#             qimg = QtGui.QImage(
#                 self._down_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
#             )
#             self.down_image_signal.emit(qimg)

#         except Exception as e:
#             rospy.logwarn("[CoralCaptainGUI] Error converting down image: %s", e)

#     def _on_rosout_log(self, msg: RosoutLog):
#         text = msg.msg or ""
#         if not text:
#             return

#         if ("[executor]" not in text and
#                 "[actions]" not in text and
#                 "[mission_memory]" not in text and
#                 "Plan published:" not in text):
#             return

#         self.exec_log_signal.emit(text)

#     # ------------------------------------------------------------------
#     # Slots in GUI thread
#     # ------------------------------------------------------------------
#     @QtCore.Slot(QtGui.QImage)
#     def _set_front_image(self, qimg):
#         self._front_qimage = qimg
#         if self._front_qimage is not None:
#             self._front_cam_view.set_image(self._front_qimage)
#         else:
#             self._front_cam_view.setText("No front camera image")

#     @QtCore.Slot(QtGui.QImage)
#     def _set_down_image(self, qimg):
#         self._down_qimage = qimg
#         if self._down_qimage is not None:
#             self._down_cam_view.set_image(self._down_qimage)
#         else:
#             self._down_cam_view.setText("No downward camera image")

#     @QtCore.Slot(float, float, float, float, float)
#     def _set_pose(self, x, y, depth, speed, heading_deg):
#         self._depth_label.setText(f"Depth: {depth:.1f} m")
#         self._speed_label.setText(f"Speed: {speed:.2f} m/s")
#         if math.isnan(heading_deg):
#             self._heading_label.setText("Heading: (N/A)")
#         else:
#             self._heading_label.setText(f"Heading: {heading_deg:.1f} °")
#         self._position_label.setText(f"Pos: (x={x:.1f}, y={y:.1f})")

#         self._depth_canvas.add_sample(depth)
#         self._xy_time_canvas.add_sample(x, y)
#         self._xy_plan_canvas.add_sample(x, y)

#     @QtCore.Slot(str)
#     def _append_exec_log(self, text):
#         if not text.strip():
#             return
#         self._exec_log.appendPlainText(text)

#     # ------------------------------------------------------------------
#     # UI update helpers
#     # ------------------------------------------------------------------
#     def _update_exec_status_view(self):
#         if self._exec_status_raw is None:
#             return

#         raw = self._exec_status_raw.strip()
#         if not raw:
#             return

#         state = "unknown"
#         try:
#             obj = json.loads(raw)
#             state = obj.get("state", "unknown")
#         except Exception:
#             state = raw

#         executing = state in ("executing", "executing_step")
#         self._btn_execute.setEnabled(not executing)

#     def _update_memory_view(self):
#         if self._memory_raw is None:
#             return

#         raw = self._memory_raw.strip()
#         if not raw:
#             return

#         try:
#             obj = json.loads(raw)
#         except Exception:
#             obj = None

#         summary = self._build_memory_summary(obj) if obj is not None else "(unable to parse memory JSON)"
#         self._memory_summary.setPlainText(summary)

#     # ------------------------------------------------------------------
#     # Memory summary helper
#     # ------------------------------------------------------------------
#     def _build_memory_summary(self, mem):
#         if not isinstance(mem, dict):
#             return "(invalid memory structure)"

#         visited = mem.get("visited_sites", [])
#         completed = mem.get("completed_actions", [])
#         photos = mem.get("photos_taken", [])
#         last_event = mem.get("last_event", "")
#         replan_events = mem.get("replan_events", [])

#         lines = []

#         if visited:
#             lines.append("Visited sites: " + ", ".join(map(str, visited)))
#         else:
#             lines.append("Visited sites: none yet")

#         if completed:
#             lines.append(f"Completed actions: {len(completed)}")
#             tail = completed[-3:]
#             descs = []
#             for c in tail:
#                 if isinstance(c, dict):
#                     a = c.get("action", "?")
#                     args = c.get("args", {}) if isinstance(c.get("args", {}), dict) else {}
#                     site = None
#                     if isinstance(args, dict):
#                         site = args.get("site") or args.get("footprint")
#                     if site:
#                         descs.append(f"{a}(site={site})")
#                     else:
#                         descs.append(a)
#                 else:
#                     descs.append(str(c))
#             lines.append("Recent: " + ", ".join(descs))
#         else:
#             lines.append("Completed actions: none yet")

#         if photos:
#             last = photos[-1]
#             if isinstance(last, dict):
#                 label = last.get("label", "?")
#             else:
#                 label = str(last)
#             lines.append(f"Photos taken: {len(photos)} (last: {label})")
#         else:
#             lines.append("Photos taken: none yet")

#         if last_event:
#             lines.append(f"Last event: {last_event}")

#         if replan_events:
#             lines.append(f"Replans triggered: {len(replan_events)}")

#         return "\n".join(lines)

#     # ------------------------------------------------------------------
#     # Cleanup
#     # ------------------------------------------------------------------
#     def shutdown(self):
#         for sub in [
#             self._llm_status_sub,
#             self._exec_status_sub,
#             self._memory_sub,
#             self._odom_sub,
#             self._rosout_sub,
#             getattr(self, "_front_cam_sub", None),
#             getattr(self, "_down_cam_sub", None),
#         ]:
#             try:
#                 if sub is not None:
#                     sub.unregister()
#             except Exception:
#                 pass

#         try:
#             self._prompt_pub.unregister()
#         except Exception:
#             pass

#         self._exec_client = None
#         self._hold_client = None


# # ---------------------------------------------------------------------------
# # Main entry point
# # ---------------------------------------------------------------------------
# def main():
#     rospy.init_node("coral_captain_gui", anonymous=True)

#     app = QtWidgets.QApplication(sys.argv)
#     widget = CoralCaptainWidget()
#     widget.show()

#     def on_quit():
#         rospy.loginfo("[CoralCaptainGUI] Shutting down GUI")
#         widget.shutdown()
#         rospy.signal_shutdown("GUI closed")

#     app.aboutToQuit.connect(on_quit)

#     sys.exit(app.exec_())


# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Coral Captain Standalone GUI

Standalone Qt + rospy dashboard for your coral LLM + executor stack.

Features:
- Prompt input -> /coral_captain/user_prompt
- Prompt history (within session)
- Mission memory summary              <- /coral_captain/memory_state
- Approve & Execute button            -> /coral_action_executor/execute_plan (Trigger)
- Emergency stop                      -> /bluerov2/hold_vehicle (uuv_control_msgs/Hold)
- Vehicle State Dashboard             <- /bluerov2/pose_gt (depth, speed, heading, x, y)
- Depth vs time plot (matplotlib)     <- /bluerov2/pose_gt
- Plan-view XY map with coral sites   <- /bluerov2/pose_gt
- Live cameras                        <- /bluerov2/bluerov2/camera_front/camera_image
                                         /bluerov2/bluerov2/camera_down/camera_image
- Executor log (filtered /rosout)     <- /rosout
"""

import json
import math
import sys

import rospy
import numpy as np

from std_msgs.msg import String as StringMsg
from std_srvs.srv import Trigger, TriggerRequest
from uuv_control_msgs.srv import Hold
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from rosgraph_msgs.msg import Log as RosoutLog

from python_qt_binding import QtWidgets, QtGui, QtCore

try:
    from tf.transformations import euler_from_quaternion
    _HAS_TF = True
except ImportError:
    _HAS_TF = False

try:
    from cv_bridge import CvBridge
    _HAS_BRIDGE = True
except ImportError:
    _HAS_BRIDGE = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle, Ellipse


# ---------------------------------------------------------------------------
# Image viewer widget (auto-fit, no wheel zoom, fixed size)
# ---------------------------------------------------------------------------
class ImageViewWidget(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super(ImageViewWidget, self).__init__(parent)
        self._qimage = None
        self._pixmap = None

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFrameShape(QtWidgets.QFrame.Box)

        # FIXED SIZE for camera views
        self.setFixedSize(360, 220)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                            QtWidgets.QSizePolicy.Fixed)
        self.setSizePolicy(size_policy)

    def set_image(self, qimage: QtGui.QImage):
        if qimage is None or qimage.isNull():
            return
        self._qimage = qimage
        self._pixmap = QtGui.QPixmap.fromImage(qimage)
        self._update_view()

    def _update_view(self):
        if self._pixmap is None or self._pixmap.isNull():
            self.setPixmap(QtGui.QPixmap())
            self.setText("No image")
            return

        self.setText("")
        scaled = self._pixmap.scaled(
            self.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super(ImageViewWidget, self).resizeEvent(event)
        self._update_view()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        event.ignore()  # disable zoom


# ---------------------------------------------------------------------------
# Depth vs time plot using matplotlib
# ---------------------------------------------------------------------------
class DepthPlotCanvas(FigureCanvas):
    """
    Depth vs mission time (seconds).
    """

    def __init__(self, parent=None, max_points=600):
        self._fig = Figure(figsize=(3, 2))
        self._ax = self._fig.add_subplot(111)
        self._ax.set_title("Depth vs Time")
        self._ax.set_xlabel("Time (s)")
        self._ax.set_ylabel("Depth (m)")
        self._ax.invert_yaxis()
        self._ax.grid(True)

        super(DepthPlotCanvas, self).__init__(self._fig)
        self.setParent(parent)

        self._max_points = max_points
        self._ts = []
        self._depths = []
        (self._line,) = self._ax.plot([], [])

    def add_sample(self, t_sec: float, depth: float):
        self._ts.append(float(t_sec))
        self._depths.append(float(depth))

        if len(self._ts) > self._max_points:
            self._ts = self._ts[-self._max_points:]
            self._depths = self._depths[-self._max_points:]

        self._line.set_data(self._ts, self._depths)
        self._ax.relim()
        self._ax.autoscale_view()
        self.draw_idle()


# ---------------------------------------------------------------------------
# Plan-view XY map using matplotlib (with coral sites + grid)
# ---------------------------------------------------------------------------
class XYPlanCanvas(FigureCanvas):
    """
    Plan-view XY track with environment:

    - Fixed grid from -20..120 in X and Y (20 m spacing)
    - Coral sites A, B, C, D drawn as in the reference figure
    - Robot trajectory line + current-position marker
    """

    def __init__(self, parent=None, max_points=2000):
        self._fig = Figure(figsize=(3, 2))
        self._ax = self._fig.add_subplot(111)
        self._ax.set_title("XY Plan View")
        self._ax.set_xlabel("X (m)")
        self._ax.set_ylabel("Y (m)")
        self._ax.grid(False)
        self._ax.set_aspect("equal", adjustable="box")

        super(XYPlanCanvas, self).__init__(self._fig)
        self.setParent(parent)

        self._max_points = max_points
        self._xs = []
        self._ys = []

        self._draw_environment()

        (self._line,) = self._ax.plot([], [], linewidth=1.5)
        self._marker = self._ax.plot([], [], "o", markersize=5)[0]

    def _draw_environment(self):
        x_min, x_max = -20.0, 120.0
        y_min, y_max = -20.0, 120.0
        self._ax.set_xlim(x_min, x_max)
        self._ax.set_ylim(y_min, y_max)

        # 20 m gridlines
        for x in range(-20, 121, 20):
            self._ax.axvline(x, linewidth=0.4, color="#d0e0f0", zorder=0)
        for y in range(-20, 121, 20):
            self._ax.axhline(y, linewidth=0.4, color="#d0e0f0", zorder=0)

        # Site centers
        sites = {
            "A": (0.0, 0.0),
            "B": (80.0, 0.0),
            "C": (0.0, 80.0),
            "D": (80.0, 80.0),
        }

        # A: rectangle 34 x 32
        cx, cy = sites["A"]
        rect_A = Rectangle((cx - 17.0, cy - 16.0), 34.0, 32.0,
                           fill=False, edgecolor="black", linewidth=1.0)
        self._ax.add_patch(rect_A)
        self._ax.text(cx, cy, "A", ha="center", va="center")

        # B: circle Ø15
        cx, cy = sites["B"]
        circ_B = Circle((cx, cy), 7.5, fill=False, edgecolor="black", linewidth=1.0)
        self._ax.add_patch(circ_B)
        self._ax.text(cx, cy, "B", ha="center", va="center")

        # C: ellipse 21 x 6, rotated 90°
        cx, cy = sites["C"]
        ell_C = Ellipse((cx, cy), width=21.0, height=6.0, angle=90,
                        fill=False, edgecolor="black", linewidth=1.0)
        self._ax.add_patch(ell_C)
        self._ax.text(cx, cy, "C", ha="center", va="center")

        # D: small square 5 x 5
        cx, cy = sites["D"]
        rect_D = Rectangle((cx - 2.5, cy - 2.5), 5.0, 5.0,
                           fill=False, edgecolor="black", linewidth=1.0)
        self._ax.add_patch(rect_D)
        self._ax.text(cx, cy, "D", ha="center", va="center")

        self._ax.set_xlim(x_min, x_max)
        self._ax.set_ylim(y_min, y_max)

    def add_sample(self, x: float, y: float):
        self._xs.append(float(x))
        self._ys.append(float(y))

        if len(self._xs) > self._max_points:
            self._xs = self._xs[-self._max_points:]
            self._ys = self._ys[-self._max_points:]

        self._line.set_data(self._xs, self._ys)
        self._marker.set_data([self._xs[-1]], [self._ys[-1]])

        self._ax.figure.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Main GUI widget
# ---------------------------------------------------------------------------
class CoralCaptainWidget(QtWidgets.QWidget):
    # Now carries time_rel as well
    front_image_signal = QtCore.Signal(QtGui.QImage)
    down_image_signal = QtCore.Signal(QtGui.QImage)
    pose_signal = QtCore.Signal(float, float, float, float, float, float)  # x, y, depth, speed, heading, t
    exec_log_signal = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(CoralCaptainWidget, self).__init__(parent)

        # Parameters
        self._pose_topic = rospy.get_param("~pose_topic", "/bluerov2/pose_gt")
        self._front_cam_topic = rospy.get_param(
            "~front_cam_topic", "/bluerov2/bluerov2/camera_front/camera_image"
        )
        self._down_cam_topic = rospy.get_param(
            "~down_cam_topic", "/bluerov2/bluerov2/camera_down/camera_image"
        )

        self._exec_service_name = rospy.get_param(
            "~execute_service", "/coral_action_executor/execute_plan"
        )
        self._hold_service_name = rospy.get_param(
            "~hold_service", "/bluerov2/hold_vehicle"
        )

        # Internal state (textual data)
        self._llm_status_raw = None
        self._exec_status_raw = None
        self._memory_raw = None

        # Internal state (images)
        self._front_qimage = None
        self._down_qimage = None
        self._front_bytes = None
        self._down_bytes = None

        # Time baseline for plots
        self._t0 = rospy.Time.now().to_sec()

        # ROS pubs/subs/clients
        self._prompt_pub = rospy.Publisher(
            "/coral_captain/user_prompt", StringMsg, queue_size=10
        )

        self._llm_status_sub = rospy.Subscriber(
            "/coral_captain/llm_status", StringMsg, self._on_llm_status, queue_size=10
        )

        self._exec_status_sub = rospy.Subscriber(
            "/coral_captain/execution_status", StringMsg,
            self._on_exec_status, queue_size=10
        )

        self._memory_sub = rospy.Subscriber(
            "/coral_captain/memory_state", StringMsg,
            self._on_memory_state, queue_size=10
        )

        self._odom_sub = rospy.Subscriber(
            self._pose_topic, Odometry, self._on_odom, queue_size=1
        )

        self._rosout_sub = rospy.Subscriber(
            "/rosout", RosoutLog, self._on_rosout_log, queue_size=100
        )

        if _HAS_BRIDGE:
            self._bridge = CvBridge()
            rospy.loginfo("[CoralCaptainGUI] cv_bridge OK, subscribing to cameras:")
            rospy.loginfo("  front_cam_topic = %s", self._front_cam_topic)
            rospy.loginfo("  down_cam_topic  = %s", self._down_cam_topic)

            self._front_cam_sub = rospy.Subscriber(
                self._front_cam_topic, Image, self._on_front_image, queue_size=1
            )
            self._down_cam_sub = rospy.Subscriber(
                self._down_cam_topic, Image, self._on_down_image, queue_size=1
            )
        else:
            self._bridge = None
            self._front_cam_sub = None
            self._down_cam_sub = None
            rospy.logwarn("[CoralCaptainGUI] cv_bridge not available; camera views disabled.")

        self._exec_client = None
        self._hold_client = None

        # Build UI & styling
        self._build_ui()
        self._apply_stylesheet()

        self.setWindowTitle("Coral Captain")
        self.setWindowIcon(QtGui.QIcon.fromTheme("applications-science"))
        self.setMinimumSize(1200, 650)

        # Connect signals
        self.front_image_signal.connect(self._set_front_image)
        self.down_image_signal.connect(self._set_down_image)
        self.pose_signal.connect(self._set_pose)
        self.exec_log_signal.connect(self._append_exec_log)

        # Timer for textual UI
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start(100)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(8)

        # Mission console
        mission_box = QtWidgets.QGroupBox("Mission Console")
        mission_layout = QtWidgets.QVBoxLayout(mission_box)
        mission_layout.setContentsMargins(6, 6, 6, 6)
        mission_layout.setSpacing(4)

        history_label = QtWidgets.QLabel("Prompt history (this mission):")
        self._prompt_history = QtWidgets.QPlainTextEdit()
        self._prompt_history.setReadOnly(True)
        self._prompt_history.setPlaceholderText("Sent prompts will appear here...")
        self._prompt_history.setMinimumHeight(80)

        prompt_label = QtWidgets.QLabel("LLM Prompt:")
        self._prompt_edit = QtWidgets.QLineEdit()
        self._prompt_edit.setPlaceholderText(
            "E.g., \"Survey coral bed A, then circle site B and return home.\""
        )
        self._prompt_edit.returnPressed.connect(self._on_send_prompt)

        btn_row = QtWidgets.QHBoxLayout()
        self._btn_send = QtWidgets.QPushButton("Send Prompt")
        self._btn_send.clicked.connect(self._on_send_prompt)

        self._btn_clear = QtWidgets.QPushButton("Clear")
        self._btn_clear.clicked.connect(self._on_clear_prompt)

        self._btn_execute = QtWidgets.QPushButton("Approve & Execute Plan")
        self._btn_execute.clicked.connect(self._on_execute_plan)

        self._btn_emergency_stop = QtWidgets.QPushButton("EMERGENCY STOP")
        self._btn_emergency_stop.setObjectName("emergencyStopButton")
        self._btn_emergency_stop.clicked.connect(self._on_emergency_stop)

        btn_row.addWidget(self._btn_send)
        btn_row.addWidget(self._btn_clear)
        btn_row.addWidget(self._btn_execute)
        btn_row.addWidget(self._btn_emergency_stop)

        mission_layout.addWidget(history_label)
        mission_layout.addWidget(self._prompt_history)
        mission_layout.addWidget(prompt_label)
        mission_layout.addWidget(self._prompt_edit)
        mission_layout.addLayout(btn_row)

        # Mission memory
        memory_box = QtWidgets.QGroupBox("Mission Memory")
        memory_layout = QtWidgets.QVBoxLayout(memory_box)

        summary_label = QtWidgets.QLabel("Summary:")
        self._memory_summary = QtWidgets.QPlainTextEdit()
        self._memory_summary.setReadOnly(True)
        self._memory_summary.setPlaceholderText(
            "Visited sites, completed actions, photos, events..."
        )

        memory_layout.addWidget(summary_label)
        memory_layout.addWidget(self._memory_summary)

        # Front camera
        front_cam_box = QtWidgets.QGroupBox("Front camera")
        front_cam_layout = QtWidgets.QVBoxLayout(front_cam_box)
        self._front_cam_view = ImageViewWidget()
        front_cam_layout.addWidget(self._front_cam_view, alignment=QtCore.Qt.AlignCenter)

        # Executor log
        log_box = QtWidgets.QGroupBox("Executor Log")
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self._exec_log = QtWidgets.QPlainTextEdit()
        self._exec_log.setReadOnly(True)
        log_layout.addWidget(self._exec_log)

        # Vehicle state & plots
        vehicle_box = QtWidgets.QGroupBox("Vehicle State / Depth / XY Plan")
        vehicle_layout = QtWidgets.QVBoxLayout(vehicle_box)

        labels_row = QtWidgets.QGridLayout()
        self._depth_label = QtWidgets.QLabel("Depth: — m")
        self._speed_label = QtWidgets.QLabel("Speed: — m/s")
        self._heading_label = QtWidgets.QLabel("Heading: — °")
        self._position_label = QtWidgets.QLabel("Pos: (x=—, y=—)")

        labels_row.addWidget(self._depth_label,   0, 0)
        labels_row.addWidget(self._speed_label,   0, 1)
        labels_row.addWidget(self._heading_label, 1, 0)
        labels_row.addWidget(self._position_label,1, 1)
        vehicle_layout.addLayout(labels_row)

        # Depth plot
        self._depth_canvas = DepthPlotCanvas()
        self._depth_canvas.setMinimumHeight(160)
        vehicle_layout.addWidget(self._depth_canvas)

        # XY plan view
        self._xy_plan_canvas = XYPlanCanvas()
        self._xy_plan_canvas.setMinimumHeight(220)
        vehicle_layout.addWidget(self._xy_plan_canvas)

        # Downward camera
        down_cam_box = QtWidgets.QGroupBox("Downward camera")
        down_cam_layout = QtWidgets.QVBoxLayout(down_cam_box)
        self._down_cam_view = ImageViewWidget()
        down_cam_layout.addWidget(self._down_cam_view, alignment=QtCore.Qt.AlignCenter)

        # Add to main grid
        grid.addWidget(mission_box,   0, 0)
        grid.addWidget(memory_box,    0, 1)
        grid.addWidget(front_cam_box, 0, 2)
        grid.addWidget(log_box,       1, 0)
        grid.addWidget(vehicle_box,   1, 1)
        grid.addWidget(down_cam_box,  1, 2)

        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #f3f5f7;
                color: #202020;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #c0c0c0;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                font-size: 13px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px 0 8px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #b0b0b0;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e6f0ff;
            }
            QPushButton:pressed {
                background-color: #cadbff;
            }
            QPushButton#emergencyStopButton {
                background-color: #ff4a4a;
                border: 1px solid #b00000;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#emergencyStopButton:hover {
                background-color: #ff7070;
            }
            QPushButton#emergencyStopButton:pressed {
                background-color: #e00000;
            }
            QPlainTextEdit, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
                padding: 3px 6px;
            }
            QLabel {
                font-size: 11px;
            }
        """)

        self._btn_send.setIcon(QtGui.QIcon.fromTheme("mail-send"))
        self._btn_clear.setIcon(QtGui.QIcon.fromTheme("edit-clear"))
        self._btn_execute.setIcon(QtGui.QIcon.fromTheme("media-playback-start"))

    # ------------------------------------------------------------------
    # Timer tick – update text UI
    # ------------------------------------------------------------------
    def _on_timer_tick(self):
        self._update_exec_status_view()
        self._update_memory_view()

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------
    def _on_send_prompt(self):
        text = self._prompt_edit.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(
                self, "Empty prompt", "Please enter a prompt first."
            )
            return

        msg = StringMsg(data=text)
        self._prompt_pub.publish(msg)
        self._llm_status_raw = "planning: " + text

        rospy.loginfo("[CoralCaptainGUI] Prompt sent: %s", text)
        self._prompt_history.appendPlainText(f"> {text}")
        self._prompt_edit.clear()

    def _on_clear_prompt(self):
        self._prompt_edit.clear()

    def _on_execute_plan(self):
        if self._exec_client is None:
            try:
                rospy.loginfo("[CoralCaptainGUI] Waiting for execute service: %s",
                              self._exec_service_name)
                rospy.wait_for_service(self._exec_service_name, timeout=1.0)
                self._exec_client = rospy.ServiceProxy(self._exec_service_name, Trigger)
            except rospy.ROSException:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Executor not available",
                    "Service '{}' not available.".format(self._exec_service_name)
                )
                return

        try:
            resp = self._exec_client(TriggerRequest())
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Execution failed",
                "Service call failed: {}".format(e)
            )
            return

        if resp.success:
            msg = resp.message or "Plan execution started."
            self.exec_log_signal.emit("[GUI] execute_plan: " + msg)
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Execution error",
                resp.message or "Plan execution failed."
            )

    def _on_emergency_stop(self):
        if self._hold_client is None:
            try:
                rospy.loginfo("[CoralCaptainGUI] Waiting for hold service (Hold): %s",
                              self._hold_service_name)
                rospy.wait_for_service(self._hold_service_name, timeout=3.0)
                self._hold_client = rospy.ServiceProxy(self._hold_service_name, Hold)
            except rospy.ROSException:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Emergency stop unavailable",
                    "Service '{}' (uuv_control_msgs/Hold) not available.".format(
                        self._hold_service_name
                    )
                )
                return

        try:
            resp = self._hold_client()
            ok = bool(getattr(resp, "success", True))
            msg = getattr(resp, "message", "")
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Emergency stop failed",
                "Service call failed: {}".format(e)
            )
            return

        if ok:
            self.exec_log_signal.emit(
                "[EMERGENCY] hold_vehicle (Hold) called successfully: {}".format(
                    msg or ""
                )
            )
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Emergency stop error",
                msg or "Vehicle hold/stop command reported failure."
            )
            self.exec_log_signal.emit(
                "[EMERGENCY] hold_vehicle (Hold) FAILED: {}".format(msg)
            )

    # ------------------------------------------------------------------
    # ROS callbacks
    # ------------------------------------------------------------------
    def _on_llm_status(self, msg):
        self._llm_status_raw = msg.data

    def _on_exec_status(self, msg):
        self._exec_status_raw = msg.data

    def _on_memory_state(self, msg):
        self._memory_raw = msg.data

    def _on_odom(self, msg):
        z = msg.pose.pose.position.z
        depth = -z

        v = msg.twist.twist.linear
        speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)

        heading_deg = float('nan')
        if _HAS_TF:
            q = msg.pose.pose.orientation
            quat = [q.x, q.y, q.z, q.w]
            try:
                _, _, yaw = euler_from_quaternion(quat)
                heading_deg = (math.degrees(yaw) + 360.0) % 360.0
            except Exception:
                heading_deg = float('nan')

        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y

        stamp = msg.header.stamp if msg.header.stamp != rospy.Time() else rospy.Time.now()
        t_rel = stamp.to_sec() - self._t0

        self.pose_signal.emit(x, y, depth, speed, heading_deg, t_rel)

    def _on_front_image(self, msg):
        if self._bridge is None:
            return
        try:
            try:
                cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            except Exception:
                cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

            if cv_img.ndim == 2:
                cv_img = np.stack([cv_img] * 3, axis=-1)

            rgb = cv_img[:, :, ::-1]
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            self._front_bytes = rgb.tobytes()
            qimg = QtGui.QImage(
                self._front_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
            )
            self.front_image_signal.emit(qimg)

        except Exception as e:
            rospy.logwarn("[CoralCaptainGUI] Error converting front image: %s", e)

    def _on_down_image(self, msg):
        if self._bridge is None:
            return
        try:
            try:
                cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            except Exception:
                cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

            if cv_img.ndim == 2:
                cv_img = np.stack([cv_img] * 3, axis=-1)

            rgb = cv_img[:, :, ::-1]
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            self._down_bytes = rgb.tobytes()
            qimg = QtGui.QImage(
                self._down_bytes, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
            )
            self.down_image_signal.emit(qimg)

        except Exception as e:
            rospy.logwarn("[CoralCaptainGUI] Error converting down image: %s", e)

    def _on_rosout_log(self, msg: RosoutLog):
        text = msg.msg or ""
        if not text:
            return

        if ("[executor]" not in text and
                "[actions]" not in text and
                "[mission_memory]" not in text and
                "Plan published:" not in text):
            return

        self.exec_log_signal.emit(text)

    # ------------------------------------------------------------------
    # Slots in GUI thread
    # ------------------------------------------------------------------
    @QtCore.Slot(QtGui.QImage)
    def _set_front_image(self, qimg):
        self._front_qimage = qimg
        if self._front_qimage is not None:
            self._front_cam_view.set_image(self._front_qimage)
        else:
            self._front_cam_view.setText("No front camera image")

    @QtCore.Slot(QtGui.QImage)
    def _set_down_image(self, qimg):
        self._down_qimage = qimg
        if self._down_qimage is not None:
            self._down_cam_view.set_image(self._down_qimage)
        else:
            self._down_cam_view.setText("No downward camera image")

    @QtCore.Slot(float, float, float, float, float, float)
    def _set_pose(self, x, y, depth, speed, heading_deg, t_rel):
        self._depth_label.setText(f"Depth: {depth:.1f} m")
        self._speed_label.setText(f"Speed: {speed:.2f} m/s")
        if math.isnan(heading_deg):
            self._heading_label.setText("Heading: (N/A)")
        else:
            self._heading_label.setText(f"Heading: {heading_deg:.1f} °")
        self._position_label.setText(f"Pos: (x={x:.1f}, y={y:.1f})")

        self._depth_canvas.add_sample(t_rel, depth)
        self._xy_plan_canvas.add_sample(x, y)

    @QtCore.Slot(str)
    def _append_exec_log(self, text):
        if not text.strip():
            return
        self._exec_log.appendPlainText(text)

    # ------------------------------------------------------------------
    # UI update helpers
    # ------------------------------------------------------------------
    def _update_exec_status_view(self):
        if self._exec_status_raw is None:
            return

        raw = self._exec_status_raw.strip()
        if not raw:
            return

        state = "unknown"
        try:
            obj = json.loads(raw)
            state = obj.get("state", "unknown")
        except Exception:
            state = raw

        executing = state in ("executing", "executing_step")
        self._btn_execute.setEnabled(not executing)
        # self._btn_execute.setEnabled(!executing if False else not executing)  # simple, always "not executing"

    def _update_memory_view(self):
        if self._memory_raw is None:
            return

        raw = self._memory_raw.strip()
        if not raw:
            return

        try:
            obj = json.loads(raw)
        except Exception:
            obj = None

        summary = self._build_memory_summary(obj) if obj is not None else "(unable to parse memory JSON)"
        self._memory_summary.setPlainText(summary)

    # ------------------------------------------------------------------
    # Memory summary helper
    # ------------------------------------------------------------------
    def _build_memory_summary(self, mem):
        if not isinstance(mem, dict):
            return "(invalid memory structure)"

        visited = mem.get("visited_sites", [])
        completed = mem.get("completed_actions", [])
        photos = mem.get("photos_taken", [])
        last_event = mem.get("last_event", "")
        replan_events = mem.get("replan_events", [])

        lines = []

        if visited:
            lines.append("Visited sites: " + ", ".join(map(str, visited)))
        else:
            lines.append("Visited sites: none yet")

        if completed:
            lines.append(f"Completed actions: {len(completed)}")
            tail = completed[-3:]
            descs = []
            for c in tail:
                if isinstance(c, dict):
                    a = c.get("action", "?")
                    args = c.get("args", {}) if isinstance(c.get("args", {}), dict) else {}
                    site = None
                    if isinstance(args, dict):
                        site = args.get("site") or args.get("footprint")
                    if site:
                        descs.append(f"{a}(site={site})")
                    else:
                        descs.append(a)
                else:
                    descs.append(str(c))
            lines.append("Recent: " + ", ".join(descs))
        else:
            lines.append("Completed actions: none yet")

        if photos:
            last = photos[-1]
            if isinstance(last, dict):
                label = last.get("label", "?")
            else:
                label = str(last)
            lines.append(f"Photos taken: {len(photos)} (last: {label})")
        else:
            lines.append("Photos taken: none yet")

        if last_event:
            lines.append(f"Last event: {last_event}")

        if replan_events:
            lines.append(f"Replans triggered: {len(replan_events)}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def shutdown(self):
        for sub in [
            self._llm_status_sub,
            self._exec_status_sub,
            self._memory_sub,
            self._odom_sub,
            self._rosout_sub,
            getattr(self, "_front_cam_sub", None),
            getattr(self, "_down_cam_sub", None),
        ]:
            try:
                if sub is not None:
                    sub.unregister()
            except Exception:
                pass

        try:
            self._prompt_pub.unregister()
        except Exception:
            pass

        self._exec_client = None
        self._hold_client = None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    rospy.init_node("coral_captain_gui", anonymous=True)

    app = QtWidgets.QApplication(sys.argv)
    widget = CoralCaptainWidget()
    widget.show()

    def on_quit():
        rospy.loginfo("[CoralCaptainGUI] Shutting down GUI")
        widget.shutdown()
        rospy.signal_shutdown("GUI closed")

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
