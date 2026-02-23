# src/coral_inspection/tools/action_tools.py
# -*- coding: utf-8 -*-

import math
import yaml
import rospy

from nav_msgs.msg import Odometry

# Shared helpers some per-action modules might reuse
from std_msgs.msg import Time as TimeMsg, String as StringMsg, Header
from geometry_msgs.msg import Point
from uuv_control_msgs.msg import Waypoint

# Import per-action implementations
from coral_inspection.tools.actions.go_to import do_go_to
from coral_inspection.tools.actions.go_to_site import do_go_to_site
from coral_inspection.tools.actions.waypoint_list import do_waypoint_list
from coral_inspection.tools.actions.circular import do_circular
from coral_inspection.tools.actions.helical import do_helical
from coral_inspection.tools.actions.waypoint_file import do_waypoint_file
from coral_inspection.tools.actions.hold import do_hold
from coral_inspection.tools.actions.survey_rectangle import do_survey_rectangle
from coral_inspection.tools.actions.survey_site import do_survey_site
from coral_inspection.tools.actions.survey_circle_rings import do_survey_circle_rings

from coral_inspection.tools.actions.hover_observe import do_hover_observe
from coral_inspection.tools.actions.return_home import do_return_home
from coral_inspection.tools.actions.emergency_stop import do_emergency_stop
from coral_inspection.tools.actions.take_photo import do_take_photo
from coral_inspection.tools.actions.replan_on_event import do_replan_on_event


