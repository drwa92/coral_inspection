#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import json
from std_msgs.msg import String


class CoralEventMonitor(object):
    """
    CoralEventMonitor: watches for high-level events and triggers LLM replanning.

    - Reads a configuration from the ROS parameter:
        /coral_captain/replan_config

      Example (set by replan_on_event action):
        {
          "event": "low_visibility",
          "prompt": "Visibility is low, safely abort the survey and return home.",
          "active": True
        }

    - Subscribes to /coral_captain/event_signal (std_msgs/String):
        The message data is the event name, e.g. "low_visibility".

    - When a matching event is received and 'active' is True:
        * Publishes the configured prompt to /coral_captain/user_prompt
          (std_msgs/String) to trigger a new LLM plan.
        * Sets 'active' to False to avoid repeated replans.
    """

    def __init__(self):
        rospy.init_node("coral_event_monitor")

        self.param_name = rospy.get_param(
            "~replan_param", "/coral_captain/replan_config"
        )
        self.event_topic = rospy.get_param(
            "~event_topic", "/coral_captain/event_signal"
        )
        self.user_prompt_topic = rospy.get_param(
            "~user_prompt_topic", "/coral_captain/user_prompt"
        )

        self._user_prompt_pub = rospy.Publisher(
            self.user_prompt_topic, String, queue_size=10, latch=True
        )

        rospy.Subscriber(self.event_topic, String, self._event_cb)

        rospy.loginfo("[event_monitor] replan_param   = %s", self.param_name)
        rospy.loginfo("[event_monitor] event_topic    = %s", self.event_topic)
        rospy.loginfo("[event_monitor] user_prompt_topic = %s", self.user_prompt_topic)
        rospy.loginfo("[event_monitor] ready: publish events on %s (e.g. 'low_visibility')",
                      self.event_topic)

    # ------------------------------------------------------------------
    def _load_config(self):
        """Load replan config from ROS param; return dict or None."""
        if not rospy.has_param(self.param_name):
            return None
        try:
            cfg = rospy.get_param(self.param_name)
            if not isinstance(cfg, dict):
                rospy.logwarn("[event_monitor] replan config is not a dict: %r", cfg)
                return None
            return cfg
        except Exception as e:
            rospy.logwarn("[event_monitor] error reading replan config: %s", e)
            return None

    def _save_config(self, cfg):
        """Save updated config back to ROS param."""
        try:
            rospy.set_param(self.param_name, cfg)
        except Exception as e:
            rospy.logwarn("[event_monitor] error writing replan config: %s", e)

    # ------------------------------------------------------------------
    def _event_cb(self, msg):
        event_name = msg.data.strip()
        if not event_name:
            return

        rospy.loginfo("[event_monitor] event received: '%s'", event_name)
        cfg = self._load_config()
        if cfg is None:
            rospy.loginfo("[event_monitor] no replan config set; ignoring event")
            return

        cfg_event = cfg.get("event", "").strip()
        active = bool(cfg.get("active", False))

        if not active:
            rospy.loginfo("[event_monitor] replan config exists but is not active; ignoring")
            return

        if cfg_event != event_name:
            rospy.loginfo("[event_monitor] event '%s' does not match configured '%s'; ignoring",
                          event_name, cfg_event)
            return

        # We have a match!
        prompt = cfg.get("prompt", "").strip()
        if not prompt:
            prompt = (
                "Event '{event}' occurred during the mission. "
                "Generate a safe replanned mission from the current state."
            ).format(event=event_name)

        rospy.logwarn("[event_monitor] MATCH: triggering replanning for event '%s'", event_name)
        rospy.loginfo("[event_monitor] sending prompt to LLM: %s", prompt)

        # Publish prompt to LLM planner
        self._user_prompt_pub.publish(String(data=prompt))

        # Mark config as inactive to avoid repeated triggers
        cfg["active"] = False
        self._save_config(cfg)
        rospy.loginfo("[event_monitor] replan config set to inactive")

    # ------------------------------------------------------------------
    def spin(self):
        rospy.spin()


if __name__ == "__main__":
    try:
        node = CoralEventMonitor()
        node.spin()
    except rospy.ROSInterruptException:
        pass
