# src/coral_inspection/tools/actions/survey_rectangle.py
# -*- coding: utf-8 -*-

import rospy


def do_survey_rectangle(ctx, args):
    """
    survey_rectangle: generate a lawnmower pattern for a rectangular/square
    coral footprint and execute it as a waypoint_list.

    Args:
      footprint: name of footprint in YAML (e.g. 'coral_bed_A', 'coral_bed_crown_D')
      OR site: any alias that resolves to that footprint (e.g. 'A', 'D').
      Optional:
        stripe_spacing, turn_buffer, max_forward_speed, radius_of_acceptance,
        z (depth override), interpolator, start_now, heading_offset
    """
    site_name = args.get("footprint", None) or args.get("site", None)
    if not site_name:
        rospy.logerr("[actions] survey_rectangle: 'footprint' or 'site' argument is required")
        return False

    site_info = ctx._get_site_info(site_name)
    if site_info is None:
        rospy.logerr("[actions] survey_rectangle: unknown site/footprint '%s'", site_name)
        return False

    wps = ctx._generate_lawnmower_waypoints(site_info, args)
    if not wps:
        rospy.logerr("[actions] survey_rectangle: no waypoints generated")
        return False

    wl_args = {
        "waypoints": wps,
        "global_max_forward_speed": float(args.get(
            "max_forward_speed", ctx.survey_defaults.get("speed_mps", 0.5))),
        "heading_offset": float(args.get("heading_offset", 0.0)),
        "interpolator": args.get("interpolator", "cubic"),
        "start_now": bool(args.get("start_now", True))
    }

    rospy.loginfo("[actions] survey_rectangle -> site/footprint '%s'", site_name)
    return ctx.do_waypoint_list(wl_args)

