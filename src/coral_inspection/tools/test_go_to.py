#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
from uuv_control_msgs.srv import GoTo, GoToRequest
from uuv_control_msgs.msg import Waypoint
from std_msgs.msg import Header
from geometry_msgs.msg import Point

def main():
    rospy.init_node("test_go_to")

    service_name = "/bluerov2/go_to"

    # === EDIT THESE TARGET VALUES IF YOU WANT ===
    target_x = 0.0
    target_y = 0.0
    target_z = 0.0
    wp_speed = 0.4
    wp_heading_offset = 0.0
    wp_use_fixed_heading = False
    wp_radius_of_acceptance = 1.0

    req_max_speed = 0.4
    interpolator = "cubic"  # one of: lipb, cubic, dubins, linear

    rospy.loginfo("Waiting for service %s", service_name)
    rospy.wait_for_service(service_name)
    client = rospy.ServiceProxy(service_name, GoTo)

    # Build waypoint
    wp = Waypoint()
    wp.header = Header()
    wp.header.stamp = rospy.Time.now()
    wp.header.frame_id = "world"

    wp.point = Point(x=target_x, y=target_y, z=target_z)
    wp.max_forward_speed = wp_speed
    wp.heading_offset = wp_heading_offset
    wp.use_fixed_heading = wp_use_fixed_heading
    wp.radius_of_acceptance = wp_radius_of_acceptance

    # Build request
    req = GoToRequest()
    req.waypoint = wp
    req.max_forward_speed = req_max_speed
    req.interpolator = interpolator

    rospy.loginfo("Calling %s to go to (%.2f, %.2f, %.2f)",
                  service_name, target_x, target_y, target_z)
    try:
        resp = client(req)
        rospy.loginfo("Service returned success=%s", resp.success)
    except Exception as e:
        rospy.logerr("Service call failed: %s", e)

if __name__ == "__main__":
    main()
