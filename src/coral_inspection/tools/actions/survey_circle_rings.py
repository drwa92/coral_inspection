# src/coral_inspection/tools/actions/survey_circle_rings.py
# -*- coding: utf-8 -*-

import math
import rospy


def do_survey_circle_rings(ctx, args):
    """
    High-level action: survey_circle_rings

    Perform multiple circular orbits around a circular coral site at different
    radii ("rings"). This is a semantic / macro action that internally calls
    the lower-level 'circular' action multiple times via ctx.do_circular().

    Expected args (all optional except site/footprint or center):

      Either:
        site: "B" or "site_B" or "coral_bed_circle_B"
      Or:
        footprint: "coral_bed_circle_B"
      Or (fallback):
        center: [x, y, z]   # explicit world coordinates

      Rings (choose one of):
        rings: [6.0, 8.0, 10.0]  # explicit list of radii in meters
        OR
        n_rings: int             # number of rings to generate
        ring_spacing: float      # spacing between rings (default 2.0 m)
        start_radius: float      # optional, default derived from footprint

      Optional parameters:
        duration_per_ring: float (seconds per orbit, default ~120)
        max_forward_speed: float (default from ctx.survey_defaults or 0.5)
        is_clockwise: bool (default True)
        n_points: int (default 80)
        heading_offset: float (default 0.0)
        angle_offset: float (default 0.0)
        z: float  # explicit depth for orbit; otherwise use seafloor+altitude_m

    Returns:
        True if all rings succeed, False otherwise.
    """

    # ------------------------------------------------------------------
    # Resolve center (site / footprint / explicit center)
    # ------------------------------------------------------------------
    site_name = None
    site_info = None

    if "site" in args:
        site_name = args["site"]
    elif "footprint" in args:
        site_name = args["footprint"]

    if site_name is not None:
        site_info = ctx._get_site_info(site_name)
        if site_info is None:
            rospy.logerr("[actions][survey_circle_rings] Unknown site/footprint '%s'", site_name)
            return False

        (cx, cy, cz) = site_info.get("center", (0.0, 0.0, -30.0))
        footprint_type = site_info.get("footprint_type", "")
        raw_fp = site_info.get("raw", {})

        if footprint_type and footprint_type != "circle":
            rospy.logwarn("[actions][survey_circle_rings] footprint '%s' is type '%s', "
                          "but survey_circle_rings is intended for circular sites.",
                          site_name, footprint_type)
    else:
        # Fallback: explicit center
        center = args.get("center", None)
        if (not isinstance(center, (list, tuple))) or len(center) < 3:
            rospy.logerr("[actions][survey_circle_rings] Need 'site', 'footprint', "
                         "or 'center' [x,y,z] in args.")
            return False
        cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
        raw_fp = {}
        footprint_type = "unknown"

    # ------------------------------------------------------------------
    # Choose orbit depth (z)
    # ------------------------------------------------------------------
    if "z" in args:
        z_orbit = float(args["z"])
    else:
        # Use seafloor + altitude_m if we know seafloor (cz)
        altitude_m = float(ctx.survey_defaults.get("altitude_m", 3.0))
        z_orbit = cz + altitude_m

    # ------------------------------------------------------------------
    # Determine radii (rings)
    # ------------------------------------------------------------------
    rings = None

    if "rings" in args:
        # Explicit list of radii
        try:
            rings = [float(r) for r in args["rings"]]
        except Exception as e:
            rospy.logerr("[actions][survey_circle_rings] invalid 'rings' list: %s", e)
            return False
    else:
        # Auto-generate via n_rings + ring_spacing
        n_rings = int(args.get("n_rings", 0))
        ring_spacing = float(args.get("ring_spacing", 2.0))

        if n_rings <= 0:
            # Default to 3 rings if nothing specified
            n_rings = 3

        # Base radius from footprint if available, otherwise 7.5 m
        base_radius = 7.5
        if raw_fp:
            # If footprint is circle, diameter may be provided
            if "radius" in raw_fp:
                base_radius = float(raw_fp["radius"])
            elif "diameter" in raw_fp:
                base_radius = float(raw_fp["diameter"]) / 2.0

        start_radius = float(args.get("start_radius", max(base_radius * 0.6, 2.0)))

        rings = [start_radius + i * ring_spacing for i in range(n_rings)]

    # Filter out any non-positive radii
    rings = [r for r in rings if r > 0.0]
    if not rings:
        rospy.logerr("[actions][survey_circle_rings] No valid positive radii for rings.")
        return False

    rospy.loginfo("[actions][survey_circle_rings] Using center=(%.2f, %.2f, %.2f), rings=%s",
                  cx, cy, z_orbit, rings)

    # ------------------------------------------------------------------
    # Other parameters for each circular orbit
    # ------------------------------------------------------------------
    duration_per_ring = float(args.get("duration_per_ring", 120.0))
    max_speed = float(args.get("max_forward_speed",
                               ctx.survey_defaults.get("speed_mps", 0.5)))
    is_clockwise = bool(args.get("is_clockwise", True))
    n_points = int(args.get("n_points", 80))
    heading_offset = float(args.get("heading_offset", 0.0))
    angle_offset = float(args.get("angle_offset", 0.0))

    # ------------------------------------------------------------------
    # Execute each ring by calling ctx.do_circular(...)
    # ------------------------------------------------------------------
    all_ok = True

    for idx, radius in enumerate(rings):
        if rospy.is_shutdown():
            all_ok = False
            break

        ring_args = {
            "center": [cx, cy, z_orbit],
            "radius": float(radius),
            "is_clockwise": is_clockwise,
            "angle_offset": angle_offset,
            "n_points": n_points,
            "heading_offset": heading_offset,
            "max_forward_speed": max_speed,
            "duration": duration_per_ring,
            "start_now": True
        }

        rospy.loginfo("[actions][survey_circle_rings] Starting ring %d/%d: radius=%.2f m",
                      idx + 1, len(rings), radius)

        ok = ctx.do_circular(ring_args)

        if not ok:
            rospy.logerr("[actions][survey_circle_rings] Ring %d (radius=%.2f) FAILED",
                         idx + 1, radius)
            all_ok = False
            break

    if all_ok:
        rospy.loginfo("[actions][survey_circle_rings] Completed all %d rings successfully",
                      len(rings))
    else:
        rospy.logwarn("[actions][survey_circle_rings] survey_circle_rings did not complete successfully")

    return all_ok

