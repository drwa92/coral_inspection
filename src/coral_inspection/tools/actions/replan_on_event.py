# src/coral_inspection/tools/actions/replan_on_event.py
# -*- coding: utf-8 -*-

import rospy


def do_replan_on_event(ctx, args):
    """
    replan_on_event: configure an event-based replanning trigger.

    The idea:
      - This action does NOT block or call the LLM directly.
      - Instead, it stores a configuration in a ROS parameter
        (default: /coral_captain/replan_config).
      - A separate node (coral_event_monitor) watches for events and,
        when the configured event occurs, it publishes a new prompt
        on /coral_captain/user_prompt to request a replanned mission.

    Args (from JSON):
      - event  (string, required): name of the event, e.g. "low_visibility",
                                   "low_battery", "strong_current", etc.
      - prompt (string, optional): custom natural-language prompt that will
                                   be sent to the LLM when the event occurs.
                                   If omitted, a generic prompt will be used.

    Example:
      { "action": "replan_on_event",
        "args": {
          "event": "low_visibility",
          "prompt": "Visibility has become low, abort the survey and plan a safe return."
        }
      }
    """
    event_name = args.get("event", "").strip()
    if not event_name:
        rospy.logerr("[actions] replan_on_event: 'event' field is required")
        return False

    prompt = args.get("prompt", "").strip()
    if not prompt:
        prompt = (
            "Event '{event}' occurred during the mission. "
            "Generate a safe replanned mission from the current state, "
            "for example by aborting the survey, returning home, and holding."
        ).format(event=event_name)

    # Where we store the config
    param_name = "/coral_captain/replan_config"

    config = {
        "event": event_name,
        "prompt": prompt,
        "active": True
    }

    rospy.set_param(param_name, config)
    rospy.loginfo("[actions] replan_on_event: configured replan on event='%s'", event_name)
    rospy.loginfo("[actions] replan_on_event: prompt='%s'", prompt)

    return True
