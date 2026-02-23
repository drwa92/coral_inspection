# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# """
# llm_planner_node.py

# ROS node: LLM-driven mission planner for coral inspection.

# - Subscribes:  user prompt topic (std_msgs/String)
# - Publishes:   JSON mission plan (std_msgs/String)
# - Publishes:   status topic (std_msgs/String)

# Uses OpenAI API to translate natural-language prompts into a structured JSON
# plan with steps like:
#   - go_to
#   - go_to_site
#   - waypoint_list
#   - waypoint_file
#   - circular
#   - helical
#   - hold
#   - survey_site
#   - survey_rectangle
#   - survey_circle_rings
#   - hover_observe
#   - return_home
#   - emergency_stop
#   - take_photo
#   - replan_on_event

# NEW: The planner can optionally use mission memory from /coral_captain/get_memory
# (std_srvs/Trigger) and pass a compact summary as an additional system message
# starting with 'MISSION MEMORY:' so the LLM can avoid repeating work and can
# continue multi-step missions.
# """

# import os
# import json
# import yaml
# import traceback

# import rospy
# from std_msgs.msg import String as StringMsg
# from std_srvs.srv import Trigger, TriggerRequest

# try:
#     from openai import OpenAI  # OpenAI Python SDK v1
#     _HAS_OPENAI = True
# except ImportError:
#     _HAS_OPENAI = False
#     OpenAI = None  # type: ignore


# # ---------------------------------------------------------------------------
# # Allowed actions in the JSON plan
# # ---------------------------------------------------------------------------
# ALLOWED_ACTIONS = [
#     "go_to",
#     "go_to_site",
#     "waypoint_list",
#     "waypoint_file",
#     "circular",
#     "helical",
#     "hold",
#     "survey_rectangle",
#     "survey_site",
#     "survey_circle_rings",
#     "hover_observe",
#     "return_home",
#     "emergency_stop",
#     "take_photo",
#     "replan_on_event"
# ]


