# src/coral_inspection/tools/actions/hold.py
# -*- coding: utf-8 -*-

import rospy
from uuv_control_msgs.srv import Hold


def do_hold(ctx, args):
    """hold: call /hold_vehicle."""
    rospy.wait_for_service(ctx.srv_hold)
    client = rospy.ServiceProxy(ctx.srv_hold, Hold)
    rospy.loginfo("[actions] hold_vehicle")
    resp = client()
    rospy.loginfo("[actions] hold success=%s", resp.success)
    return resp.success

