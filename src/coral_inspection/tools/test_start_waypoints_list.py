#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
from uuv_control_msgs.srv import InitWaypointSet, InitWaypointSetRequest
from uuv_control_msgs.msg import Waypoint
from std_msgs.msg import Time as TimeMsg, Header, String
from geometry_msgs.msg import Point

def main():
    rospy.init_node("test_start_waypoint_list")

    service_name = "/bluerov2/start_waypoint_list"

    # === EDIT THESE WAYPOINTS IF YOU WANT ===
    wps_coords = [
        (0.0, 0.0, -60.0),
        (10.0, 0.0, -60.0),
        (10.0, 10.0, -60.0),
        (0.0, 10.0, -60.0)
    ]
    wp_speed = 0.4
    heading_offset = 0.0
    use_fixed_heading = False
    radius_of_acceptance = 1.0

    global_max_forward_speed = 0.4
    global_heading_offset = 0.0
    interpolator_str = "cubic"

    rospy.loginfo("Waiting for service %s", service_name)
    rospy.wait_for_service(service_name)
    client = rospy.ServiceProxy(service_name, InitWaypointSet)

    # start_time: 0, start_now: True
    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitWaypointSetRequest()
    req.start_time = start_t
    req.start_now = True

    # Build waypoint list
    for (x, y, z) in wps_coords:
        wp = Waypoint()
        wp.header = Header()
        wp.header.stamp = rospy.Time.now()
        wp.header.frame_id = "world"
        wp.point = Point(x=x, y=y, z=z)
        wp.max_forward_speed = wp_speed
        wp.heading_offset = heading_offset
        wp.use_fixed_heading = use_fixed_heading
        wp.radius_of_acceptance = radius_of_acceptance
        req.waypoints.append(wp)

    req.max_forward_speed = global_max_forward_speed
    req.heading_offset = global_heading_offset
    req.interpolator.data = interpolator_str

    rospy.loginfo("Calling %s with %d waypoints", service_name, len(req.waypoints))
    try:
        resp = client(req)
        rospy.loginfo("Service returned success=%s", resp.success)
    except Exception as e:
        rospy.logerr("Service call failed: %s", e)

if __name__ == "__main__":
    main()
