#!/usr/bin/env python
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import Time as TimeMsg
from uuv_control_msgs.srv import InitWaypointsFromFile, InitWaypointsFromFileRequest

def execute_yaml(yaml_path, interpolator, service_name):
    """
    Call <vehicle_ns>/init_waypoints_from_file. Handles both message layouts:
      A) filename: std_msgs/String, interpolator: std_msgs/String, start_time: std_msgs/Time
      B) file_name: string,          interpolator: string,          start_time: ros::Time
    """
    try:
        rospy.wait_for_service(service_name, timeout=5.0)
        proxy = rospy.ServiceProxy(service_name, InitWaypointsFromFile)
        req = InitWaypointsFromFileRequest()

        try:
            # Newer layout (std_msgs/String + std_msgs/Time)
            req.filename.data = yaml_path
            req.interpolator.data = interpolator
            t = TimeMsg()
            t.data = rospy.Time(0)
            req.start_time = t
            req.start_now = True
        except Exception:
            # Older layout (plain fields)
            req.file_name = yaml_path
            req.interpolator = interpolator
            req.start_time = rospy.Time(0)
            req.start_now = True

        resp = proxy(req)
        return bool(getattr(resp, "success", False))
    except Exception as e:
        rospy.logerr("[execute_yaml] %s", e)
        return False