# # ---------------------------------------------------------------------------
# # System prompt to control the LLM behaviour
# # ---------------------------------------------------------------------------
# system_prompt = (
#     "You are an AI mission planner for an underwater ROV doing coral monitoring in a\n"
#     "simulated Gazebo environment. You receive a natural-language user prompt and\n"
#     "you must output a JSON object with:\n"
#     "  {\"steps\": [ ... ], \"note\": \"short explanation\"}\n"
#     "Each step must be of the form:\n"
#     "  {\"action\": <string>, \"args\": { ... }}\n"
#     "\n"
#     "You are NOT allowed to output anything except valid JSON.\n"
#     "Do NOT include comments, explanations, or trailing commas.\n"
#     "Do NOT invent new action names. Only use the actions listed below.\n"
#     "\n"
#     "ENVIRONMENT DESCRIPTION (WORLD & CORAL SITES)\n"
#     "--------------------------------------------\n"
#     "- World frame: 'world'. Coordinates (x, y, z) in meters.\n"
#     "- Seafloor depth is around z = -60. The ROV typically operates a few meters\n"
#     "  above the seafloor (e.g., z ≈ -57 for 3 m altitude).\n"
#     "- There are 4 main coral sites arranged in a grid-like layout. Each site has\n"
#     "  a frame and a footprint defined in a YAML file. You should REASON using\n"
#     "  site names (A, B, C, D, etc.) instead of raw coordinates when possible.\n"
#     "\n"
#     "Frames (approximate centers, all at z = -60):\n"
#     "  site_A: (0,   0,  -60)  yaw = 0 deg\n"
#     "  site_B: (80,  0,  -60)  yaw = 0 deg\n"
#     "  site_C: (0,  80,  -60)  yaw = 90 deg\n"
#     "  site_D: (80, 80,  -60)  yaw = 0 deg\n"
#     "\n"
#     "Footprints (linked to the frames):\n"
#     "  coral_bed_A:\n"
#     "    - center: site_A\n"
#     "    - type: rectangle\n"
#     "    - size_x: 34 m, size_y: 32 m, yaw ≈ 0 deg\n"
#     "  coral_bed_circle_B:\n"
#     "    - center: site_B\n"
#     "    - type: circle\n"
#     "    - diameter: 15 m\n"
#     "  coral_bed_cluster_C:\n"
#     "    - center: site_C\n"
#     "    - type: ellipse\n"
#     "    - size_x: 21 m, size_y: 6 m, yaw ≈ 90 deg\n"
#     "  coral_bed_crown_D:\n"
#     "    - center: site_D\n"
#     "    - type: square\n"
#     "    - size: 5 m\n"
#     "\n"
#     "Survey defaults (from YAML, used when args are not specified):\n"
#     "  stripe_spacing ≈ 4.0 m (lawnmower spacing)\n"
#     "  turn_buffer   ≈ 5.0 m (extra margin outside footprint)\n"
#     "  speed_mps     ≈ 0.5 m/s\n"
#     "  altitude_m    ≈ 3.0 m above seafloor (z ≈ -57)\n"
#     "Some footprints also have their own survey_profile with custom speed,\n"
#     "stripe spacing, altitude, and orbit padding. The executor automatically\n"
#     "uses these profiles for site-aware and ecology-aware surveys.\n"
#     "\n"
#     "AVAILABLE ACTIONS (YOU MUST CHOOSE FROM THIS LIST ONLY)\n"
#     "-------------------------------------------------------\n"
#     "\n"
#     "1) go_to: move the vehicle to a specific XYZ position.\n"
#     "   args:\n"
#     "     x, y, z: position in meters (world frame)\n"
#     "     optional max_forward_speed (float, default 0.4)\n"
#     "     optional heading_offset (float, default 0.0)\n"
#     "     optional use_fixed_heading (bool, default false)\n"
#     "     optional radius_of_acceptance (float, default 1.0)\n"
#     "     optional interpolator: one of [\"cubic\", \"linear\", \"lipb\", \"dubins\"]\n"
#     "       (default \"cubic\")\n"
#     "\n"
#     "2) waypoint_list: follow a list of waypoints in sequence.\n"
#     "   args:\n"
#     "     waypoints: [\n"
#     "       {\"x\": ..., \"y\": ..., \"z\": ...,\n"
#     "        \"max_forward_speed\": <float>,\n"
#     "        \"heading_offset\": <float>,\n"
#     "        \"use_fixed_heading\": <bool>,\n"
#     "        \"radius_of_acceptance\": <float>}, ...]\n"
#     "     optional global_max_forward_speed (float, default 0.4)\n"
#     "     optional heading_offset (float, default 0.0)\n"
#     "     optional interpolator (string, default \"cubic\")\n"
#     "     optional start_now (bool, default true)\n"
#     "\n"
#     "3) waypoint_file: load and execute a waypoint file from disk.\n"
#     "   args:\n"
#     "     file: absolute path to YAML file containing waypoints\n"
#     "     optional interpolator (string, default \"cubic\")\n"
#     "     optional start_now (bool, default true)\n"
#     "\n"
#     "4) circular: circular trajectory around a center.\n"
#     "   args:\n"
#     "     center: [x, y, z]\n"
#     "     radius: float (meters)\n"
#     "     optional is_clockwise (bool, default true)\n"
#     "     optional angle_offset (float, default 0.0)\n"
#     "     optional n_points (int, default 50)\n"
#     "     optional heading_offset (float, default 0.0)\n"
#     "     optional max_forward_speed (float, default 0.3)\n"
#     "     optional duration (float seconds, if > 0 the executor will sleep\n"
#     "       this long)\n"
#     "     optional start_now (bool, default true)\n"
#     "\n"
#     "5) helical: helical trajectory around a center.\n"
#     "   args:\n"
#     "     center: [x, y, z]\n"
#     "     radius: float\n"
#     "     optional is_clockwise (bool, default true)\n"
#     "     optional angle_offset (float, default 0.0)\n"
#     "     optional n_points (int, default 100)\n"
#     "     optional heading_offset (float, default 0.0)\n"
#     "     optional max_forward_speed (float, default 0.3)\n"
#     "     optional duration (float seconds, default 200)\n"
#     "     optional n_turns (float, default 3.0)\n"
#     "     optional delta_z (float, default 10.0)\n"
#     "     optional start_now (bool, default true)\n"
#     "\n"
#     "6) hold: hold position at the current location.\n"
#     "   args: { } (no arguments)\n"
#     "\n"
#     "7) go_to_site: go to the center of a named coral site.\n"
#     "   The executor will look up the site in a site database built from YAML.\n"
#     "   Typical site names: \"A\", \"B\", \"C\", \"D\", \"site_A\", \"coral_bed_A\", etc.\n"
#     "   args:\n"
#     "     site: string (e.g., \"A\", \"B\", \"site_C\", \"coral_bed_crown_D\")\n"
#     "     optional z: depth override (float)\n"
#     "     optional offset: [dx, dy, dz] in meters from site center\n"
#     "     optional max_forward_speed (float, default 0.4)\n"
#     "     optional heading_offset (float, default 0.0)\n"
#     "     optional use_fixed_heading (bool, default false)\n"
#     "     optional radius_of_acceptance (float, default 1.5)\n"
#     "     optional interpolator (string, default \"cubic\")\n"
#     "\n"
#     "8) survey_rectangle: perform a lawnmower (back-and-forth) survey over a\n"
#     "   rectangular or square coral footprint.\n"
#     "   Args:\n"
#     "     footprint: name of the footprint in the YAML (e.g. \"coral_bed_A\",\n"
#     "                \"coral_bed_crown_D\"), OR\n"
#     "     site: any alias that resolves to the same footprint (e.g. \"A\", \"D\").\n"
#     "   Optional:\n"
#     "     stripe_spacing: meters between stripes (default from survey defaults\n"
#     "       or footprint survey_profile)\n"
#     "     turn_buffer: meters beyond the footprint edge to allow turns\n"
#     "     max_forward_speed: float\n"
#     "     radius_of_acceptance: float\n"
#     "     z: explicit depth; if not given, altitude above seafloor is used\n"
#     "     interpolator: e.g. \"cubic\"\n"
#     "     start_now: bool\n"
#     "\n"
#     "9) survey_site: high-level semantic coral site survey.\n"
#     "   - Uses the site/footprint geometry and survey_profile from YAML.\n"
#     "   - rectangle/square/ellipse -> lawnmower (survey_rectangle)\n"
#     "   - circle                   -> circular orbit around the site.\n"
#     "   Args:\n"
#     "     site: alias like \"A\", \"B\", \"site_A\", \"coral_bed_A\", etc., OR\n"
#     "     footprint: explicit footprint name from the YAML.\n"
#     "   Optional:\n"
#     "     stripe_spacing, turn_buffer, max_forward_speed, radius_of_acceptance,\n"
#     "     z, interpolator, start_now, heading_offset, duration, orbit_radius,\n"
#     "     n_points, is_clockwise.\n"
#     "\n"
#     "10) survey_circle_rings: for circular coral sites, perform multiple\n"
#     "    circular orbits at different radii.\n"
#     "    Args:\n"
#     "      site or footprint: which circular site to use (e.g. \"B\",\n"
#     "        \"site_B\", \"coral_bed_circle_B\").\n"
#     "      Optional:\n"
#     "        rings: list of radii in meters, e.g. [6.0, 8.0, 10.0]; OR\n"
#     "        n_rings + ring_spacing to auto-generate radii.\n"
#     "        duration_per_ring: seconds per orbit (default ~120)\n"
#     "        max_forward_speed, is_clockwise, n_points, heading_offset,\n"
#     "        angle_offset, start_now.\n"
#     "\n"
#     "11) hover_observe: move (optionally) to a site or coordinate, then hold and\n"
#     "    observe for some duration.\n"
#     "    Args:\n"
#     "      Either:\n"
#     "        site or footprint: go to that site center (optionally with z override),\n"
#     "      Or:\n"
#     "        x, y, z: explicit world coordinates.\n"
#     "      Optional:\n"
#     "        duration: seconds to observe (default ~30).\n"
#     "\n"
#     "12) return_home: navigate back to a designated home at (0,0,0) and hold there.\n"
#     "    Args:\n"
#     "      site (optional): site alias to treat as home (default \"0,0,0\").\n"
#     "\n"
#     "13) emergency_stop: immediately stop and hold the vehicle.\n"
#     "    Args: { }\n"
#     "    This should be used for abort conditions. After this action, the\n"
#     "    executor will normally stop executing any remaining steps.\n"
#     "\n"
#     "14) take_photo: capture an image at the current pose.\n"
#     "    Args:\n"
#     "      optional label: string describing the photo (e.g. \"site_A_overview\").\n"
#     "    Currently this is implemented as a semantic/logging action, but it is\n"
#     "    safe and useful to include in mission plans.\n"
#     "\n"
#     "15) replan_on_event: semantic marker that this mission expects replanning\n"
#     "    on a certain event (e.g. \"low_visibility\", \"low_battery\").\n"
#     "    Args:\n"
#     "      event: short string naming the event.\n"
#     "    Currently this is a no-op stub in the executor; an external monitor\n"
#     "    may use it in the future to trigger a new plan.\n"
#     "\n"
#     "GUIDANCE FOR CHOOSING ACTIONS\n"
#     "-----------------------------\n"
#     "- If the user mentions specific coral sites (A, B, C, D, site_A,\n"
#     "  coral_bed_A, etc.), prefer using 'go_to_site', 'survey_site',\n"
#     "  'survey_rectangle', or 'survey_circle_rings' instead of raw 'go_to'\n"
#     "  coordinates.\n"
#     "- Use 'go_to' when the user gives a specific numeric (x, y, z).\n"
#     "- Use 'waypoint_list' or 'waypoint_file' for explicit precomputed paths.\n"
#     "- Use 'circular' or 'helical' for free-form orbit/spiral inspections not\n"
#     "  tied to a named site.\n"
#     "- Use 'hover_observe' when the user wants the ROV to hover and watch for\n"
#     "  some time at a site or position.\n"
#     "- Use 'take_photo' at meaningful points in the mission (e.g., after\n"
#     "  reaching a site or finishing a survey pattern).\n"
#     "- Use 'return_home' near the end of missions when the user asks to go back\n"
#     "  to the starting site or base.\n"
#     "- Use 'emergency_stop' only when the user explicitly asks to abort/stop\n"
#     "  immediately.\n"
#     "- 'replan_on_event' is optional and mainly used when the user mentions\n"
#     "  conditions like \"if visibility becomes too low, then...\".\n"
#     "\n"
#     "MISSION STRUCTURE\n"
#     "-----------------\n"
#     "- Plans should be a small sequence of steps (usually 1–10) that logically\n"
#     "  accomplish the user’s goal.\n"
#     "- Prefer simple, robust plans over overly complex ones.\n"
#     "- It is often good to end missions with 'hold' or 'return_home' plus 'hold'.\n"
#     "\n"
#     "MISSION MEMORY USAGE\n"
#     "--------------------\n"
#     "You may also receive an additional system message starting with\n"
#     "'MISSION MEMORY:'. It summarizes the current mission history, for example:\n"
#     "- which coral sites have already been visited or surveyed,\n"
#     "- which actions were recently completed,\n"
#     "- which photos were taken (by label),\n"
#     "- any recent high-level events or replans.\n"
#     "Use this memory to avoid repeating work (e.g., re-surveying a site that was\n"
#     "just finished), to continue multi-step missions, and to react consistently\n"
#     "to past events. For example, if site A has already been surveyed and the\n"
#     "user says 'continue with the remaining sites', plan for sites B, C, and D.\n"
#     "\n"
#     "Output only a single JSON object with 'steps' and 'note'.\n"
#     "Do not include any text before or after the JSON.\n"
# )


