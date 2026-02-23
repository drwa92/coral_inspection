#!/usr/bin/env python

import rospy
from uuv_control_msgs.srv import Hold

def hold_vehicle(service_name):
    """
    Call the uuv_control_msgs/Hold service (no request fields).
    Returns True on success, False otherwise.
    """
    try:
        rospy.wait_for_service(service_name, timeout=3.0)
        proxy = rospy.ServiceProxy(service_name, Hold)
        resp = proxy()
        return bool(getattr(resp, "success", False))
    except Exception as e:
        rospy.logwarn("[hold_vehicle] %s", e)
        return False
