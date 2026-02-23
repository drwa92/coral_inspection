# src/coral_inspection/tools/actions/take_photo.py
# -*- coding: utf-8 -*-

import rospy


def do_take_photo(ctx, args):
    """
    take_photo: semantic action to capture an image at the current pose.

    Current implementation:
      - Logs a message
      - No ROS service is called (safe placeholder)
    Future:
      - Could call a camera trigger service or publish a capture request topic.
    """
    label = args.get("label", "")
    if label:
        rospy.loginfo("[actions] take_photo: capturing image with label '%s'", label)
    else:
        rospy.loginfo("[actions] take_photo: capturing image at current pose")

    # Placeholder: no real side-effect yet, but you can plug in a camera trigger
    # service or topic here later.
    return True