# # ---------------------------------------------------------------------------
# # Helper functions
# # ---------------------------------------------------------------------------
# def load_openai_config(path):
#     """Load OpenAI config from YAML."""
#     with open(path, "r") as f:
#         data = yaml.safe_load(f)

#     if not isinstance(data, dict) or "openai" not in data:
#         raise ValueError("YAML must contain top-level 'openai' key")

#     cfg = data["openai"]
#     api_key = cfg.get("api_key", None)
#     model_name = cfg.get("model_name", "gpt-4.1")
#     temperature = float(cfg.get("temperature", 0.2))
#     max_tokens = int(cfg.get("max_tokens", 800))

#     if not api_key:
#         raise ValueError("Missing openai.api_key in config")

#     return api_key, model_name, temperature, max_tokens


# def extract_json_object(text):
#     """
#     Try to extract a JSON object from a string.
#     The system prompt tells the LLM to output only JSON, but this is a safety net.
#     """
#     text = text.strip()
#     try:
#         return json.loads(text)
#     except Exception:
#         pass

#     try:
#         start = text.index("{")
#         end = text.rindex("}") + 1
#         candidate = text[start:end]
#         return json.loads(candidate)
#     except Exception:
#         raise ValueError("Could not parse JSON from LLM response")


# def validate_plan(plan):
#     """
#     Basic validation: ensure structure and allowed actions.
#     Raises ValueError if invalid.
#     """
#     if not isinstance(plan, dict):
#         raise ValueError("Plan must be a JSON object")

#     if "steps" not in plan:
#         raise ValueError("Plan must contain 'steps'")

#     steps = plan["steps"]
#     if not isinstance(steps, list):
#         raise ValueError("'steps' must be a list")

#     for i, step in enumerate(steps):
#         if not isinstance(step, dict):
#             raise ValueError("Step %d is not an object" % i)
#         if "action" not in step:
#             raise ValueError("Step %d missing 'action'" % i)
#         if "args" not in step:
#             raise ValueError("Step %d missing 'args'" % i)

#         action = step["action"]
#         if action not in ALLOWED_ACTIONS:
#             raise ValueError("Step %d uses unknown action '%s'" % (i, action))

#         if not isinstance(step["args"], dict):
#             raise ValueError("Step %d 'args' must be an object" % i)

#     if "note" not in plan:
#         plan["note"] = "LLM-generated mission plan"

#     return plan


# def build_fallback_plan(prompt_text):
#     """
#     Fallback plan if the LLM or JSON parsing fails.
#     Simple behaviour: go to site A, then hold.
#     """
#     rospy.logwarn("[llm_planner] Using fallback plan for prompt: %s", prompt_text)

#     plan = {
#         "steps": [
#             {
#                 "action": "go_to_site",
#                 "args": {
#                     "site": "A",
#                     "radius_of_acceptance": 2.0
#                 }
#             },
#             {
#                 "action": "hold",
#                 "args": {}
#             }
#         ],
#         "note": "Fallback plan: go to site A and hold."
#     }
#     return plan


# # ---------------------------------------------------------------------------
# # LLM Planner Node
# # ---------------------------------------------------------------------------
# class LLMPlannerNode(object):
#     def __init__(self):
#         rospy.init_node("llm_planner", anonymous=False)

#         # Parameters
#         self.user_prompt_topic = rospy.get_param("~user_prompt_topic", "/coral_captain/user_prompt")
#         self.plan_topic        = rospy.get_param("~plan_topic", "/coral_captain/plan")
#         self.status_topic      = rospy.get_param("~status_topic", "/coral_captain/llm_status")
#         self.openai_config     = rospy.get_param("~openai_config", "")
#         self.memory_service    = rospy.get_param("~memory_service", "/coral_captain/get_memory")

#         # Publishers
#         self.plan_pub   = rospy.Publisher(self.plan_topic,   StringMsg, queue_size=10, latch=True)
#         self.status_pub = rospy.Publisher(self.status_topic, StringMsg, queue_size=10, latch=True)

