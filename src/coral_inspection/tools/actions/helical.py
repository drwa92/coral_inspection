# src/coral_inspection/tools/actions/helical.py
# -*- coding: utf-8 -*-

import rospy
from std_msgs.msg import Time as TimeMsg
from geometry_msgs.msg import Point
from uuv_control_msgs.srv import InitHelicalTrajectory, InitHelicalTrajectoryRequest


def do_helical(ctx, args):
    """helical: call /start_helical_trajectory, then sleep for duration (if > 0)."""
    rospy.wait_for_service(ctx.srv_helical)
    client = rospy.ServiceProxy(ctx.srv_helical, InitHelicalTrajectory)

    center = args.get("center", [0.0, 0.0, -30.0])
    cx = float(center[0])
    cy = float(center[1])
    cz = float(center[2])

    radius = float(args.get("radius", 6.0))
    is_clockwise = bool(args.get("is_clockwise", True))
    angle_offset = float(args.get("angle_offset", 0.0))
    n_points = int(args.get("n_points", 100))
    heading_offset = float(args.get("heading_offset", 0.0))
    max_forward_speed = float(args.get("max_forward_speed", 0.3))
    duration = float(args.get("duration", 200.0))
    n_turns = float(args.get("n_turns", 3.0))
    delta_z = float(args.get("delta_z", 10.0))
    start_now = bool(args.get("start_now", True))

    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitHelicalTrajectoryRequest()
    req.start_time = start_t
    req.start_now = start_now
    req.radius = radius
    req.center = Point(x=cx, y=cy, z=cz)
    req.is_clockwise = is_clockwise
    req.angle_offset = angle_offset
    req.n_points = n_points
    req.heading_offset = heading_offset
    req.max_forward_speed = max_forward_speed
    req.duration = duration
    req.n_turns = n_turns
    req.delta_z = delta_z

    rospy.loginfo("[actions] helical -> center=(%.1f, %.1f, %.1f), r=%.1f, turns=%.1f, dz=%.1f",
                  cx, cy, cz, radius, n_turns, delta_z)
    resp = client(req)
    rospy.loginfo("[actions] helical success=%s", resp.success)

    if not resp.success:
        return False

    if ctx.wait_for_motion and duration > 0.0:
        rospy.loginfo("[actions] helical: sleeping for duration=%.1f s", duration)
        rospy.sleep(duration)
    else:
        rospy.loginfo("[actions] helical: no duration or waiting disabled, not blocking")

    return True

