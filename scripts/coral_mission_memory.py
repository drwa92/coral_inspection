#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import json
from std_msgs.msg import String
from std_srvs.srv import Trigger, TriggerResponse


class CoralMissionMemory(object):
    """
    Minimal mission memory for Coral Captain.

    - Subscribes to /coral_captain/memory_event (std_msgs/String) where
      the data is a JSON object describing an event.

      Example messages:
        {"type": "action_completed",
         "action": "survey_site",
         "args": {"site": "A"}}

        {"type": "photo_taken",
         "label": "siteA_overview"}

        {"type": "event",
         "name": "low_visibility"}

    - Maintains an internal memory dictionary, for example:
        {
          "visited_sites": ["A", "B"],
          "completed_actions": [
            {"action": "survey_site", "args": {"site": "A"}},
            {"action": "hover_observe", "args": {"site": "A"}}
          ],
          "photos_taken": ["siteA_overview"],
          "last_event": "low_visibility",
          "replan_events": []
        }

    - Publishes the current memory as JSON on /coral_captain/memory_state
      (std_msgs/String, latched).

    - Provides a service /coral_captain/get_memory (std_srvs/Trigger)
      which returns the memory JSON in the 'message' field.
    """

    def __init__(self):
        rospy.init_node("coral_mission_memory")

        # Parameters (can be overridden in launch file)
        self.event_topic = rospy.get_param(
            "~event_topic", "/coral_captain/memory_event"
        )
        self.state_topic = rospy.get_param(
            "~state_topic", "/coral_captain/memory_state"
        )
        self.get_memory_service_name = rospy.get_param(
            "~get_memory_service", "/coral_captain/get_memory"
        )

        # Internal memory structure
        self._memory = {
            "visited_sites": [],       # list of site IDs like "A", "B", etc.
            "completed_actions": [],   # list of dicts {"action": ..., "args": {...}}
            "photos_taken": [],        # list of labels or dicts
            "last_event": "",          # last high-level event name
            "replan_events": []        # list of {"reason": ..., "timestamp": ...}
        }

        # Publisher for full memory state (JSON)
        self._state_pub = rospy.Publisher(
            self.state_topic, String, queue_size=10, latch=True
        )

        # Subscriber for memory events
        rospy.Subscriber(self.event_topic, String, self._memory_event_cb)

        # Service to get the current memory JSON
        self._get_srv = rospy.Service(
            self.get_memory_service_name,
            Trigger,
            self._handle_get_memory
        )

        rospy.loginfo("[mission_memory] event_topic      = %s", self.event_topic)
        rospy.loginfo("[mission_memory] state_topic      = %s", self.state_topic)
        rospy.loginfo("[mission_memory] get_memory_srv   = %s",
                      self.get_memory_service_name)
        rospy.loginfo("[mission_memory] ready: publish JSON events to %s",
                      self.event_topic)

        # Publish initial empty memory
        self._publish_memory()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _memory_event_cb(self, msg):
        """
        Handle incoming memory events.

        Expected msg.data: JSON string with at least a 'type' field.
        """
        text = msg.data.strip()
        if not text:
            return

        try:
            evt = json.loads(text)
        except Exception as e:
            rospy.logwarn("[mission_memory] invalid JSON on %s: %s",
                          self.event_topic, e)
            return

        evt_type = evt.get("type", "").strip()
        if not evt_type:
            rospy.logwarn("[mission_memory] event without 'type' field: %r", evt)
            return

        # Dispatch by type
        if evt_type == "action_completed":
            self._handle_action_completed(evt)
        elif evt_type == "photo_taken":
            self._handle_photo_taken(evt)
        elif evt_type == "event":
            self._handle_high_level_event(evt)
        elif evt_type == "replan":
            self._handle_replan_event(evt)
        else:
            rospy.logwarn("[mission_memory] unknown event type '%s': %r",
                          evt_type, evt)
            return

        # After any update, publish new memory
        self._publish_memory()

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------
    def _handle_action_completed(self, evt):
        action_name = evt.get("action", "").strip()
        args = evt.get("args", {})

        if not action_name:
            rospy.logwarn("[mission_memory] action_completed event missing 'action'")
            return

        entry = {
            "action": action_name,
            "args": args
        }
        self._memory["completed_actions"].append(entry)
        rospy.loginfo("[mission_memory] action_completed: %s", action_name)

        # If this action relates to a site, track visited_sites
        site = None
        if isinstance(args, dict):
            if "site" in args:
                site = str(args["site"])
            elif "footprint" in args:
                site = str(args["footprint"])

        if site:
            if site not in self._memory["visited_sites"]:
                self._memory["visited_sites"].append(site)
                rospy.loginfo("[mission_memory] visited_sites updated: %s",
                              self._memory["visited_sites"])

    def _handle_photo_taken(self, evt):
        label = evt.get("label", "").strip()
        if not label:
            label = "photo_" + str(rospy.Time.now().to_sec())
        self._memory["photos_taken"].append(label)
        rospy.loginfo("[mission_memory] photo_taken: %s", label)

    def _handle_high_level_event(self, evt):
        name = evt.get("name", "").strip()
        if not name:
            rospy.logwarn("[mission_memory] event missing 'name'")
            return
        self._memory["last_event"] = name
        rospy.loginfo("[mission_memory] last_event set to: %s", name)

    def _handle_replan_event(self, evt):
        reason = evt.get("reason", "").strip()
        ts = rospy.Time.now().to_sec()
        entry = {
            "reason": reason,
            "timestamp": ts
        }
        self._memory["replan_events"].append(entry)
        rospy.loginfo("[mission_memory] replan event recorded: %s", reason)

    # ------------------------------------------------------------------
    # Publishing & service
    # ------------------------------------------------------------------
    def _publish_memory(self):
        try:
            text = json.dumps(self._memory)
        except Exception as e:
            rospy.logwarn("[mission_memory] error serializing memory to JSON: %s", e)
            return
        self._state_pub.publish(String(data=text))

    def _handle_get_memory(self, req):
        """
        Handle /coral_captain/get_memory (std_srvs/Trigger).

        Returns current memory JSON in 'message'.
        """
        try:
            text = json.dumps(self._memory, indent=2)
        except Exception as e:
            rospy.logwarn("[mission_memory] error serializing memory: %s", e)
            return TriggerResponse(
                success=False,
                message="Error serializing memory: {}".format(e)
            )

        return TriggerResponse(
            success=True,
            message=text
        )

    # ------------------------------------------------------------------
    def spin(self):
        rospy.spin()


if __name__ == "__main__":
    try:
        node = CoralMissionMemory()
        node.spin()
    except rospy.ROSInterruptException:
        pass