#         # OpenAI client
#         self.client = None
#         self.model_name = None
#         self.temperature = 0.2
#         self.max_tokens = 800

#         if not _HAS_OPENAI:
#             rospy.logwarn("[llm_planner] openai package not installed. Only fallback plans will be used.")
#         else:
#             self._init_openai_client()

#         # Mission memory service proxy (lazy)
#         self._memory_proxy = None

#         # Subscriber to user prompt
#         rospy.Subscriber(self.user_prompt_topic, StringMsg, self._prompt_cb, queue_size=1)

#         rospy.loginfo("[llm_planner] ready. Publish prompt on %s", self.user_prompt_topic)
#         rospy.loginfo("[llm_planner] memory_service: %s", self.memory_service)

#     def _init_openai_client(self):
#         if not self.openai_config:
#             rospy.logwarn("[llm_planner] No '~openai_config' param set; using fallback only.")
#             return

#         try:
#             api_key, model_name, temperature, max_tokens = load_openai_config(self.openai_config)
#             os.environ["OPENAI_API_KEY"] = api_key  # SDK will pick this up
#             self.client = OpenAI()
#             self.model_name = model_name
#             self.temperature = temperature
#             self.max_tokens = max_tokens
#             rospy.loginfo("[llm_planner] OpenAI client initialized: model=%s", self.model_name)
#         except Exception as e:
#             rospy.logerr("[llm_planner] Failed to init OpenAI client from %s: %s",
#                          self.openai_config, e)
#             self.client = None

#     def _publish_status(self, text):
#         msg = StringMsg(data=text)
#         self.status_pub.publish(msg)

#     # ------------------------------------------------------------------
#     # Mission memory helpers
#     # ------------------------------------------------------------------
#     def _get_memory_summary(self):
#         """
#         Call /coral_captain/get_memory (Trigger) and return a compact
#         'MISSION MEMORY:' text, or "" if unavailable.
#         """
#         if self._memory_proxy is None:
#             try:
#                 rospy.wait_for_service(self.memory_service, timeout=0.5)
#                 self._memory_proxy = rospy.ServiceProxy(self.memory_service, Trigger)
#                 rospy.loginfo("[llm_planner] Connected to mission memory service: %s",
#                               self.memory_service)
#             except Exception as e:
#                 rospy.logdebug("[llm_planner] Memory service not available: %s", e)
#                 return ""

#         try:
#             resp = self._memory_proxy(TriggerRequest())
#         except Exception as e:
#             rospy.logwarn("[llm_planner] Error calling mission memory service: %s", e)
#             return ""

#         if not resp.success or not resp.message:
#             return ""

#         try:
#             mem = json.loads(resp.message)
#         except Exception:
#             raw = resp.message
#             if len(raw) > 500:
#                 raw = raw[:500] + "...(truncated)"
#             return "MISSION MEMORY (raw):\n" + raw

#         return self._summarize_memory_dict(mem)

#     def _summarize_memory_dict(self, mem):
#         """
#         Convert mission memory dict into compact human-readable summary.
#         Assumes keys like:
#           visited_sites: [string]
#           completed_actions: [ {action, args, ...}, ... ]
#           photos_taken: [string or dict]
#           last_event: string
#           replan_events: [dict or string]
#         """
#         if not isinstance(mem, dict):
#             return ""

#         visited = mem.get("visited_sites", [])
#         completed = mem.get("completed_actions", [])
#         photos = mem.get("photos_taken", [])
#         last_event = mem.get("last_event", "")
#         replan_events = mem.get("replan_events", [])

#         lines = []

#         if visited:
#             lines.append("Visited coral sites: " + ", ".join(map(str, visited)))
#         else:
#             lines.append("Visited coral sites: none yet.")

#         if completed:
#             lines.append("Total completed actions: {}".format(len(completed)))
#             tail = completed[-5:]
#             descs = []
#             for c in tail:
#                 if isinstance(c, dict):
#                     a = c.get("action", "?")
#                     args = c.get("args", {})
#                     site = args.get("site", args.get("footprint", None)) if isinstance(args, dict) else None
#                     if site:
#                         descs.append("{}(site={})".format(a, site))
#                     else:
#                         descs.append(a)
#                 else:
#                     descs.append(str(c))
#             lines.append("Recent actions: " + ", ".join(descs))
#         else:
#             lines.append("No actions completed yet in this mission.")

#         if photos:
#             lines.append("Photos taken: {} total".format(len(photos)))
#             last_photo = photos[-1]
#             if isinstance(last_photo, dict):
#                 label = last_photo.get("label", "?")
#             else:
#                 label = str(last_photo)
#             lines.append("Last photo label: {}".format(label))
#         else:
#             lines.append("No photos taken yet.")

#         if last_event:
#             lines.append("Last high-level event: {}".format(last_event))

#         if replan_events:
#             lines.append("Replans triggered: {}".format(len(replan_events)))

#         summary = "MISSION MEMORY:\n" + "\n".join(lines)
#         return summary

#     # ------------------------------------------------------------------
#     # Prompt callback
#     # ------------------------------------------------------------------
#     def _prompt_cb(self, msg):
#         prompt_text = msg.data.strip()
#         if not prompt_text:
#             rospy.logwarn("[llm_planner] Received empty prompt; ignoring.")
#             return

#         rospy.loginfo("[llm_planner] Received user prompt: %s", prompt_text)
#         self._publish_status("planning: " + prompt_text)

#         memory_summary = self._get_memory_summary()
#         if memory_summary:
#             rospy.loginfo("[llm_planner] Mission memory summary will be included in LLM prompt.")
#         else:
#             rospy.loginfo("[llm_planner] No mission memory available or service not ready.")

#         plan = None
#         error_str = None

#         if self.client is None:
#             error_str = "OpenAI client not available; using fallback."
#         else:
#             try:
#                 plan = self._call_llm(prompt_text, memory_summary)
#             except Exception as e:
#                 error_str = "LLM or JSON error: %s" % e
#                 rospy.logerr("[llm_planner] %s", error_str)
#                 rospy.logdebug(traceback.format_exc())

#         if plan is None:
#             plan = build_fallback_plan(prompt_text)

#         plan_str = json.dumps(plan, separators=(",", ":"))
#         self.plan_pub.publish(StringMsg(data=plan_str))

#         if error_str:
#             self._publish_status("ok_with_fallback: " + error_str)
#         else:
#             self._publish_status("ok: plan generated")

#         rospy.loginfo("[llm_planner] Plan published: %s", plan_str)

#     def _call_llm(self, prompt_text, memory_summary=""):
#         """
#         Call OpenAI model and return a validated plan (dict).
#         Raises exceptions if anything goes wrong.
#         """
#         if self.client is None:
#             raise RuntimeError("OpenAI client not initialized")

