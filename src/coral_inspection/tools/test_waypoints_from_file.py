#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
from uuv_control_msgs.srv import InitWaypointsFromFile, InitWaypointsFromFileRequest
from std_msgs.msg import Time as TimeMsg, String as StringMsg

def main():
    rospy.init_node("test_init_waypoints_from_file")

    service_name = "/bluerov2/init_waypoints_from_file"

    # === EDIT THIS PATH TO YOUR YAML ===
    yaml_file = "/home/mbzirc2/catkin_ws/src/coral_inspection/data/example_waypoints.yaml"
    interpolator_str = "cubic"

    rospy.loginfo("Waiting for service %s", service_name)
    rospy.wait_for_service(service_name)
    client = rospy.ServiceProxy(service_name, InitWaypointsFromFile)

    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitWaypointsFromFileRequest()
    req.start_time = start_t
    req.start_now = True
    req.filename = StringMsg(data=yaml_file)
    req.interpolator = StringMsg(data=interpolator_str)

    rospy.loginfo("Calling %s with file %s", service_name, yaml_file)
    try:
        resp = client(req)
        rospy.loginfo("Service returned success=%s", resp.success)
    except Exception as e:
        rospy.logerr("Service call failed: %s", e)

if __name__ == "__main__":
    main()
