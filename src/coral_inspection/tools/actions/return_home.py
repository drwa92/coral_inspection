# src/coral_inspection/tools/actions/return_home.py
# -*- coding: utf-8 -*-

import rospy


def do_return_home(ctx, args):
    """
    return_home: navigate to a designated 'home' site and hold there.

    Args:
      - site (optional): which site alias to treat as home (e.g. "A", "site_A").
                         Default: "A".

    Behavior:
      - Uses ctx._get_site_info(site_name) for coordinates.
      - Falls back to (0,0,-60) if site not found.
      - Calls ctx.do_go_to(...) then ctx.do_hold({}).
    """
    site_name = args.get("site", "Home")

    site_info = ctx._get_site_info(site_name)
    if site_info is None:
        rospy.logwarn("[actions] return_home: site '%s' not found, using (0,0,-0)",
                      site_name)
        x, y, z = 0.0, 0.0, -0.0
    else:
        (x, y, z) = site_info.get("center", (0.0, 0.0, -0.0))

    rospy.loginfo("[actions] return_home: going to '%s' -> (%.2f, %.2f, %.2f)",
                  site_name, x, y, z)
    ok = ctx.do_go_to({"x": x, "y": y, "z": z})
    if not ok:
        rospy.logerr("[actions] return_home: go_to failed")
        return False

    rospy.loginfo("[actions] return_home: holding at home position")
    ctx.do_hold({})
    return True