#         messages = [
#             {"role": "system", "content": system_prompt}
#         ]

#         if memory_summary:
#             messages.append({"role": "system", "content": memory_summary})

#         messages.append({"role": "user", "content": prompt_text})

#         completion = self.client.chat.completions.create(
#             model=self.model_name,
#             temperature=self.temperature,
#             max_tokens=self.max_tokens,
#             response_format={"type": "json_object"},
#             messages=messages,
#         )

#         content = completion.choices[0].message.content
#         rospy.logdebug("[llm_planner] Raw LLM response: %s", content)

#         obj = extract_json_object(content)
#         plan = validate_plan(obj)
#         return plan


# # ---------------------------------------------------------------------------
# # Main
# # ---------------------------------------------------------------------------
# if __name__ == "__main__":
#     try:
#         node = LLMPlannerNode()
#         rospy.spin()
#     except rospy.ROSInterruptException:
#         pass

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
llm_planner_node.py

ROS node: LLM-driven mission planner for coral inspection.

- Subscribes:  user prompt topic (std_msgs/String)
- Publishes:   JSON mission plan (std_msgs/String)
- Publishes:   status topic (std_msgs/String)

Uses OpenAI API to translate natural-language prompts into a structured JSON
plan with steps like:
  - go_to
  - go_to_site
  - waypoint_list
  - waypoint_file
  - circular
  - helical
  - hold
  - survey_site
  - survey_rectangle
  - survey_circle_rings
  - hover_observe
  - return_home
  - emergency_stop
  - take_photo
  - replan_on_event

