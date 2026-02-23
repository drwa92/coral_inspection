import rospy
from uuv_control_msgs.srv import Hold
rospy.init_node("test_hold", anonymous=True)
rospy.wait_for_service("/bluerov2/hold_vehicle")
hold = rospy.ServiceProxy("/bluerov2/hold_vehicle", Hold)
resp = hold()   # <-- no arguments
print(resp.success)
