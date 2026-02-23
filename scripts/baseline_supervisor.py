# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
# import json, yaml, math, os
# import rospy
# from std_msgs.msg import String, Bool
# from std_srvs.srv import Trigger, TriggerResponse
# from nav_msgs.msg import Odometry

# from coral_inspection.tools.execute_yaml_tool import execute_yaml
# from coral_inspection.tools.hold_tool import hold_vehicle

# class BaselineSupervisor:
#     """
#     Minimal baseline with:
#       - propose -> approve -> execute
#       - auto-hold when reaching the final waypoint (distance threshold)
#       - manual stop service (/baseline/stop_now) to hold immediately
#     """
#     def __init__(self):
#         rospy.init_node("baseline_supervisor")

#         self.vehicle_ns    = rospy.get_param("~vehicle_ns", "/bluerov2")
#         self.init_service  = rospy.get_param("~init_service", self.vehicle_ns + "/init_waypoints_from_file")
#         self.hold_service  = rospy.get_param("~hold_service", self.vehicle_ns + "/hold_vehicle")
#         self.interpolator  = rospy.get_param("~interpolator", "cubic")
#         self.default_yaml  = rospy.get_param("~default_yaml", "/tmp/mission.yaml")

#         # Odometry + completion params
#         self.odom_topic    = rospy.get_param("~odom_topic", self.vehicle_ns + "/pose_gt")
#         self.pos_tolerance = float(rospy.get_param("~pos_tolerance", 2.0))   # meters (xy)
#         self.z_tolerance   = float(rospy.get_param("~z_tolerance", 2.0))     # meters (z)
#         self.check_rate_hz = float(rospy.get_param("~check_rate_hz", 5.0))   # how often to check completion

#         # Pub/Sub/Services
#         self.plan_pub    = rospy.Publisher("baseline/plan_proposal", String, queue_size=10)
#         self.status_pub  = rospy.Publisher("baseline/status", String, queue_size=10)
#         self.approve_sub = rospy.Subscriber("baseline/approve", Bool, self._approve_cb, queue_size=1)
#         self.prop_srv    = rospy.Service("baseline/propose_plan", Trigger, self._propose_example)
#         self.stop_srv    = rospy.Service("baseline/stop_now", Trigger, self._stop_now)

#         # State
#         self.pending_chain = None
#         self.executing = False
#         self.last_wp = None           # (x, y, z)
#         self.curr_pos = None          # (x, y, z)

#         # Odometry sub
#         self.odom_sub = rospy.Subscriber(self.odom_topic, Odometry, self._odom_cb, queue_size=10)

#         # Periodic completion checker
#         self.timer = rospy.Timer(rospy.Duration(1.0 / self.check_rate_hz), self._tick)

#         rospy.loginfo("[baseline] ready: call /baseline/propose_plan then publish /baseline/approve")

#     # ---------- plan/propose/approve ----------
#     def _propose_example(self, _req):
#         chain = {
#             "steps": [
#                 {"tool":"execute_yaml",
#                  "args":{"yaml": self.default_yaml, "interpolator": self.interpolator}}
#             ],
#             "note":"Baseline demo: execute provided YAML"
#         }
#         self.pending_chain = chain
#         self.plan_pub.publish(String(data=json.dumps(chain)))
#         self.status_pub.publish("PLAN_PROPOSED")
#         return TriggerResponse(success=True, message="Plan proposed; approve on /baseline/approve")

#     def _approve_cb(self, msg):
#         if not self.pending_chain:
#             return
#         if msg.data:
#             self.status_pub.publish("APPROVED")
#             yaml_path = self.pending_chain["steps"][-1]["args"]["yaml"]
#             # load final waypoint for completion detection
#             self.last_wp = self._read_last_waypoint(yaml_path)
#             if self.last_wp is None:
#                 rospy.logwarn("[baseline] could not read last waypoint from %s; auto-hold disabled", yaml_path)
#             ok = execute_yaml(yaml_path, self.interpolator, self.init_service)
#             self.executing = bool(ok)
#             self.status_pub.publish("EXECUTING" if ok else "EXECUTION_FAILED")
#             rospy.loginfo("[baseline] execute_yaml: %s", "OK" if ok else "FAILED")
#         else:
#             self.status_pub.publish("REJECTED")
#         self.pending_chain = None

