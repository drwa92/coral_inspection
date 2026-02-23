#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
from uuv_control_msgs.srv import InitCircularTrajectory, InitCircularTrajectoryRequest
from std_msgs.msg import Time as TimeMsg
from geometry_msgs.msg import Point

def main():
    rospy.init_node("test_start_circular")

    service_name = "/bluerov2/start_circular_trajectory"

    # === EDIT PARAMETERS IF YOU WANT ===
    radius = 8.0
    center_x = 0.0
    center_y = 0.0
    center_z = -60.0
    is_clockwise = True
    angle_offset = 0.0
    n_points = 50
    heading_offset = 0.0
    max_forward_speed = 0.3
    duration = 0.0  # 0 means use speed to determine time (in uuv)

    rospy.loginfo("Waiting for service %s", service_name)
    rospy.wait_for_service(service_name)
    client = rospy.ServiceProxy(service_name, InitCircularTrajectory)

    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitCircularTrajectoryRequest()
    req.start_time = start_t
    req.start_now = True
    req.radius = radius
    req.center = Point(x=center_x, y=center_y, z=center_z)
    req.is_clockwise = is_clockwise
    req.angle_offset = angle_offset
    req.n_points = n_points
    req.heading_offset = heading_offset
    req.max_forward_speed = max_forward_speed
    req.duration = duration

    rospy.loginfo("Calling %s (center=(%.1f, %.1f, %.1f), radius=%.1f)",
                  service_name, center_x, center_y, center_z, radius)
    try:
        resp = client(req)
        rospy.loginfo("Service returned success=%s", resp.success)
    except Exception as e:
        rospy.logerr("Service call failed: %s", e)

if __name__ == "__main__":
    main()
