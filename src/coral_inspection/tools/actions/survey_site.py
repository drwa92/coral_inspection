# src/coral_inspection/tools/actions/survey_site.py
# -*- coding: utf-8 -*-

import rospy


def do_survey_site(ctx, args):
    """
    survey_site: high-level semantic survey action.

    It chooses a pattern based on the site's footprint type:
      - rectangle / square / ellipse -> lawnmower pattern (survey_rectangle)
      - circle                       -> circular orbit (circular)

    Args (JSON from LLM):
      - site:       alias like "A", "B", "site_A", or footprint name
                    such as "coral_bed_A"
        OR
      - footprint:  explicit footprint name from YAML.

    Optional (forwarded as appropriate):
      For lawnmower (rectangle/square/ellipse):
        - stripe_spacing
        - turn_buffer
        - max_forward_speed
        - radius_of_acceptance
        - z
        - interpolator
        - start_now
        - heading_offset

      For circular footprints:
        - orbit_radius        (preferred; defaults from diameter + padding)
        - duration
        - is_clockwise
        - n_points
        - max_forward_speed
        - heading_offset
        - angle_offset
        - start_now

    Examples:
      { "action": "survey_site", "args": { "site": "A" } }
      { "action": "survey_site", "args": { "footprint": "coral_bed_circle_B",
                                           "duration": 120.0 } }
    """
    # Resolve site/footprint name
    site_name = args.get("site", None) or args.get("footprint", None)
    if not site_name:
        rospy.logerr("[actions] survey_site: 'site' or 'footprint' argument is required")
        return False

    # Use ActionTools helper to get site info
    site_info = ctx._get_site_info(site_name)
    if site_info is None:
        rospy.logerr("[actions] survey_site: unknown site/footprint '%s'", site_name)
        return False

    fp_type = site_info.get("footprint_type", "")
    rospy.loginfo("[actions] survey_site '%s' -> footprint_type=%s",
                  site_name, fp_type)

    # RECT / SQUARE / ELLIPSE -> use lawnmower survey (survey_rectangle)
    if fp_type in ("rectangle", "square", "ellipse"):
        # Forward args, but ensure we tell survey_rectangle which footprint to use
        sr_args = dict(args)
        if "footprint" not in sr_args:
            sr_args["footprint"] = site_name

        rospy.loginfo("[actions] survey_site '%s' -> survey_rectangle", site_name)
        return ctx.do_survey_rectangle(sr_args)

    # CIRCLE -> use circular orbit
    if fp_type == "circle":
        raw = site_info.get("raw", {})
        profile = site_info.get("survey_profile", {}) or {}

        # Diameter from YAML footprint
        diameter = float(raw.get("diameter", 10.0))
        base_radius = diameter / 2.0

        # Orbit padding from profile (ecology-aware) or default 2.0 m
        orbit_padding = float(profile.get("orbit_padding", 2.0))

        # Allow explicit override from args
        radius = float(args.get("orbit_radius", base_radius + orbit_padding))

        cx, cy, cz = site_info.get("center", (0.0, 0.0, -60.0))

        # Use profile-aware defaults if present, otherwise fallback
        def choose(name, arg_key=None, default=None):
            if arg_key is None:
                arg_key = name
            if arg_key in args:
                return float(args[arg_key])
            if name in profile:
                return float(profile[name])
            return float(default) if default is not None else None

        max_speed = choose("speed_mps", "max_forward_speed", 0.3)
        duration  = choose("duration", "duration", 180.0)

        circ_args = {
            "center": [cx, cy, cz],
            "radius": radius,
            "is_clockwise": bool(args.get("is_clockwise", True)),
            "angle_offset": float(args.get("angle_offset", 0.0)),
            "n_points": int(args.get("n_points", 80)),
            "heading_offset": float(args.get("heading_offset", 0.0)),
            "max_forward_speed": max_speed,
            "duration": duration,
            "start_now": bool(args.get("start_now", True))
        }

        rospy.loginfo("[actions] survey_site '%s' -> circular, r=%.2f, duration=%.1f",
                      site_name, circ_args["radius"], circ_args["duration"])
        return ctx.do_circular(circ_args)

    rospy.logerr("[actions] survey_site: unsupported footprint_type '%s' for '%s'",
                 fp_type, site_name)
    return False