#     # ---------- manual stop ----------
#     def _stop_now(self, _req):
#         ok = hold_vehicle(self.hold_service)
#         if ok:
#             self.executing = False
#             self.status_pub.publish("HELD_MANUAL")
#             return TriggerResponse(success=True, message="Vehicle held (manual stop).")
#         else:
#             return TriggerResponse(success=False, message="Hold service failed.")

#     # ---------- odom & tick ----------
#     def _odom_cb(self, msg):
#         p = msg.pose.pose.position
#         self.curr_pos = (p.x, p.y, p.z)

#     def _tick(self, _evt):
#         # only check while executing and if we know the last waypoint
#         if not self.executing or self.last_wp is None or self.curr_pos is None:
#             return

#         dist_xy = math.hypot(self.curr_pos[0] - self.last_wp[0], self.curr_pos[1] - self.last_wp[1])
#         dz = abs(self.curr_pos[2] - self.last_wp[2])

#         if dist_xy <= self.pos_tolerance and dz <= self.z_tolerance:
#             rospy.loginfo("[baseline] final waypoint reached (dx=%.2f, dz=%.2f). Holding vehicle.", dist_xy, dz)
#             ok = hold_vehicle(self.hold_service)
#             if ok:
#                 self.status_pub.publish("HELD_COMPLETE")
#             else:
#                 self.status_pub.publish("HOLD_FAILED")
#             self.executing = False  # stop checking until next mission

#     # ---------- helpers ----------
#     def _read_last_waypoint(self, yaml_path):
#         try:
#             with open(yaml_path, "r") as f:
#                 data = yaml.safe_load(f)
#             wps = data.get("waypoints", [])
#             if not wps:
#                 return None
#             p = wps[-1].get("point", None)
#             if p and len(p) >= 3:
#                 return (float(p[0]), float(p[1]), float(p[2]))
#         except Exception as e:
#             rospy.logwarn("[baseline] YAML read error: %s", e)
#         return None

# if __name__ == "__main__":
#     BaselineSupervisor()
#     rospy.spin()


# new 

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, yaml, math
import rospy
from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger, TriggerResponse
from nav_msgs.msg import Odometry

from coral_inspection.tools.execute_yaml_tool import execute_yaml
from coral_inspection.tools.hold_tool import hold_vehicle

