# src/coral_inspection/tools/actions/hover_observe.py
# -*- coding: utf-8 -*-

import rospy


def do_hover_observe(ctx, args):
    """
    hover_observe: move (optionally) to a target, then hold and observe in place.

    Modes:
      1) If 'site' or 'footprint' is given:
           - go_to_site (using its center, optionally with custom z)
           - then hold for 'duration' seconds (if > 0)

      2) If explicit x,y,z given:
           - go_to(x,y,z)
           - then hold for 'duration' seconds

      3) If no target is given:
           - just hold at current pose and wait 'duration' seconds.

    Args:
      - site or footprint (optional)
      - x, y, z (optional)
      - duration (seconds, default 30)
    """
    duration = float(args.get("duration", 30.0))
    site_name = args.get("site", None) or args.get("footprint", None)

    # 1) If site specified, move to site center
    if site_name is not None:
        site_info = ctx._get_site_info(site_name)
        if site_info is None:
            rospy.logerr("[actions] hover_observe: unknown site '%s'", site_name)
            return False

        (cx, cy, cz) = site_info.get("center", (0.0, 0.0, -60.0))

        # Allow explicit z override in args
        if "z" in args:
            cz = float(args["z"])

        go_args = {"x": cx, "y": cy, "z": cz}
        rospy.loginfo("[actions] hover_observe: go_to_site '%s' -> (%.2f, %.2f, %.2f)",
                      site_name, cx, cy, cz)
        ok = ctx.do_go_to(go_args)
        if not ok:
            rospy.logerr("[actions] hover_observe: go_to_site failed")
            return False

        rospy.loginfo("[actions] hover_observe: holding at site '%s'", site_name)
        ctx.do_hold({})

    # 2) If explicit coordinate given without site
    elif all(k in args for k in ["x", "y", "z"]):
        x = float(args["x"])
        y = float(args["y"])
        z = float(args["z"])
        go_args = {"x": x, "y": y, "z": z}
        rospy.loginfo("[actions] hover_observe: go_to (%.2f, %.2f, %.2f)", x, y, z)
        ok = ctx.do_go_to(go_args)
        if not ok:
            rospy.logerr("[actions] hover_observe: go_to failed")
            return False

        rospy.loginfo("[actions] hover_observe: holding at (%.2f, %.2f, %.2f)", x, y, z)
        ctx.do_hold({})

    # 3) No target: just hold where we are
    else:
        rospy.loginfo("[actions] hover_observe: no target given, holding current pose")
        ctx.do_hold({})

    # Observe duration
    if duration > 0.0:
        rospy.loginfo("[actions] hover_observe: observing for %.1f s", duration)
        rospy.sleep(duration)

    rospy.loginfo("[actions] hover_observe: done")
    return True

