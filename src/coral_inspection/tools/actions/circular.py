# src/coral_inspection/tools/actions/circular.py
# -*- coding: utf-8 -*-

import rospy
from std_msgs.msg import Time as TimeMsg
from geometry_msgs.msg import Point
from uuv_control_msgs.srv import InitCircularTrajectory, InitCircularTrajectoryRequest


def do_circular(ctx, args):
    """circular: call /start_circular_trajectory, then sleep for duration (if > 0)."""
    rospy.wait_for_service(ctx.srv_circular)
    client = rospy.ServiceProxy(ctx.srv_circular, InitCircularTrajectory)

    center = args.get("center", [0.0, 0.0, -30.0])
    cx = float(center[0])
    cy = float(center[1])
    cz = float(center[2])

    radius = float(args.get("radius", 8.0))
    is_clockwise = bool(args.get("is_clockwise", True))
    angle_offset = float(args.get("angle_offset", 0.0))
    n_points = int(args.get("n_points", 50))
    heading_offset = float(args.get("heading_offset", 0.0))
    max_forward_speed = float(args.get("max_forward_speed", 0.3))
    duration = float(args.get("duration", 0.0))
    start_now = bool(args.get("start_now", True))

    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitCircularTrajectoryRequest()
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

    rospy.loginfo("[actions] circular -> center=(%.1f, %.1f, %.1f), r=%.1f",
                  cx, cy, cz, radius)
    resp = client(req)
    rospy.loginfo("[actions] circular success=%s", resp.success)

    if not resp.success:
        return False

    if ctx.wait_for_motion and duration > 0.0:
        rospy.loginfo("[actions] circular: sleeping for duration=%.1f s", duration)
        rospy.sleep(duration)
    else:
        rospy.loginfo("[actions] circular: no duration or waiting disabled, not blocking")

    return True