class ActionTools(object):
    """
    Central context + utilities for all actions.

    This class holds:
      - vehicle namespace and service names
      - pose subscriber and latest pose
      - coral site database (from YAML)
      - survey defaults
      - generic helpers (_wait_until_near, site lookup, lawnmower generation)

    Each actual action implementation lives in a separate module under:
      coral_inspection.tools.actions.*

    The methods here are just thin delegators:
      do_go_to(self, args) -> actions.go_to.do_go_to(self, args)
    """

    def __init__(self, vehicle_ns="/bluerov2",
                 pose_topic=None,
                 wait_for_motion=True):

        self.vehicle_ns = vehicle_ns
        self.wait_for_motion = wait_for_motion

        if pose_topic is None:
            pose_topic = self.vehicle_ns + "/pose_gt"
        self.pose_topic = pose_topic

        # Service names
        self.srv_go_to         = self.vehicle_ns + "/go_to"
        self.srv_wp_list       = self.vehicle_ns + "/start_waypoint_list"
        self.srv_circular      = self.vehicle_ns + "/start_circular_trajectory"
        self.srv_helical       = self.vehicle_ns + "/start_helical_trajectory"
        self.srv_wp_file       = self.vehicle_ns + "/init_waypoints_from_file"
        self.srv_hold          = self.vehicle_ns + "/hold_vehicle"

        # Pose state
        self._have_pose = False
        self._pose_x = 0.0
        self._pose_y = 0.0
        self._pose_z = 0.0

        rospy.Subscriber(self.pose_topic, Odometry, self._pose_cb)

        # Coral site database + survey defaults
        self.sites = {}
        self.survey_defaults = {
            "stripe_spacing": 4.0,
            "turn_buffer": 5.0,
            "speed_mps": 0.5,
            "altitude_m": 3.0
        }

        sites_yaml_path = rospy.get_param("~sites_yaml", "")
        if sites_yaml_path:
            try:
                with open(sites_yaml_path, "r") as f:
                    data = yaml.safe_load(f)
                self._build_sites_from_yaml(data)
                rospy.loginfo("[actions] Loaded %d coral sites from %s",
                              len(self.sites), sites_yaml_path)
            except Exception as e:
                rospy.logwarn("[actions] Failed to load sites YAML '%s': %s",
                              sites_yaml_path, e)
        else:
            rospy.logwarn("[actions] No '~sites_yaml' parameter set; go_to_site/survey may be limited.")

        rospy.loginfo("[actions] vehicle_ns=%s pose_topic=%s wait_for_motion=%s",
                      self.vehicle_ns, self.pose_topic, self.wait_for_motion)

    # ------------------------------------------------------------------
    # Pose handling & generic wait helper
    # ------------------------------------------------------------------
    def _pose_cb(self, msg):
        self._pose_x = msg.pose.pose.position.x
        self._pose_y = msg.pose.pose.position.y
        self._pose_z = msg.pose.pose.position.z
        self._have_pose = True

    def _wait_until_near(self, target, radius, timeout_sec, label="target"):
        """Generic pose-based waiting helper."""
        if not self.wait_for_motion:
            return True

        if not self._have_pose:
            rospy.logwarn("[actions] %s: no pose yet on %s, not waiting",
                          label, self.pose_topic)
            return True

        tx, ty, tz = target
        rospy.loginfo("[actions] %s: waiting until within %.2f m...", label, radius)

        rate = rospy.Rate(5)  # Hz
        timeout = rospy.Time.now() + rospy.Duration(timeout_sec)

        while not rospy.is_shutdown() and rospy.Time.now() < timeout:
            dx = self._pose_x - tx
            dy = self._pose_y - ty
            dz = self._pose_z - tz
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)

            if dist <= radius:
                rospy.loginfo("[actions] %s reached, dist=%.2f m", label, dist)
                return True

            rate.sleep()

        rospy.logwarn("[actions] %s: timeout waiting to reach target", label)
        return False

    # ------------------------------------------------------------------
    # Sites & survey helpers
    # ------------------------------------------------------------------
    def _build_sites_from_yaml(self, data):
        """
        Build a generic sites dict from YAML of the form:

        frames:
          site_A: {x:..., y:..., z:..., yaw_deg:...}
          ...

        footprints:
          coral_bed_A:
            center: site_A
            type: rectangle
            size_x: ...
            size_y: ...
            yaw_deg: ...

        survey:
          stripe_spacing, turn_buffer, speed_mps, altitude_m
        """
        frames = data.get("frames", {})
        footprints = data.get("footprints", {})
        survey = data.get("survey", {})

        # Survey defaults
        try:
            self.survey_defaults["stripe_spacing"] = float(
                survey.get("stripe_spacing", self.survey_defaults["stripe_spacing"]))
            self.survey_defaults["turn_buffer"] = float(
                survey.get("turn_buffer", self.survey_defaults["turn_buffer"]))
            self.survey_defaults["speed_mps"] = float(
                survey.get("speed_mps", self.survey_defaults["speed_mps"]))
            self.survey_defaults["altitude_m"] = float(
                survey.get("altitude_m", self.survey_defaults["altitude_m"]))
        except Exception as e:
            rospy.logwarn("[actions] Invalid 'survey' defaults in YAML: %s", e)

        # Index frames by name
        frame_centers = {}
        for frame_name, info in frames.items():
            try:
                x = float(info.get("x", 0.0))
                y = float(info.get("y", 0.0))
                z = float(info.get("z", -60.0))
                yaw_deg = float(info.get("yaw_deg", 0.0))
            except Exception as e:
                rospy.logwarn("[actions] Invalid frame '%s': %s", frame_name, e)
                continue

            frame_centers[frame_name] = {
                "center": (x, y, z),
                "yaw_deg": yaw_deg
            }

            self.sites[frame_name] = {
                "center": (x, y, z),
                "yaw_deg": yaw_deg
            }

            if frame_name.lower().startswith("site_"):
                short = frame_name.split("_", 1)[1].upper()
                self.sites[short] = {
                    "center": (x, y, z),
                    "yaw_deg": yaw_deg
                }

        # Link footprints to frames
        for fp_name, info in footprints.items():
            center_ref = info.get("center", None)
            if center_ref not in frame_centers:
                rospy.logwarn("[actions] Footprint '%s' references unknown frame '%s'",
                              fp_name, center_ref)
                continue

            base = frame_centers[center_ref]
            x, y, z = base["center"]
            yaw_deg = float(info.get("yaw_deg", base.get("yaw_deg", 0.0)))
            fp_type = info.get("type", "unknown")

            site_info = {
                "center": (x, y, z),
                "yaw_deg": yaw_deg,
                "footprint_type": fp_type,
                "raw": info
            }

            self.sites[fp_name] = site_info

            parts = fp_name.split("_")
            if parts:
                suffix = parts[-1]
                if len(suffix) == 1 and suffix.isalpha():
                    key = suffix.upper()
                    if key not in self.sites:
                        self.sites[key] = site_info

        rospy.loginfo("[actions] Sites available: %s",
                      ", ".join(sorted(self.sites.keys())))

    def _get_site_info(self, site_name):
        """Return full site info dict for a named site, or None if unknown."""
        if not self.sites:
            rospy.logerr("[actions] sites database is empty; cannot resolve site '%s'",
                         site_name)
            return None

        raw_key = str(site_name).strip()
        if raw_key in self.sites:
            info = self.sites[raw_key]
        else:
            upper = raw_key.upper()
            if upper in self.sites:
                info = self.sites[upper]
            else:
                rospy.logerr("[actions] Unknown site '%s'. Known: %s",
                             raw_key, ", ".join(sorted(self.sites.keys())))
                return None

        return info

    def _get_site_center(self, site_name):
        """Return (x, y, z) center for a named site, or None if unknown."""
        info = self._get_site_info(site_name)
        if info is None:
            return None

        center = info.get("center", None)
        if center is None or len(center) < 3:
            rospy.logerr("[actions] Site '%s' has invalid center: %s", site_name, center)
            return None

        return float(center[0]), float(center[1]), float(center[2])

    def _generate_lawnmower_waypoints(self, site_info, args):
        """
        Generate a simple lawnmower (boustrophedon) waypoint pattern for
        rectangular/square footprints.
        """
        fp_type = site_info.get("footprint_type", "")
        raw = site_info.get("raw", {})

        if fp_type not in ("rectangle", "square"):
            rospy.logerr("[actions] survey_rectangle: footprint_type '%s' not supported",
                         fp_type)
            return []

        if fp_type == "square":
            size = float(raw.get("size", 0.0))
            size_x = size_y = size
        else:
            size_x = float(raw.get("size_x", 0.0))
            size_y = float(raw.get("size_y", 0.0))

        if size_x <= 0.0 or size_y <= 0.0:
            rospy.logerr("[actions] survey_rectangle: invalid footprint size (%f, %f)",
                         size_x, size_y)
            return []

        (cx, cy, cz) = site_info.get("center", (0.0, 0.0, -60.0))
        yaw_deg = float(site_info.get("yaw_deg", 0.0))
        yaw_rad = math.radians(yaw_deg)

        stripe_spacing = float(args.get(
            "stripe_spacing", self.survey_defaults.get("stripe_spacing", 4.0)))
        turn_buffer = float(args.get(
            "turn_buffer", self.survey_defaults.get("turn_buffer", 5.0)))
        speed = float(args.get(
            "max_forward_speed", self.survey_defaults.get("speed_mps", 0.5)))
        radius = float(args.get("radius_of_acceptance", 1.0))

        if "z" in args:
            z_target = float(args["z"])
        else:
            altitude_m = float(self.survey_defaults.get("altitude_m", 3.0))
            z_target = cz + altitude_m

        half_x = size_x / 2.0
        half_y = size_y / 2.0

        if stripe_spacing <= 0.0:
            stripe_spacing = 4.0

        waypoints = []

        y = -half_y
        direction = 1  # 1: left->right, -1: right->left

        def local_to_world(xl, yl):
            xw = cx + (xl * math.cos(yaw_rad) - yl * math.sin(yaw_rad))
            yw = cy + (xl * math.sin(yaw_rad) + yl * math.cos(yaw_rad))
            return xw, yw

        while y <= half_y + 1e-6:
            if direction > 0:
                x_start_local = -half_x - turn_buffer
                x_end_local = +half_x + turn_buffer
            else:
                x_start_local = +half_x + turn_buffer
                x_end_local = -half_x - turn_buffer

            xw1, yw1 = local_to_world(x_start_local, y)
            waypoints.append({
                "x": xw1,
                "y": yw1,
                "z": z_target,
                "max_forward_speed": speed,
                "radius_of_acceptance": radius
            })

            xw2, yw2 = local_to_world(x_end_local, y)
            waypoints.append({
                "x": xw2,
                "y": yw2,
                "z": z_target,
                "max_forward_speed": speed,
                "radius_of_acceptance": radius
            })

            y += stripe_spacing
            direction *= -1

        rospy.loginfo("[actions] survey_rectangle: generated %d waypoints", len(waypoints))
        return waypoints

    # ------------------------------------------------------------------
    # Thin delegators to per-action modules
    # ------------------------------------------------------------------
    def do_go_to(self, args):
        return do_go_to(self, args)

    def do_go_to_site(self, args):
        return do_go_to_site(self, args)

    def do_waypoint_list(self, args):
        return do_waypoint_list(self, args)

    def do_circular(self, args):
        return do_circular(self, args)

    def do_helical(self, args):
        return do_helical(self, args)

    def do_waypoint_file(self, args):
        return do_waypoint_file(self, args)

    def do_hold(self, args):
        return do_hold(self, args)

    def do_survey_rectangle(self, args):
        return do_survey_rectangle(self, args)

    def do_survey_site(self, args):
        return do_survey_site(self, args)

    def do_survey_circle_rings(self, args):
        return do_survey_circle_rings(self, args)

    def do_hover_observe(self, args):
        return do_hover_observe(self, args)

    def do_return_home(self, args):
        return do_return_home(self, args)

    def do_emergency_stop(self, args):
        return do_emergency_stop(self, args)

    def do_take_photo(self, args):
        return do_take_photo(self, args)

    def do_replan_on_event(self, args):
        return do_replan_on_event(self, args)
