#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rospy
import json
from std_msgs.msg import String
from std_srvs.srv import Trigger

def main():
    rospy.init_node("send_test_plan")

    plan_pub = rospy.Publisher("/coral_captain/plan", String, queue_size=1, latch=True)

    rospy.sleep(1.0)  # let publisher connect

    # ---- SIMPLE PLAN: go_to then hold ----
    plan = {
        "steps": [
            {
                "action": "go_to",
                "args": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "max_forward_speed": 0.4,
                    "heading_offset": 0.0,
                    "use_fixed_heading": False,
                    "radius_of_acceptance": 1.0,
                    "interpolator": "cubic"
                }
            },
            {
                "action": "hold",
                "args": {}
            }
        ],
        "note": "Test go_to then hold"
    }

    msg = String()
    msg.data = json.dumps(plan)
    rospy.loginfo("[send_test_plan] Publishing plan: %s", msg.data)
    plan_pub.publish(msg)

    rospy.sleep(1.0)

    # ---- Call the executor service ----
    rospy.wait_for_service("/coral_action_executor/execute_plan")
    exec_srv = rospy.ServiceProxy("/coral_action_executor/execute_plan", Trigger)

    rospy.loginfo("[send_test_plan] Calling execute_plan...")
    resp = exec_srv()
    rospy.loginfo("[send_test_plan] execute_plan -> success=%s, message=%s",
                  resp.success, resp.message)

if __name__ == "__main__":
    main()
