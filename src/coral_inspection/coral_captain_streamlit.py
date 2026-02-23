#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Coral Captain – Streamlit Web Dashboard (ocean theme + mission map + gadgets)
"""

import json
import math
import threading
from typing import Optional, Tuple, Dict, Any, List

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Ellipse
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import rospy
from std_msgs.msg import String as StringMsg
from std_srvs.srv import Trigger, TriggerRequest
from uuv_control_msgs.srv import Hold
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from rosgraph_msgs.msg import Log as RosoutLog

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


# ---------------------------------------------------------------------------
# ROS interface (same logic as before, just grouped here)
# ---------------------------------------------------------------------------
class CoralCaptainROS:
    def __init__(self):
        self._lock = threading.Lock()

        self.llm_status_raw: Optional[str] = None
        self.exec_status_raw: Optional[str] = None
        self.memory_raw: Optional[str] = None

        self.x: float = float("nan")
        self.y: float = float("nan")
        self.depth: float = float("nan")
        self.speed: float = float("nan")
        self.heading_deg: float = float("nan")

        self.depth_samples: List[float] = []
        self.xy_samples_x: List[float] = []
        self.xy_samples_y: List[float] = []
        self.sample_indices: List[int] = []
        self.max_points = 300

        self.front_image: Optional[np.ndarray] = None
        self.down_image: Optional[np.ndarray] = None

        self.exec_log_lines: List[str] = []

        self.bridge = CvBridge() if _HAS_BRIDGE else None

        self.pose_topic = rospy.get_param("~pose_topic", "/bluerov2/pose_gt")
        self.front_cam_topic = rospy.get_param(
            "~front_cam_topic", "/bluerov2/bluerov2/camera_front/camera_image"
        )
        self.down_cam_topic = rospy.get_param(
            "~down_cam_topic", "/bluerov2/bluerov2/camera_down/camera_image"
        )
        self.exec_service_name = rospy.get_param(
            "~execute_service", "/coral_action_executor/execute_plan"
        )
        self.hold_service_name = rospy.get_param(
            "~hold_service", "/bluerov2/hold_vehicle"
        )

        try:
            rospy.init_node("coral_captain_streamlit", anonymous=True, disable_signals=True)
        except rospy.exceptions.ROSException:
            # already initialised
            pass

        self.prompt_pub = rospy.Publisher(
            "/coral_captain/user_prompt", StringMsg, queue_size=10
        )

        self.llm_status_sub = rospy.Subscriber(
            "/coral_captain/llm_status", StringMsg, self._on_llm_status, queue_size=10
        )
        self.exec_status_sub = rospy.Subscriber(
            "/coral_captain/execution_status", StringMsg,
            self._on_exec_status, queue_size=10
        )
        self.memory_sub = rospy.Subscriber(
            "/coral_captain/memory_state", StringMsg,
            self._on_memory_state, queue_size=10
        )
        self.odom_sub = rospy.Subscriber(
            self.pose_topic, Odometry, self._on_odom, queue_size=1
        )
        self.rosout_sub = rospy.Subscriber(
            "/rosout", RosoutLog, self._on_rosout_log, queue_size=100
        )

        if self.bridge is not None:
            self.front_cam_sub = rospy.Subscriber(
                self.front_cam_topic, Image, self._on_front_image, queue_size=1
            )
            self.down_cam_sub = rospy.Subscriber(
                self.down_cam_topic, Image, self._on_down_image, queue_size=1
            )
        else:
            self.front_cam_sub = None
            self.down_cam_sub = None
            rospy.logwarn("[CoralCaptainStreamlit] cv_bridge not available; camera views disabled.")

        self.exec_client = None
        self.hold_client = None

    # --- callbacks ---

    def _on_llm_status(self, msg: StringMsg):
        with self._lock:
            self.llm_status_raw = msg.data

    def _on_exec_status(self, msg: StringMsg):
        with self._lock:
            self.exec_status_raw = msg.data

    def _on_memory_state(self, msg: StringMsg):
        with self._lock:
            self.memory_raw = msg.data

    def _on_odom(self, msg: Odometry):
        z = msg.pose.pose.position.z
        depth = -z
        v = msg.twist.twist.linear
        speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)

        heading_deg = float("nan")
        if _HAS_TF:
            q = msg.pose.pose.orientation
            quat = [q.x, q.y, q.z, q.w]
            try:
                _, _, yaw = euler_from_quaternion(quat)
                heading_deg = (math.degrees(yaw) + 360.0) % 360.0
            except Exception:
                heading_deg = float("nan")

        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y

        with self._lock:
            self.x = x
            self.y = y
            self.depth = depth
            self.speed = speed
            self.heading_deg = heading_deg

            idx = self.sample_indices[-1] + 1 if self.sample_indices else 0
            self.sample_indices.append(idx)
            self.depth_samples.append(depth)
            self.xy_samples_x.append(float(x))
            self.xy_samples_y.append(float(y))

            if len(self.sample_indices) > self.max_points:
                self.sample_indices = self.sample_indices[-self.max_points:]
                self.depth_samples = self.depth_samples[-self.max_points:]
                self.xy_samples_x = self.xy_samples_x[-self.max_points:]
                self.xy_samples_y = self.xy_samples_y[-self.max_points:]

    def _on_front_image(self, msg: Image):
        if self.bridge is None:
            return
        try:
            try:
                cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            except Exception:
                cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

            if cv_img.ndim == 2:
                cv_img = np.stack([cv_img] * 3, axis=-1)

            rgb = cv_img[:, :, ::-1]
            with self._lock:
                self.front_image = rgb
        except Exception as e:
            rospy.logwarn("[CoralCaptainStreamlit] Error converting front image: %s", e)

    def _on_down_image(self, msg: Image):
        if self.bridge is None:
            return
        try:
            try:
                cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            except Exception:
                cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

            if cv_img.ndim == 2:
                cv_img = np.stack([cv_img] * 3, axis=-1)

            rgb = cv_img[:, :, ::-1]
            with self._lock:
                self.down_image = rgb
        except Exception as e:
            rospy.logwarn("[CoralCaptainStreamlit] Error converting down image: %s", e)

    def _on_rosout_log(self, msg: RosoutLog):
        text = msg.msg or ""
        if not text:
            return
        if ("[executor]" not in text and
                "[actions]" not in text and
                "[mission_memory]" not in text and
                "Plan published:" not in text):
            return
        with self._lock:
            self.exec_log_lines.append(text)
            if len(self.exec_log_lines) > 1000:
                self.exec_log_lines = self.exec_log_lines[-1000:]

    # --- public API / helpers ---

    def send_prompt(self, text: str):
        msg = StringMsg(data=text)
        self.prompt_pub.publish(msg)
        with self._lock:
            self.llm_status_raw = "planning: " + text
        rospy.loginfo("[CoralCaptainStreamlit] Prompt sent: %s", text)

    def execute_plan(self) -> Tuple[bool, str]:
        if self.exec_client is None:
            try:
                rospy.wait_for_service(self.exec_service_name, timeout=1.0)
                self.exec_client = rospy.ServiceProxy(self.exec_service_name, Trigger)
            except rospy.ROSException:
                return False, f"Service '{self.exec_service_name}' not available."
        try:
            resp = self.exec_client(TriggerRequest())
        except Exception as e:
            return False, f"Service call failed: {e}"
        if resp.success:
            msg = resp.message or "Plan execution started."
            with self._lock:
                self.exec_log_lines.append("[GUI] execute_plan: " + msg)
            return True, msg
        else:
            return False, resp.message or "Plan execution failed."

    def emergency_stop(self) -> Tuple[bool, str]:
        if self.hold_client is None:
            try:
                rospy.wait_for_service(self.hold_service_name, timeout=3.0)
                self.hold_client = rospy.ServiceProxy(self.hold_service_name, Hold)
            except rospy.ROSException:
                return False, (
                    f"Service '{self.hold_service_name}' "
                    "(uuv_control_msgs/Hold) not available."
                )
        try:
            resp = self.hold_client()
            ok = bool(getattr(resp, "success", True))
            msg = getattr(resp, "message", "")
        except Exception as e:
            return False, f"Service call failed: {e}"
        with self._lock:
            if ok:
                self.exec_log_lines.append(
                    f"[EMERGENCY] hold_vehicle (Hold) called successfully: {msg}"
                )
            else:
                self.exec_log_lines.append(
                    f"[EMERGENCY] hold_vehicle (Hold) FAILED: {msg}"
                )
        return ok, msg

    def _build_memory_summary(self, mem: Dict[str, Any]) -> str:
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

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            exec_state = "unknown"
            if self.exec_status_raw:
                raw = self.exec_status_raw.strip()
                if raw:
                    try:
                        obj = json.loads(raw)
                        exec_state = obj.get("state", "unknown")
                    except Exception:
                        exec_state = raw

            memory_summary = ""
            if self.memory_raw:
                raw = self.memory_raw.strip()
                if raw:
                    try:
                        obj = json.loads(raw)
                        memory_summary = self._build_memory_summary(obj)
                    except Exception:
                        memory_summary = "(unable to parse memory JSON)"

            log_text = "\n".join(self.exec_log_lines[-500:])

            depth_samples = list(self.depth_samples)
            xy_x = list(self.xy_samples_x)
            xy_y = list(self.xy_samples_y)
            sample_indices = list(self.sample_indices)

            front_img = None if self.front_image is None else self.front_image.copy()
            down_img = None if self.down_image is None else self.down_image.copy()

            return {
                "exec_state": exec_state,
                "memory_summary": memory_summary,
                "depth": self.depth,
                "speed": self.speed,
                "heading_deg": self.heading_deg,
                "x": self.x,
                "y": self.y,
                "depth_samples": depth_samples,
                "xy_x": xy_x,
                "xy_y": xy_y,
                "sample_indices": sample_indices,
                "front_image": front_img,
                "down_image": down_img,
                "exec_log": log_text,
            }


@st.cache_resource
def get_ros_interface() -> CoralCaptainROS:
    return CoralCaptainROS()


# ---------------------------------------------------------------------------
# UI helpers: theme, map, and metrics
# ---------------------------------------------------------------------------
def _inject_css():
    # light ocean / grey background, white cards
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #dfe9f3 0%, #f7fbff 40%, #b7d3ea 100%);
            color: #102a43;
        }
        .block-container {
            padding-top: 0.6rem;
            padding-bottom: 1.0rem;
        }
        .cc-card {
            background: rgba(255,255,255,0.95);
            border-radius: 16px;
            padding: 16px 18px;
            box-shadow: 0 10px 25px rgba(15, 35, 60, 0.20);
            border: 1px solid rgba(170,190,214,0.7);
        }
        .cc-title {
            font-weight: 600;
            font-size: 1.05rem;
            color: #102a43;
            margin-bottom: 0.4rem;
        }
        .cc-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #829ab1;
            margin-bottom: 0.2rem;
        }
        .cc-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .cc-pill-ok {
            background: rgba(74, 222, 128, 0.15);
            color: #15803d;
            border: 1px solid rgba(21,128,61,0.55);
        }
        .cc-pill-bad {
            background: rgba(248, 113, 113, 0.15);
            color: #b91c1c;
            border: 1px solid rgba(185,28,28,0.55);
        }
        .cc-log textarea {
            font-family: "SF Mono", Menlo, Consolas, monospace;
            font-size: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def make_mission_map(current_x, current_y, traj_x, traj_y):
    """Draw coral grid + ROV path + current position."""
    sites = {
        "A: rectangle bed (34×32 m)": {"center": (0, 0)},
        "B: circle bed (Ø15 m)": {"center": (80, 0)},
        "C: circle cluster (21×6 m)": {"center": (0, 80)},
        "D: bed+crown small (5×5 m)": {"center": (80, 80)},
    }

    fig, ax = plt.subplots(figsize=(5, 5))

    # A
    cx, cy = sites["A: rectangle bed (34×32 m)"]["center"]
    ax.add_patch(Rectangle((cx - 17, cy - 16), 34, 32, fill=False))
    ax.text(cx, cy, "A", ha="center", va="center")

    # B
    cx, cy = sites["B: circle bed (Ø15 m)"]["center"]
    ax.add_patch(Circle((cx, cy), 7.5, fill=False))
    ax.text(cx, cy, "B", ha="center", va="center")

    # C
    cx, cy = sites["C: circle cluster (21×6 m)"]["center"]
    ax.add_patch(Ellipse((cx, cy), width=21, height=6, angle=90, fill=False))
    ax.text(cx, cy, "C", ha="center", va="center")

    # D
    cx, cy = sites["D: bed+crown small (5×5 m)"]["center"]
    ax.add_patch(Rectangle((cx - 2.5, cy - 2.5), 5, 5, fill=False))
    ax.text(cx, cy, "D", ha="center", va="center")

    # Grid
    for xg in range(-20, 121, 20):
        ax.axvline(xg, linewidth=0.2)
    for yg in range(-20, 121, 20):
        ax.axhline(yg, linewidth=0.2)

    # Trajectory
    if traj_x and traj_y and len(traj_x) == len(traj_y):
        ax.plot(traj_x, traj_y)  # default style

    # Current position as a larger marker
    if not any(map(math.isnan, [current_x, current_y])):
        ax.plot(current_x, current_y, marker="o", markersize=8)

    ax.set_aspect("equal", "box")
    ax.set_xlim(-20, 120)
    ax.set_ylim(-20, 120)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title("Mission map: coral sites & ROV track")
    fig.tight_layout()
    return fig


def depth_zone(depth_m: float) -> str:
    if math.isnan(depth_m):
        return "unknown"
    if depth_m < 1.0:
        return "surface"
    if depth_m < 10.0:
        return "survey band"
    return "deep"


def speed_zone(speed_ms: float) -> str:
    if math.isnan(speed_ms):
        return "unknown"
    if speed_ms < 0.05:
        return "stopped"
    if speed_ms < 0.3:
        return "slow"
    if speed_ms < 0.7:
        return "cruise"
    return "fast"


def metric_with_delta(label: str, value: float, key: str, fmt: str = "{:.2f}"):
    """Streamlit metric with simple delta from last frame."""
    prev = st.session_state.get(key)
    if math.isnan(value):
        display = "—"
        delta = None
    else:
        display = fmt.format(value)
        if prev is None or math.isnan(prev):
            delta = None
        else:
            diff = value - prev
            if abs(diff) < 1e-3:
                delta = "0"
            else:
                delta = ("+" if diff > 0 else "") + fmt.format(diff)
    st.metric(label, display, delta=delta)
    if not math.isnan(value):
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# Main Streamlit app
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="Coral Captain",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()

    st.sidebar.markdown("### Coral Captain")

    # Auto-refresh (controls how “live” everything feels)
    refresh_ms = st.sidebar.slider(
        "Auto-refresh interval (ms)",
        min_value=100,
        max_value=2000,
        value=250,
        step=50,
        help="Lower = more live, higher = less CPU usage.",
    )
    st_autorefresh(interval=refresh_ms, limit=None, key="coral_autorefresh")

    ros_if = get_ros_interface()
    snapshot = ros_if.get_snapshot()

    ros_ok = not rospy.is_shutdown()
    ros_pill_class = "cc-pill-ok" if ros_ok else "cc-pill-bad"
    ros_text = "ROS node running" if ros_ok else "ROS node stopped"
    st.sidebar.markdown(
        f"""
        <div class="cc-pill {ros_pill_class}">
          <span>ROS:</span>
          <span>{ros_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "prompt_history" not in st.session_state:
        st.session_state.prompt_history = []

    st.markdown("## Coral Captain")

    # -------------------- Top row: console + memory --------------------
    top_left, top_right = st.columns([2.0, 1.2])

    with top_left:
        st.markdown('<div class="cc-card">', unsafe_allow_html=True)
        st.markdown('<div class="cc-title">Mission Console</div>', unsafe_allow_html=True)

        st.markdown('<div class="cc-label">Prompt history (this mission)</div>',
                    unsafe_allow_html=True)
        history_str = "\n".join(st.session_state.prompt_history)
        st.text_area("", value=history_str, height=110, key="history_view", disabled=True)

        prompt = st.text_input(
            "LLM Prompt",
            placeholder='e.g. "Survey coral bed A, then circle site B and return home."',
            key="prompt_input",
        )

        c1, c2, c3, c4 = st.columns(4)
        send_clicked = c1.button("Send", use_container_width=True)
        clear_clicked = c2.button("Clear", use_container_width=True)
        exec_clicked = c3.button("Approve & Execute", use_container_width=True)
        emergency_clicked = c4.button("EMERGENCY STOP", use_container_width=True)

        if send_clicked and prompt.strip():
            ros_if.send_prompt(prompt.strip())
            st.session_state.prompt_history.append(f"> {prompt.strip()}")
            st.session_state.prompt_input = ""

        if clear_clicked:
            st.session_state.prompt_input = ""

        if exec_clicked:
            ok, msg = ros_if.execute_plan()
            (st.success if ok else st.error)(msg)

        if emergency_clicked:
            ok, msg = ros_if.emergency_stop()
            if ok:
                st.warning("Emergency stop / hold sent successfully: " + (msg or ""))
            else:
                st.error("Emergency stop error: " + (msg or ""))

        st.markdown(
            f"<p style='margin-top:0.4rem;'>Executor state: "
            f"<strong>{snapshot['exec_state']}</strong></p>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with top_right:
        st.markdown('<div class="cc-card">', unsafe_allow_html=True)
        st.markdown('<div class="cc-title">Mission Memory</div>', unsafe_allow_html=True)
        st.markdown('<div class="cc-label">Summary</div>', unsafe_allow_html=True)
        st.text_area(
            "",
            value=snapshot["memory_summary"] or "",
            height=210,
            disabled=True,
            key="memory_summary_view",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # -------------------- Middle row: state/map + cameras ---------------
    mid_left, mid_right = st.columns([2.0, 1.2])

    with mid_left:
        st.markdown('<div class="cc-card">', unsafe_allow_html=True)
        st.markdown('<div class="cc-title">Vehicle State & Environment</div>',
                    unsafe_allow_html=True)

        d = snapshot["depth"]
        s = snapshot["speed"]
        h = snapshot["heading_deg"]
        x = snapshot["x"]
        y = snapshot["y"]

        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            metric_with_delta("Depth (m)", d, "prev_depth", "{:.1f}")
            st.caption(f"Depth zone: **{depth_zone(d)}**")
        with mcol2:
            metric_with_delta("Speed (m/s)", s, "prev_speed", "{:.2f}")
            st.caption(f"Speed zone: **{speed_zone(s)}**")
        with mcol3:
            metric_with_delta("Heading (°)", h, "prev_heading", "{:.1f}")

        mcol4, mcol5 = st.columns(2)
        with mcol4:
            metric_with_delta("X (m)", x, "prev_x", "{:.1f}")
        with mcol5:
            metric_with_delta("Y (m)", y, "prev_y", "{:.1f}")

        depth_samples = snapshot["depth_samples"]
        sample_indices = snapshot["sample_indices"]
        xy_x = snapshot["xy_x"]
        xy_y = snapshot["xy_y"]

        # Depth trend
        st.markdown('<div class="cc-label" style="margin-top:0.6rem;">Depth vs sample index</div>',
                    unsafe_allow_html=True)
        if depth_samples and sample_indices:
            fig1, ax1 = plt.subplots()
            ax1.plot(sample_indices, depth_samples)
            ax1.set_xlabel("Samples")
            ax1.set_ylabel("Depth (m)")
            ax1.invert_yaxis()
            ax1.grid(True)
            st.pyplot(fig1, use_container_width=True)
        else:
            st.info("No depth samples yet.")

        # X/Y trend
        st.markdown('<div class="cc-label" style="margin-top:0.4rem;">X / Y vs sample index</div>',
                    unsafe_allow_html=True)
        if xy_x and xy_y and sample_indices:
            fig2, ax2 = plt.subplots()
            ax2.plot(sample_indices, xy_x, label="x")
            ax2.plot(sample_indices, xy_y, label="y")
            ax2.set_xlabel("Samples")
            ax2.set_ylabel("Position (m)")
            ax2.grid(True)
            ax2.legend(loc="upper right", fontsize=8)
            st.pyplot(fig2, use_container_width=True)
        else:
            st.info("No position samples yet.")

        # Mission map
        st.markdown('<div class="cc-label" style="margin-top:0.4rem;">Mission map</div>',
                    unsafe_allow_html=True)
        fig_map = make_mission_map(x, y, xy_x, xy_y)
        st.pyplot(fig_map, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with mid_right:
        st.markdown('<div class="cc-card">', unsafe_allow_html=True)
        st.markdown('<div class="cc-title">Cameras (live)</div>', unsafe_allow_html=True)
        st.caption("Streams update with the same auto-refresh interval as the rest of the dashboard.")

        front_tab, down_tab = st.tabs(["Front", "Downward"])

        with front_tab:
            if snapshot["front_image"] is not None:
                st.image(snapshot["front_image"], use_container_width=True)
            else:
                st.info("No front camera image received yet (topic or cv_bridge missing).")

        with down_tab:
            if snapshot["down_image"] is not None:
                st.image(snapshot["down_image"], use_container_width=True)
            else:
                st.info("No downward camera image received yet (topic or cv_bridge missing).")

        st.markdown("</div>", unsafe_allow_html=True)

    # -------------------- Bottom row: executor log ----------------------
    st.markdown('<div class="cc-card cc-log">', unsafe_allow_html=True)
    st.markdown('<div class="cc-title">Executor Log</div>', unsafe_allow_html=True)
    st.text_area(
        "",
        value=snapshot["exec_log"],
        height=220,
        disabled=True,
        key="exec_log_view",
    )
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
