#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
from uuv_control_msgs.srv import InitHelicalTrajectory, InitHelicalTrajectoryRequest
from std_msgs.msg import Time as TimeMsg
from geometry_msgs.msg import Point

def main():
    rospy.init_node("test_start_helical")

    service_name = "/bluerov2/start_helical_trajectory"

    # === EDIT PARAMETERS IF YOU WANT ===
    radius = 6.0
    center_x = 0.0
    center_y = 0.0
    center_z = -60.0
    is_clockwise = True
    angle_offset = 0.0
    n_points = 100
    heading_offset = 0.0
    max_forward_speed = 0.3
    duration = 200.0  # seconds (approx)
    n_turns = 3.0
    delta_z = 10.0    # vertical change (e.g., from -60 to -50)

    rospy.loginfo("Waiting for service %s", service_name)
    rospy.wait_for_service(service_name)
    client = rospy.ServiceProxy(service_name, InitHelicalTrajectory)

    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitHelicalTrajectoryRequest()
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
    req.n_turns = n_turns
    req.delta_z = delta_z

    rospy.loginfo("Calling %s (center=(%.1f, %.1f, %.1f), radius=%.1f, n_turns=%.1f, dz=%.1f)",
                  service_name, center_x, center_y, center_z, radius, n_turns, delta_z)
    try:
        resp = client(req)
        rospy.loginfo("Service returned success=%s", resp.success)
    except Exception as e:
        rospy.logerr("Service call failed: %s", e)

if __name__ == "__main__":
    main()
