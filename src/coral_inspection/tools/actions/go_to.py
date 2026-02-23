# src/coral_inspection/tools/actions/go_to.py
# -*- coding: utf-8 -*-

import rospy
from std_msgs.msg import Header
from geometry_msgs.msg import Point
from uuv_control_msgs.srv import GoTo, GoToRequest
from uuv_control_msgs.msg import Waypoint


def do_go_to(ctx, args):
    """go_to: call /go_to, then wait until target reached."""
    rospy.wait_for_service(ctx.srv_go_to)
    client = rospy.ServiceProxy(ctx.srv_go_to, GoTo)

    x = float(args.get("x", 0.0))
    y = float(args.get("y", 0.0))
    z = float(args.get("z", 0.0))

    wp_max_speed = float(args.get("max_forward_speed", 0.4))
    heading_offset = float(args.get("heading_offset", 0.0))
    use_fixed_heading = bool(args.get("use_fixed_heading", False))
    radius_of_acceptance = float(args.get("radius_of_acceptance", 1.0))

    req_max_speed = float(args.get("max_forward_speed", 0.4))
    interpolator = args.get("interpolator", "cubic")

    wp = Waypoint()
    wp.header = Header()
    wp.header.stamp = rospy.Time.now()
    wp.header.frame_id = "world"
    wp.point = Point(x=x, y=y, z=z)
    wp.max_forward_speed = wp_max_speed
    wp.heading_offset = heading_offset
    wp.use_fixed_heading = use_fixed_heading
    wp.radius_of_acceptance = radius_of_acceptance

    req = GoToRequest()
    req.waypoint = wp    # type: ignore[attr-defined]
    req.max_forward_speed = req_max_speed
    req.interpolator = interpolator

    rospy.loginfo("[actions] go_to -> (%.2f, %.2f, %.2f)", x, y, z)
    resp = client(req)
    rospy.loginfo("[actions] go_to service success=%s", resp.success)

    if not resp.success:
        return False

    return ctx._wait_until_near(
        target=(x, y, z),
        radius=radius_of_acceptance,
        timeout_sec=300.0,
        label="go_to"
    )

