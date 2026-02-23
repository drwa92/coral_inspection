# src/coral_inspection/tools/actions/waypoint_list.py
# -*- coding: utf-8 -*-

import rospy
from std_msgs.msg import Time as TimeMsg, String as StringMsg, Header
from geometry_msgs.msg import Point
from uuv_control_msgs.srv import InitWaypointSet, InitWaypointSetRequest
from uuv_control_msgs.msg import Waypoint


def do_waypoint_list(ctx, args):
    """waypoint_list: call /start_waypoint_list, then wait for the last waypoint."""
    rospy.wait_for_service(ctx.srv_wp_list)
    client = rospy.ServiceProxy(ctx.srv_wp_list, InitWaypointSet)

    waypoints = args.get("waypoints", [])
    if not waypoints:
        rospy.logerr("[actions] waypoint_list: no waypoints provided")
        return False

    global_max_speed = float(args.get("global_max_forward_speed", 0.4))
    global_heading_offset = float(args.get("heading_offset", 0.0))
    interpolator_str = args.get("interpolator", "cubic")
    start_now = bool(args.get("start_now", True))

    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitWaypointSetRequest()
    req.start_time = start_t
    req.start_now = start_now

    last_x = 0.0
    last_y = 0.0
    last_z = -40.0
    last_radius = 1.0

    for wp_dict in waypoints:
        x = float(wp_dict.get("x", 0.0))
        y = float(wp_dict.get("y", 0.0))
        z = float(wp_dict.get("z", -40.0))
        wp_speed = float(wp_dict.get("max_forward_speed", global_max_speed))
        heading_offset = float(wp_dict.get("heading_offset", 0.0))
        use_fixed_heading = bool(wp_dict.get("use_fixed_heading", False))
        radius = float(wp_dict.get("radius_of_acceptance", 1.0))

        wp = Waypoint()
        wp.header = Header()
        wp.header.stamp = rospy.Time.now()
        wp.header.frame_id = "world"
        wp.point = Point(x=x, y=y, z=z)
        wp.max_forward_speed = wp_speed
        wp.heading_offset = heading_offset
        wp.use_fixed_heading = use_fixed_heading
        wp.radius_of_acceptance = radius

        req.waypoints.append(wp)

        last_x, last_y, last_z = x, y, z
        last_radius = radius

    req.max_forward_speed = global_max_speed
    req.heading_offset = global_heading_offset
    req.interpolator = StringMsg(data=interpolator_str)

    rospy.loginfo("[actions] waypoint_list -> %d waypoints", len(req.waypoints))
    resp = client(req)
    rospy.loginfo("[actions] waypoint_list success=%s", resp.success)

    if not resp.success:
        return False

    return ctx._wait_until_near(
        target=(last_x, last_y, last_z),
        radius=last_radius,
        timeout_sec=600.0,
        label="waypoint_list (final wp)"
    )