class BaselineSupervisor:
    """
    Baseline supervisor with:
      - Local propose_plan service (for tests)
      - External plan subscriber (from LLM)
      - Approve -> execute -> auto-hold at final waypoint
      - Manual stop_now service
    """
    def __init__(self):
        rospy.init_node("baseline_supervisor")

        self.vehicle_ns    = rospy.get_param("~vehicle_ns", "/bluerov2")
        self.init_service  = rospy.get_param("~init_service", self.vehicle_ns + "/init_waypoints_from_file")
        self.hold_service  = rospy.get_param("~hold_service", self.vehicle_ns + "/hold_vehicle")
        self.interpolator  = rospy.get_param("~interpolator", "cubic")
        self.default_yaml  = rospy.get_param("~default_yaml", "/home/mbzirc2/catkin_ws/src/coral_inspection/data/example_waypoints.yaml")

        # NEW: external plan topic (from LLM)
        self.external_plan_topic = rospy.get_param("~external_plan_topic", "baseline/plan_proposal_external")

        # Odometry + completion params
        self.odom_topic    = rospy.get_param("~odom_topic", self.vehicle_ns + "/pose_gt")
        self.pos_tolerance = float(rospy.get_param("~pos_tolerance", 2.0))
        self.z_tolerance   = float(rospy.get_param("~z_tolerance", 2.0))
        self.check_rate_hz = float(rospy.get_param("~check_rate_hz", 5.0))

        # Publishers & subscribers
        self.plan_pub    = rospy.Publisher("baseline/plan_proposal", String, queue_size=10)
        self.status_pub  = rospy.Publisher("baseline/status", String, queue_size=10)
        self.approve_sub = rospy.Subscriber("baseline/approve", Bool, self._approve_cb, queue_size=1)

        # Listen for external plan proposals (from LLM)
        self.ext_plan_sub = rospy.Subscriber(self.external_plan_topic, String, self._ext_plan_cb, queue_size=1)

        # Services: local propose & manual stop
        self.prop_srv = rospy.Service("baseline/propose_plan", Trigger, self._propose_example)
        self.stop_srv = rospy.Service("baseline/stop_now", Trigger, self._stop_now)

        # State
        self.pending_chain = None  # plan waiting for approval
        self.executing = False
        self.last_wp = None        # (x, y, z)
        self.curr_pos = None       # (x, y, z)

        # Odometry & timer for completion checks
        self.odom_sub = rospy.Subscriber(self.odom_topic, Odometry, self._odom_cb, queue_size=10)
        self.timer = rospy.Timer(rospy.Duration(1.0 / self.check_rate_hz), self._tick)

        rospy.loginfo("[baseline] ready")
        rospy.loginfo("[baseline] external plans on topic: %s", self.external_plan_topic)

    # ---------- external plan from LLM ----------
    def _ext_plan_cb(self, msg):
        """Handle JSON plan from LLM (on external_plan_topic)."""
        try:
            chain = json.loads(msg.data)
            assert isinstance(chain, dict)
            assert "steps" in chain and isinstance(chain["steps"], list) and len(chain["steps"]) > 0
            self.pending_chain = chain
            # Re-publish to baseline/plan_proposal so RViz / tools can see it
            self.plan_pub.publish(String(data=json.dumps(chain)))
            self.status_pub.publish("PLAN_PROPOSED")
            rospy.loginfo("[baseline] external plan received; waiting for /baseline/approve")
        except Exception as e:
            rospy.logwarn("[baseline] invalid external plan: %s", e)

    # ---------- local example plan (for testing without LLM) ----------
    def _propose_example(self, _req):
        chain = {
            "steps": [
                {"tool":"execute_yaml",
                 "args":{"yaml": self.default_yaml, "interpolator": self.interpolator}}
            ],
            "note":"Baseline demo: execute provided YAML"
        }
        self.pending_chain = chain
        self.plan_pub.publish(String(data=json.dumps(chain)))
        self.status_pub.publish("PLAN_PROPOSED")
        return TriggerResponse(success=True, message="Plan proposed; approve on /baseline/approve")

    # ---------- approval & execution ----------
    def _approve_cb(self, msg):
        if not self.pending_chain:
            return
        if msg.data:
            self.status_pub.publish("APPROVED")
            # assume last step is execute_yaml
            yaml_path = self.pending_chain["steps"][-1]["args"]["yaml"]
            self.last_wp = self._read_last_waypoint(yaml_path)
            if self.last_wp is None:
                rospy.logwarn("[baseline] could not read last waypoint from %s; auto-hold disabled", yaml_path)
            ok = execute_yaml(yaml_path, self.interpolator, self.init_service)
            self.executing = bool(ok)
            self.status_pub.publish("EXECUTING" if ok else "EXECUTION_FAILED")
            rospy.loginfo("[baseline] execute_yaml: %s", "OK" if ok else "FAILED")
        else:
            self.status_pub.publish("REJECTED")
        self.pending_chain = None

    # ---------- manual stop ----------
    def _stop_now(self, _req):
        ok = hold_vehicle(self.hold_service)
        if ok:
            self.executing = False
            self.status_pub.publish("HELD_MANUAL")
            return TriggerResponse(success=True, message="Vehicle held (manual stop).")
        else:
            return TriggerResponse(success=False, message="Hold service failed.")

    # ---------- odometry & completion ----------
    def _odom_cb(self, msg):
        p = msg.pose.pose.position
        self.curr_pos = (p.x, p.y, p.z)

    def _tick(self, _evt):
        if not self.executing or self.last_wp is None or self.curr_pos is None:
            return
        dist_xy = math.hypot(self.curr_pos[0] - self.last_wp[0],
                             self.curr_pos[1] - self.last_wp[1])
        dz = abs(self.curr_pos[2] - self.last_wp[2])
        if dist_xy <= self.pos_tolerance and dz <= self.z_tolerance:
            rospy.loginfo("[baseline] final waypoint reached (dx=%.2f, dz=%.2f). Holding vehicle.", dist_xy, dz)
            ok = hold_vehicle(self.hold_service)
            if ok:
                self.status_pub.publish("HELD_COMPLETE")
            else:
                self.status_pub.publish("HOLD_FAILED")
            self.executing = False

    def _read_last_waypoint(self, yaml_path):
        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
            wps = data.get("waypoints", [])
            if not wps:
                return None
            p = wps[-1].get("point", None)
            if p and len(p) >= 3:
                return (float(p[0]), float(p[1]), float(p[2]))
        except Exception as e:
            rospy.logwarn("[baseline] YAML read error: %s", e)
        return None

if __name__ == "__main__":
    BaselineSupervisor()
    rospy.spin()
