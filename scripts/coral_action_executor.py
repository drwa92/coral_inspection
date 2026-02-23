#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import json

from std_msgs.msg import String
from std_srvs.srv import Trigger, TriggerResponse

from coral_inspection.tools.action_tools import ActionTools


class CoralActionExecutor(object):
    """
    Coral Action Executor

    - Subscribes to a JSON plan on /coral_captain/plan (std_msgs/String).
    - Exposes a service ~execute_plan (std_srvs/Trigger) to start executing
      the last received plan.
    - Uses ActionTools to run low-level actions.
    - Publishes execution status on /coral_captain/execution_status.
    - Publishes mission memory events on /coral_captain/memory_event to be
      consumed by coral_mission_memory.py.
    """

    def __init__(self):
        rospy.init_node("coral_action_executor")

        # Parameters
        self.vehicle_ns = rospy.get_param("~vehicle_ns", "/bluerov2")
        self.pose_topic = rospy.get_param("~pose_topic",
                                          self.vehicle_ns + "/pose_gt")
        self.plan_topic = rospy.get_param("~plan_topic",
                                          "/coral_captain/plan")
        self.status_topic = rospy.get_param("~status_topic",
                                            "/coral_captain/execution_status")
        self.wait_for_motion = rospy.get_param("~wait_for_motion", True)

        # Last received plan (dict or None)
        self._current_plan = None

        # Tools for low-level actions
        self._actions = ActionTools(
            vehicle_ns=self.vehicle_ns,
            pose_topic=self.pose_topic,
            wait_for_motion=self.wait_for_motion
        )

        # Subscribers & publishers
        self._plan_sub = rospy.Subscriber(
            self.plan_topic, String, self._plan_cb
        )
        self._status_pub = rospy.Publisher(
            self.status_topic, String, queue_size=10, latch=True
        )

        # Memory event publisher
        self._memory_pub = rospy.Publisher(
            "/coral_captain/memory_event", String, queue_size=10
        )

        # Service to trigger execution of current plan
        self._exec_srv = rospy.Service(
            "~execute_plan", Trigger, self._execute_plan_cb
        )

        rospy.loginfo("[executor] vehicle_ns     = %s", self.vehicle_ns)
        rospy.loginfo("[executor] pose_topic     = %s", self.pose_topic)
        rospy.loginfo("[executor] plan_topic     = %s", self.plan_topic)
        rospy.loginfo("[executor] status_topic   = %s", self.status_topic)
        rospy.loginfo("[executor] wait_for_motion= %s", self.wait_for_motion)
        rospy.loginfo("[executor] ready: publish JSON plan on %s and call %s/execute_plan",
                      self.plan_topic, rospy.get_name())

    # ------------------------------------------------------------------
    # Plan receiving
    # ------------------------------------------------------------------
    def _plan_cb(self, msg):
        text = msg.data.strip()
        if not text:
            rospy.logwarn("[executor] received empty plan message")
            return

        try:
            plan = json.loads(text)
        except Exception as e:
            rospy.logerr("[executor] invalid JSON on %s: %s", self.plan_topic, e)
            return

        if "steps" not in plan or not isinstance(plan["steps"], list):
            rospy.logerr("[executor] plan missing 'steps' list")
            return

        self._current_plan = plan
        note = plan.get("note", "")
        rospy.loginfo("[executor] new plan received with %d steps. note=%s",
                      len(plan["steps"]), note)

        status = {
            "state": "plan_received",
            "n_steps": len(plan["steps"]),
            "note": note
        }
        self._publish_status(status)

    # ------------------------------------------------------------------
    # Status & memory helpers
    # ------------------------------------------------------------------
    def _publish_status(self, status_dict):
        """Publish executor status as JSON on status_topic."""
        try:
            text = json.dumps(status_dict)
        except Exception as e:
            rospy.logwarn("[executor] error serializing status: %s", e)
            return
        self._status_pub.publish(String(data=text))

    def _publish_memory_event(self, evt_dict):
        """Publish mission memory event JSON on /coral_captain/memory_event."""
        try:
            text = json.dumps(evt_dict)
        except Exception as e:
            rospy.logwarn("[executor] error serializing memory event: %s", e)
            return
        self._memory_pub.publish(String(data=text))

    def _record_mission_event(self, name):
        """Convenience wrapper for high-level mission events."""
        evt = {
            "type": "event",
            "name": name
        }
        self._publish_memory_event(evt)

    def _record_action_completed(self, action_name, args):
        """Record that an action completed successfully."""
        evt = {
            "type": "action_completed",
            "action": action_name,
            "args": args or {}
        }
        self._publish_memory_event(evt)

    def _record_photo_taken(self, label):
        evt = {
            "type": "photo_taken",
            "label": label
        }
        self._publish_memory_event(evt)

    # ------------------------------------------------------------------
    # Execution service
    # ------------------------------------------------------------------
    def _execute_plan_cb(self, req):
        """
        Handle ~execute_plan (std_srvs/Trigger):
        - Execute the _current_plan if available.
        - Return success + message.
        """
        if self._current_plan is None:
            msg = "No plan received yet on {}".format(self.plan_topic)
            rospy.logerr("[executor] %s", msg)
            return TriggerResponse(success=False, message=msg)

        plan = self._current_plan
        steps = plan.get("steps", [])
        note = plan.get("note", "")
        n_steps = len(steps)

        rospy.loginfo("[executor] executing plan with %d steps, note=%s",
                      n_steps, note)

        # Mission started -> memory
        self._record_mission_event("mission_started")
        self._publish_status({
            "state": "executing",
            "n_steps": n_steps,
            "note": note
        })

        all_ok = True

        for idx, step in enumerate(steps):
            if rospy.is_shutdown():
                all_ok = False
                break

            action_name = step.get("action", "").strip()
            args = step.get("args", {}) or {}

            if not action_name:
                rospy.logerr("[executor] step %d has no 'action' field", idx)
                all_ok = False
                break

            rospy.loginfo("[executor] step %d/%d: action=%s args=%r",
                          idx + 1, n_steps, action_name, args)

            step_status = {
                "state": "executing_step",
                "index": idx,
                "total": n_steps,
                "action": action_name,
                "args": args
            }
            self._publish_status(step_status)

            ok = self._execute_single_step(action_name, args)

            if not ok:
                rospy.logerr("[executor] step %d (%s) FAILED", idx + 1, action_name)
                all_ok = False

                # Record failure into memory as an event
                fail_evt = {
                    "type": "event",
                    "name": "action_failed",
                    "action": action_name,
                    "index": idx
                }
                self._publish_memory_event(fail_evt)

                break

            # On success, update mission memory
            if action_name == "take_photo":
                label = args.get("label", "photo_{}".format(idx))
                self._record_photo_taken(label)
            else:
                self._record_action_completed(action_name, args)

        # Finalization
        if all_ok:
            rospy.loginfo("[executor] plan completed successfully")
            self._record_mission_event("mission_completed")
            final_state = "completed"
        else:
            rospy.logwarn("[executor] plan did not complete successfully")
            self._record_mission_event("mission_failed")
            final_state = "failed"

        self._publish_status({
            "state": final_state,
            "n_steps": n_steps,
            "note": note
        })

        return TriggerResponse(
            success=all_ok,
            message="Plan execution {}".format(final_state)
        )

    # ------------------------------------------------------------------
    # Step dispatch
    # ------------------------------------------------------------------
    def _execute_single_step(self, action_name, args):
        """
        Dispatch a single step to the appropriate ActionTools method.

        Returns:
            True if the action succeeded, False otherwise.
        """
        try:
            if action_name == "go_to":
                return self._actions.do_go_to(args)
            elif action_name == "waypoint_list":
                return self._actions.do_waypoint_list(args)
            elif action_name == "circular":
                return self._actions.do_circular(args)
            elif action_name == "helical":
                return self._actions.do_helical(args)
            elif action_name == "waypoint_file":
                return self._actions.do_waypoint_file(args)
            elif action_name == "hold":
                return self._actions.do_hold(args)
            elif action_name == "go_to_site":
                return self._actions.do_go_to_site(args)
            elif action_name == "survey_rectangle":
                return self._actions.do_survey_rectangle(args)
            elif action_name == "survey_site":
                return self._actions.do_survey_site(args)
            elif action_name == "survey_circle_rings":
                return self._actions.do_survey_circle_rings(args)
            elif action_name == "hover_observe":
                return self._actions.do_hover_observe(args)
            elif action_name == "return_home":
                return self._actions.do_return_home(args)
            elif action_name == "emergency_stop":
                return self._actions.do_emergency_stop(args)
            elif action_name == "take_photo":
                return self._actions.do_take_photo(args)
            elif action_name == "replan_on_event":
                return self._actions.do_replan_on_event(args)
            else:
                rospy.logerr("[executor] unknown action '%s'", action_name)
                return False
        except Exception as e:
            rospy.logerr("[executor] exception while executing action '%s': %s",
                         action_name, e)
            return False

    # ------------------------------------------------------------------
    def spin(self):
        rospy.spin()


if __name__ == "__main__":
    try:
        node = CoralActionExecutor()
        node.spin()
    except rospy.ROSInterruptException:
        pass
