# src/coral_inspection/tools/actions/emergency_stop.py
# -*- coding: utf-8 -*-

import rospy


def do_emergency_stop(ctx, args):
    """
    emergency_stop: immediate stop-and-hold of the vehicle.

    - Calls ctx.do_hold({}) to engage hold_vehicle.
    - The executor should treat this as a hard stop and stop executing
      any remaining steps in the plan.
    """
    rospy.logwarn("[actions] EMERGENCY STOP requested!")
    ok = ctx.do_hold({})
    if ok:
        rospy.logwarn("[actions] EMERGENCY STOP: vehicle held in place")
    else:
        rospy.logerr("[actions] EMERGENCY STOP: hold failed")
    return ok

