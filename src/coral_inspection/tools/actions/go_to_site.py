# src/coral_inspection/tools/actions/go_to_site.py
# -*- coding: utf-8 -*-

import rospy


def do_go_to_site(ctx, args):
    """
    go_to_site: resolve a named site/footprint from the YAML, then call go_to
    on its center (plus optional offset or depth override).
    """
    site_name = args.get("site", None)
    if not site_name:
        rospy.logerr("[actions] go_to_site: 'site' argument is required")
        return False

    center = ctx._get_site_center(site_name)
    if center is None:
        rospy.logerr("[actions] go_to_site: unknown site '%s'", site_name)
        return False

    cx, cy, cz = center

    # Optional depth override
    if "z" in args:
        cz = float(args["z"])

    # Optional offset
    offset = args.get("offset", None)
    if offset and len(offset) >= 3:
        cx += float(offset[0])
        cy += float(offset[1])
        cz += float(offset[2])

    go_args = dict(args)  # clone
    go_args["x"] = cx
    go_args["y"] = cy
    go_args["z"] = cz

    rospy.loginfo("[actions] go_to_site '%s' -> (%.2f, %.2f, %.2f)",
                  site_name, cx, cy, cz)
    return ctx.do_go_to(go_args)

