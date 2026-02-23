# src/coral_inspection/tools/actions/waypoint_file.py
# -*- coding: utf-8 -*-

import rospy
import yaml
from std_msgs.msg import Time as TimeMsg, String as StringMsg
from uuv_control_msgs.srv import InitWaypointsFromFile, InitWaypointsFromFileRequest


def do_waypoint_file(ctx, args):
    """waypoint_file: call /init_waypoints_from_file, then wait on last wp in YAML (if possible)."""
    rospy.wait_for_service(ctx.srv_wp_file)
    client = rospy.ServiceProxy(ctx.srv_wp_file, InitWaypointsFromFile)

    yaml_file = args.get("file", "")
    if not yaml_file:
        rospy.logerr("[actions] waypoint_file: 'file' argument is required")
        return False

    interpolator_str = args.get("interpolator", "cubic")
    start_now = bool(args.get("start_now", True))

    start_t = TimeMsg()
    start_t.data = rospy.Time(0)

    req = InitWaypointsFromFileRequest()
    req.start_time = start_t
    req.start_now = start_now
    req.filename = StringMsg(data=yaml_file)
    req.interpolator = StringMsg(data=interpolator_str)

    rospy.loginfo("[actions] waypoint_file -> %s", yaml_file)
    resp = client(req)
    rospy.loginfo("[actions] waypoint_file success=%s", resp.success)

    if not resp.success:
        return False

    if not ctx.wait_for_motion:
        return True

    # Parse last waypoint from YAML
    try:
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        rospy.logwarn("[actions] waypoint_file: cannot parse YAML for completion: %s", e)
        return True

    wps = data.get("waypoints", [])
    if not wps:
        rospy.logwarn("[actions] waypoint_file: no waypoints in YAML, not waiting")
        return True

    last_wp = wps[-1]
    point = last_wp.get("point", None)
    if not point or len(point) < 3:
        rospy.logwarn("[actions] waypoint_file: invalid last waypoint 'point', not waiting")
        return True

    last_x = float(point[0])
    last_y = float(point[1])
    last_z = float(point[2])
    last_radius = float(last_wp.get("radius_of_acceptance", 1.0))

    return ctx._wait_until_near(
        target=(last_x, last_y, last_z),
        radius=last_radius,
        timeout_sec=600.0,
        label="waypoint_file (final wp)"
    )