NEW: The planner can optionally use mission memory from /coral_captain/get_memory
(std_srvs/Trigger) and pass a compact summary as an additional system message
starting with 'MISSION MEMORY:' so the LLM can avoid repeating work and can
continue multi-step missions.
"""

import os
import json
import yaml
import traceback
import time  # <<< ADDED: for latency measurement

import rospy
from std_msgs.msg import String as StringMsg
from std_srvs.srv import Trigger, TriggerRequest

try:
    from openai import OpenAI  # OpenAI Python SDK v1
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False
    OpenAI = None  # type: ignore


# ---------------------------------------------------------------------------
# Allowed actions in the JSON plan
# ---------------------------------------------------------------------------
ALLOWED_ACTIONS = [
    "go_to",
    "go_to_site",
    "waypoint_list",
    "waypoint_file",
    "circular",
    "helical",
    "hold",
    "survey_rectangle",
    "survey_site",
    "survey_circle_rings",
    "hover_observe",
    "return_home",
    "emergency_stop",
    "take_photo",
    "replan_on_event"
]


# ---------------------------------------------------------------------------
# System prompt to control the LLM behaviour
# ---------------------------------------------------------------------------
system_prompt = (
    "You are an AI mission planner for an underwater ROV doing coral monitoring in a\n"
    "simulated Gazebo environment. You receive a natural-language user prompt and\n"
    "you must output a JSON object with:\n"
    "  {\"steps\": [ ... ], \"note\": \"short explanation\"}\n"
    "Each step must be of the form:\n"
    "  {\"action\": <string>, \"args\": { ... }}\n"
    "\n"
    "You are NOT allowed to output anything except valid JSON.\n"
    "Do NOT include comments, explanations, or trailing commas.\n"
    "Do NOT invent new action names. Only use the actions listed below.\n"
    "\n"
    "ENVIRONMENT DESCRIPTION (WORLD & CORAL SITES)\n"
    "--------------------------------------------\n"
    "- World frame: 'world'. Coordinates (x, y, z) in meters.\n"
    "- Seafloor depth is around z = -60. The ROV typically operates a few meters\n"
    "  above the seafloor (e.g., z ≈ -40 for 20 m altitude).\n"
    "- There are 4 main coral sites arranged in a grid-like layout. Each site has\n"
    "  a frame and a footprint defined in a YAML file. You should REASON using\n"
    "  site names (A, B, C, D, etc.) instead of raw coordinates when possible.\n"
    "\n"
    "Frames (approximate centers, all at z = -60):\n"
    "  site_A: (0,   0,  -60)  yaw = 0 deg\n"
    "  site_B: (80,  0,  -60)  yaw = 0 deg\n"
    "  site_C: (0,  80,  -60)  yaw = 90 deg\n"
    "  site_D: (80, 80,  -60)  yaw = 0 deg\n"
    "\n"
    "Footprints (linked to the frames):\n"
    "  coral_bed_A:\n"
    "    - center: site_A\n"
    "    - type: rectangle\n"
    "    - size_x: 34 m, size_y: 32 m, yaw ≈ 0 deg\n"
    "  coral_bed_circle_B:\n"
    "    - center: site_B\n"
    "    - type: circle\n"
    "    - diameter: 15 m\n"
    "  coral_bed_cluster_C:\n"
    "    - center: site_C\n"
    "    - type: ellipse\n"
    "    - size_x: 21 m, size_y: 6 m, yaw ≈ 90 deg\n"
    "  coral_bed_crown_D:\n"
    "    - center: site_D\n"
    "    - type: square\n"
    "    - size: 5 m\n"
    "\n"
    "Survey defaults (from YAML, used when args are not specified):\n"
    "  stripe_spacing ≈ 4.0 m (lawnmower spacing)\n"
    "  turn_buffer   ≈ 5.0 m (extra margin outside footprint)\n"
    "  speed_mps     ≈ 0.5 m/s\n"
    "  altitude_m    ≈ 3.0 m above seafloor (z ≈ -57)\n"
    "Some footprints also have their own survey_profile with custom speed,\n"
    "stripe spacing, altitude, and orbit padding. The executor automatically\n"
    "uses these profiles for site-aware and ecology-aware surveys.\n"
    "\n"
    "AVAILABLE ACTIONS (YOU MUST CHOOSE FROM THIS LIST ONLY)\n"
    "-------------------------------------------------------\n"
    "\n"
    "1) go_to: move the vehicle to a specific XYZ position.\n"
    "   args:\n"
    "     x, y, z: position in meters (world frame)\n"
    "     optional max_forward_speed (float, default 0.4)\n"
    "     optional heading_offset (float, default 0.0)\n"
    "     optional use_fixed_heading (bool, default false)\n"
    "     optional radius_of_acceptance (float, default 1.0)\n"
    "     optional interpolator: one of [\"cubic\", \"linear\", \"lipb\", \"dubins\"]\n"
    "       (default \"cubic\")\n"
    "\n"
    "2) waypoint_list: follow a list of waypoints in sequence.\n"
    "   args:\n"
    "     waypoints: [\n"
    "       {\"x\": ..., \"y\": ..., \"z\": ...,\n"
    "        \"max_forward_speed\": <float>,\n"
    "        \"heading_offset\": <float>,\n"
    "        \"use_fixed_heading\": <bool>,\n"
    "        \"radius_of_acceptance\": <float>}, ...]\n"
    "     optional global_max_forward_speed (float, default 0.4)\n"
    "     optional heading_offset (float, default 0.0)\n"
    "     optional interpolator (string, default \"cubic\")\n"
    "     optional start_now (bool, default true)\n"
    "\n"
    "3) waypoint_file: load and execute a waypoint file from disk.\n"
    "   args:\n"
    "     file: absolute path to YAML file containing waypoints\n"
    "     optional interpolator (string, default \"cubic\")\n"
    "     optional start_now (bool, default true)\n"
    "\n"
    "4) circular: circular trajectory around a center.\n"
    "   args:\n"
    "     center: [x, y, z]\n"
    "     radius: float (meters)\n"
    "     optional is_clockwise (bool, default true)\n"
    "     optional angle_offset (float, default 0.0)\n"
    "     optional n_points (int, default 50)\n"
    "     optional heading_offset (float, default 0.0)\n"
    "     optional max_forward_speed (float, default 0.3)\n"
    "     optional duration (float seconds, if > 0 the executor will sleep\n"
    "       this long)\n"
    "     optional start_now (bool, default true)\n"
    "\n"
    "5) helical: helical trajectory around a center.\n"
    "   args:\n"
    "     center: [x, y, z]\n"
    "     radius: float\n"
    "     optional is_clockwise (bool, default true)\n"
    "     optional angle_offset (float, default 0.0)\n"
    "     optional n_points (int, default 100)\n"
    "     optional heading_offset (float, default 0.0)\n"
    "     optional max_forward_speed (float, default 0.3)\n"
    "     optional duration (float seconds, default 200)\n"
    "     optional n_turns (float, default 3.0)\n"
    "     optional delta_z (float, default 10.0)\n"
    "     optional start_now (bool, default true)\n"
    "\n"
    "6) hold: hold position at the current location.\n"
    "   args: { } (no arguments)\n"
    "\n"
    "7) go_to_site: go to the center of a named coral site.\n"
    "   The executor will look up the site in a site database built from YAML.\n"
    "   Typical site names: \"A\", \"B\", \"C\", \"D\", \"site_A\", \"coral_bed_A\", etc.\n"
    "   args:\n"
    "     site: string (e.g., \"A\", \"B\", \"site_C\", \"coral_bed_crown_D\")\n"
    "     optional z: depth override (float)\n"
    "     optional offset: [dx, dy, dz] in meters from site center\n"
    "     optional max_forward_speed (float, default 0.4)\n"
    "     optional heading_offset (float, default 0.0)\n"
    "     optional use_fixed_heading (bool, default false)\n"
    "     optional radius_of_acceptance (float, default 1.5)\n"
    "     optional interpolator (string, default \"cubic\")\n"
    "\n"
    "8) survey_rectangle: perform a lawnmower (back-and-forth) survey over a\n"
    "   rectangular or square coral footprint.\n"
    "   Args:\n"
    "     footprint: name of the footprint in the YAML (e.g. \"coral_bed_A\",\n"
    "                \"coral_bed_crown_D\"), OR\n"
    "     site: any alias that resolves to the same footprint (e.g. \"A\", \"D\").\n"
    "   Optional:\n"
    "     stripe_spacing: meters between stripes (default from survey defaults\n"
    "       or footprint survey_profile)\n"
    "     turn_buffer: meters beyond the footprint edge to allow turns\n"
    "     max_forward_speed: float\n"
    "     radius_of_acceptance: float\n"
    "     z: explicit depth; if not given, altitude above seafloor is used\n"
    "     interpolator: e.g. \"cubic\"\n"
    "     start_now: bool\n"
    "\n"
    "9) survey_site: high-level semantic coral site survey.\n"
    "   - Uses the site/footprint geometry and survey_profile from YAML.\n"
    "   - rectangle/square/ellipse -> lawnmower (survey_rectangle)\n"
    "   - circle                   -> circular orbit around the site.\n"
    "   Args:\n"
    "     site: alias like \"A\", \"B\", \"site_A\", \"coral_bed_A\", etc., OR\n"
    "     footprint: explicit footprint name from the YAML.\n"
    "   Optional:\n"
    "     stripe_spacing, turn_buffer, max_forward_speed, radius_of_acceptance,\n"
    "     z, interpolator, start_now, heading_offset, duration, orbit_radius,\n"
    "     n_points, is_clockwise.\n"
    "\n"
    "10) survey_circle_rings: for circular coral sites, perform multiple\n"
    "    circular orbits at different radii.\n"
    "    Args:\n"
    "      site or footprint: which circular site to use (e.g. \"B\",\n"
    "        \"site_B\", \"coral_bed_circle_B\").\n"
    "      Optional:\n"
    "        rings: list of radii in meters, e.g. [6.0, 8.0, 10.0]; OR\n"
    "        n_rings + ring_spacing to auto-generate radii.\n"
    "        duration_per_ring: seconds per orbit (default ~120)\n"
    "        max_forward_speed, is_clockwise, n_points, heading_offset,\n"
    "        angle_offset, start_now.\n"
    "\n"
    "11) hover_observe: move (optionally) to a site or coordinate, then hold and\n"
    "    observe for some duration.\n"
    "    Args:\n"
    "      Either:\n"
    "        site or footprint: go to that site center (optionally with z override),\n"
    "      Or:\n"
    "        x, y, z: explicit world coordinates.\n"
    "      Optional:\n"
    "        duration: seconds to observe (default ~30).\n"
    "\n"
    "12) return_home: navigate back to a designated home at (0,0,0) and hold there.\n"
    "    Args:\n"
    "      site (optional): site alias to treat as home (default \"0,0,0\").\n"
    "\n"
    "13) emergency_stop: immediately stop and hold the vehicle.\n"
    "    Args: { }\n"
    "    This should be used for abort conditions. After this action, the\n"
    "    executor will normally stop executing any remaining steps.\n"
    "\n"
    "14) take_photo: capture an image at the current pose.\n"
    "    Args:\n"
    "      optional label: string describing the photo (e.g. \"site_A_overview\").\n"
    "    Currently this is implemented as a semantic/logging action, but it is\n"
    "    safe and useful to include in mission plans.\n"
    "\n"
    "15) replan_on_event: semantic marker that this mission expects replanning\n"
    "    on a certain event (e.g. \"low_visibility\", \"low_battery\").\n"
    "    Args:\n"
    "      event: short string naming the event.\n"
    "    Currently this is a no-op stub in the executor; an external monitor\n"
    "    may use it in the future to trigger a new plan.\n"
    "\n"
    "GUIDANCE FOR CHOOSING ACTIONS\n"
    "-----------------------------\n"
    "- If the user mentions specific coral sites (A, B, C, D, site_A,\n"
    "  coral_bed_A, etc.), prefer using 'go_to_site', 'survey_site',\n"
    "  'survey_rectangle', or 'survey_circle_rings' instead of raw 'go_to'\n"
    "  coordinates.\n"
    "- Use 'go_to' when the user gives a specific numeric (x, y, z).\n"
    "- Use 'waypoint_list' or 'waypoint_file' for explicit precomputed paths.\n"
    "- Use 'circular' or 'helical' for free-form orbit/spiral inspections not\n"
    "  tied to a named site.\n"
    "- Use 'hover_observe' when the user wants the ROV to hover and watch for\n"
    "  some time at a site or position.\n"
    "- Use 'take_photo' at meaningful points in the mission (e.g., after\n"
    "  reaching a site or finishing a survey pattern).\n"
    "- Use 'return_home' near the end of missions when the user asks to go back\n"
    "  to the starting site or base.\n"
    "- Use 'emergency_stop' only when the user explicitly asks to abort/stop\n"
    "  immediately.\n"
    "- 'replan_on_event' is optional and mainly used when the user mentions\n"
    "  conditions like \"if visibility becomes too low, then...\".\n"
    "\n"
    "MISSION STRUCTURE\n"
    "-----------------\n"
    "- Plans should be a small sequence of steps (usually 1–10) that logically\n"
    "  accomplish the user’s goal.\n"
    "- Prefer simple, robust plans over overly complex ones.\n"
    "- It is often good to end missions with 'hold' or 'return_home' plus 'hold'.\n"
    "\n"
    "MISSION MEMORY USAGE\n"
    "--------------------\n"
    "You may also receive an additional system message starting with\n"
    "'MISSION MEMORY:'. It summarizes the current mission history, for example:\n"
    "- which coral sites have already been visited or surveyed,\n"
    "- which actions were recently completed,\n"
    "- which photos were taken (by label),\n"
    "- any recent high-level events or replans.\n"
    "Use this memory to avoid repeating work (e.g., re-surveying a site that was\n"
    "just finished), to continue multi-step missions, and to react consistently\n"
    "to past events. For example, if site A has already been surveyed and the\n"
    "user says 'continue with the remaining sites', plan for sites B, C, and D.\n"
    "\n"
    "Output only a single JSON object with 'steps' and 'note'.\n"
    "Do not include any text before or after the JSON.\n"
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def load_openai_config(path):
    """Load OpenAI config from YAML."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "openai" not in data:
        raise ValueError("YAML must contain top-level 'openai' key")

    cfg = data["openai"]
    api_key = cfg.get("api_key", None)
    model_name = cfg.get("model_name", "gpt-4.1")
    temperature = float(cfg.get("temperature", 0.2))
    max_tokens = int(cfg.get("max_tokens", 800))

    if not api_key:
        raise ValueError("Missing openai.api_key in config")

    return api_key, model_name, temperature, max_tokens


def extract_json_object(text):
    """
    Try to extract a JSON object from a string.
    The system prompt tells the LLM to output only JSON, but this is a safety net.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        candidate = text[start:end]
        return json.loads(candidate)
    except Exception:
        raise ValueError("Could not parse JSON from LLM response")


def validate_plan(plan):
    """
    Basic validation: ensure structure and allowed actions.
    Raises ValueError if invalid.
    """
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a JSON object")

    if "steps" not in plan:
        raise ValueError("Plan must contain 'steps'")

    steps = plan["steps"]
    if not isinstance(steps, list):
        raise ValueError("'steps' must be a list")

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError("Step %d is not an object" % i)
        if "action" not in step:
            raise ValueError("Step %d missing 'action'" % i)
        if "args" not in step:
            raise ValueError("Step %d missing 'args'" % i)

        action = step["action"]
        if action not in ALLOWED_ACTIONS:
            raise ValueError("Step %d uses unknown action '%s'" % (i, action))

        if not isinstance(step["args"], dict):
            raise ValueError("Step %d 'args' must be an object" % i)

    if "note" not in plan:
        plan["note"] = "LLM-generated mission plan"

    return plan


def build_fallback_plan(prompt_text):
    """
    Fallback plan if the LLM or JSON parsing fails.
    Simple behaviour: go to site A, then hold.
    """
    rospy.logwarn("[llm_planner] Using fallback plan for prompt: %s", prompt_text)

    plan = {
        "steps": [
            {
                "action": "go_to_site",
                "args": {
                    "site": "A",
                    "radius_of_acceptance": 2.0
                }
            },
            {
                "action": "hold",
                "args": {}
            }
        ],
        "note": "Fallback plan: go to site A and hold."
    }
    return plan


# ---------------------------------------------------------------------------
# LLM Planner Node
# ---------------------------------------------------------------------------
class LLMPlannerNode(object):
    def __init__(self):
        rospy.init_node("llm_planner", anonymous=False)

        # Parameters
        self.user_prompt_topic = rospy.get_param("~user_prompt_topic", "/coral_captain/user_prompt")
        self.plan_topic        = rospy.get_param("~plan_topic", "/coral_captain/plan")
        self.status_topic      = rospy.get_param("~status_topic", "/coral_captain/llm_status")
        self.openai_config     = rospy.get_param("~openai_config", "")
        self.memory_service    = rospy.get_param("~memory_service", "/coral_captain/get_memory")

        # Publishers
        self.plan_pub   = rospy.Publisher(self.plan_topic,   StringMsg, queue_size=10, latch=True)
        self.status_pub = rospy.Publisher(self.status_topic, StringMsg, queue_size=10, latch=True)

        # OpenAI client
        self.client = None
        self.model_name = None
        self.temperature = 0.2
        self.max_tokens = 800

        if not _HAS_OPENAI:
            rospy.logwarn("[llm_planner] openai package not installed. Only fallback plans will be used.")
        else:
            self._init_openai_client()

        # Mission memory service proxy (lazy)
        self._memory_proxy = None

        # Subscriber to user prompt
        rospy.Subscriber(self.user_prompt_topic, StringMsg, self._prompt_cb, queue_size=1)

        rospy.loginfo("[llm_planner] ready. Publish prompt on %s", self.user_prompt_topic)
        rospy.loginfo("[llm_planner] memory_service: %s", self.memory_service)

    def _init_openai_client(self):
        if not self.openai_config:
            rospy.logwarn("[llm_planner] No '~openai_config' param set; using fallback only.")
            return

        try:
            api_key, model_name, temperature, max_tokens = load_openai_config(self.openai_config)
            os.environ["OPENAI_API_KEY"] = api_key  # SDK will pick this up
            self.client = OpenAI()
            self.model_name = model_name
            self.temperature = temperature
            self.max_tokens = max_tokens
            rospy.loginfo("[llm_planner] OpenAI client initialized: model=%s", self.model_name)
        except Exception as e:
            rospy.logerr("[llm_planner] Failed to init OpenAI client from %s: %s",
                         self.openai_config, e)
            self.client = None

    def _publish_status(self, text):
        msg = StringMsg(data=text)
        self.status_pub.publish(msg)

    # ------------------------------------------------------------------
    # Mission memory helpers
    # ------------------------------------------------------------------
    def _get_memory_summary(self):
        """
        Call /coral_captain/get_memory (Trigger) and return a compact
        'MISSION MEMORY:' text, or "" if unavailable.
        """
        if self._memory_proxy is None:
            try:
                rospy.wait_for_service(self.memory_service, timeout=0.5)
                self._memory_proxy = rospy.ServiceProxy(self.memory_service, Trigger)
                rospy.loginfo("[llm_planner] Connected to mission memory service: %s",
                              self.memory_service)
            except Exception as e:
                rospy.logdebug("[llm_planner] Memory service not available: %s", e)
                return ""

        try:
            resp = self._memory_proxy(TriggerRequest())
        except Exception as e:
            rospy.logwarn("[llm_planner] Error calling mission memory service: %s", e)
            return ""

        if not resp.success or not resp.message:
            return ""

        try:
            mem = json.loads(resp.message)
        except Exception:
            raw = resp.message
            if len(raw) > 500:
                raw = raw[:500] + "...(truncated)"
            return "MISSION MEMORY (raw):\n" + raw

        return self._summarize_memory_dict(mem)

    def _summarize_memory_dict(self, mem):
        """
        Convert mission memory dict into compact human-readable summary.
        Assumes keys like:
          visited_sites: [string]
          completed_actions: [ {action, args, ...}, ... ]
          photos_taken: [string or dict]
          last_event: string
          replan_events: [dict or string]
        """
        if not isinstance(mem, dict):
            return ""

        visited = mem.get("visited_sites", [])
        completed = mem.get("completed_actions", [])
        photos = mem.get("photos_taken", [])
        last_event = mem.get("last_event", "")
        replan_events = mem.get("replan_events", [])

        lines = []

        if visited:
            lines.append("Visited coral sites: " + ", ".join(map(str, visited)))
        else:
            lines.append("Visited coral sites: none yet.")

        if completed:
            lines.append("Total completed actions: {}".format(len(completed)))
            tail = completed[-5:]
            descs = []
            for c in tail:
                if isinstance(c, dict):
                    a = c.get("action", "?")
                    args = c.get("args", {})
                    site = args.get("site", args.get("footprint", None)) if isinstance(args, dict) else None
                    if site:
                        descs.append("{}(site={})".format(a, site))
                    else:
                        descs.append(a)
                else:
                    descs.append(str(c))
            lines.append("Recent actions: " + ", ".join(descs))
        else:
            lines.append("No actions completed yet in this mission.")

        if photos:
            lines.append("Photos taken: {} total".format(len(photos)))
            last_photo = photos[-1]
            if isinstance(last_photo, dict):
                label = last_photo.get("label", "?")
            else:
                label = str(last_photo)
            lines.append("Last photo label: {}".format(label))
        else:
            lines.append("No photos taken yet.")

        if last_event:
            lines.append("Last high-level event: {}".format(last_event))

        if replan_events:
            lines.append("Replans triggered: {}".format(len(replan_events)))

        summary = "MISSION MEMORY:\n" + "\n".join(lines)
        return summary

    # ------------------------------------------------------------------
    # Prompt callback
    # ------------------------------------------------------------------
    def _prompt_cb(self, msg):
        prompt_text = msg.data.strip()
        if not prompt_text:
            rospy.logwarn("[llm_planner] Received empty prompt; ignoring.")
            return

        rospy.loginfo("[llm_planner] Received user prompt: %s", prompt_text)
        self._publish_status("planning: " + prompt_text)

        memory_summary = self._get_memory_summary()
        if memory_summary:
            rospy.loginfo("[llm_planner] Mission memory summary will be included in LLM prompt.")
        else:
            rospy.loginfo("[llm_planner] No mission memory available or service not ready.")

        plan = None
        error_str = None
        latency_s = None  # <<< ADDED: track latency per prompt

        if self.client is None:
            error_str = "OpenAI client not available; using fallback."
        else:
            try:
                t0 = time.time()  # <<< start timer
                plan = self._call_llm(prompt_text, memory_summary)
                latency_s = time.time() - t0  # <<< end timer
                rospy.loginfo("[llm_planner] LLM planning latency: %.3f s", latency_s)
            except Exception as e:
                error_str = "LLM or JSON error: %s" % e
                rospy.logerr("[llm_planner] %s", error_str)
                rospy.logdebug(traceback.format_exc())

        if plan is None:
            plan = build_fallback_plan(prompt_text)

        # Attach latency into the plan JSON if available
        if latency_s is not None:
            # This key is optional and ignored by executor, but useful for logs/benchmarks
            plan["llm_latency_s"] = float(latency_s)

        plan_str = json.dumps(plan, separators=(",", ":"))
        self.plan_pub.publish(StringMsg(data=plan_str))

        # Include latency in status if we have it
        if error_str:
            status = "ok_with_fallback: " + error_str
        else:
            if latency_s is not None:
                status = "ok: plan generated in %.3f s" % latency_s
            else:
                status = "ok: plan generated"
        self._publish_status(status)

        rospy.loginfo("[llm_planner] Plan published: %s", plan_str)

    def _call_llm(self, prompt_text, memory_summary=""):
        """
        Call OpenAI model and return a validated plan (dict).
        Raises exceptions if anything goes wrong.
        """
        if self.client is None:
            raise RuntimeError("OpenAI client not initialized")

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        if memory_summary:
            messages.append({"role": "system", "content": memory_summary})

        messages.append({"role": "user", "content": prompt_text})

        completion = self.client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=messages,
        )

        content = completion.choices[0].message.content
        rospy.logdebug("[llm_planner] Raw LLM response: %s", content)

        obj = extract_json_object(content)
        plan = validate_plan(obj)
        return plan


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        node = LLMPlannerNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
