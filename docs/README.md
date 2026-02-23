# 🪸 Coral Inspection  
### LLM-Guided Adaptive Mission Planning for Autonomous Underwater Coral Reef Monitoring

---

# 🌊 Overview

Autonomous coral reef monitoring requires:

- Long-horizon, multi-stage missions  
- Adaptation to uncertain underwater conditions  
- Geometry-aware survey strategies  
- Transparent human supervision  

Traditional waypoint-based mission scripts lack contextual reasoning and online adaptability.

This project introduces a **structured LLM-guided planning layer** that enables:

- Natural-language mission specification  
- Constrained semantic action planning  
- Persistent mission memory  
- Event-driven replanning  
- Human-in-the-loop supervision  

All validated in a **Gazebo + BlueROV2 simulation environment**.

---

# 🧠 Key Contributions

- ✅ LLM-based mission reasoning for underwater robotics  
- ✅ Constrained semantic action interface grounded in vehicle capabilities  
- ✅ Persistent mission memory for long-horizon planning  
- ✅ Event-driven adaptive replanning  
- ✅ Operator-interpretable autonomy layer  
- ✅ Simulation validation using UUV Simulator  

This work does **not** replace low-level navigation or control.  
Instead, it adds a safe, interpretable, high-level reasoning layer on top of conventional ROV autonomy.

---

# 📦 Installation

## Prerequisites

- Ubuntu 20.04 (recommended)
- ROS Noetic
- Python 3.8+
- Gazebo
- UUV Simulator

---

## 🔧 Install & Setup Environment

```bash
# Update system
sudo apt update

# Install ROS Noetic
sudo apt install ros-noetic-desktop-full

# Initialize rosdep
sudo rosdep init
rosdep update

# Source ROS automatically
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc

# Create catkin workspace
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws
catkin_make

# Source workspace automatically
echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc
source ~/.bashrc

# Install UUV Simulator
cd ~/catkin_ws/src
git clone https://github.com/uuvsimulator/uuv_simulator.git

cd ~/catkin_ws
rosdep install --from-paths src --ignore-src -r -y
catkin_make

# Clone coral_inspection repository
cd ~/catkin_ws/src
git clone https://github.com/drwa92/coral_inspection.git

# Final build
cd ~/catkin_ws
catkin_make
source devel/setup.bash

# Verify installation
rospack list | grep coral_inspection

```


# ▶️ Running the Simulation

After completing installation and building the workspace, follow the steps below.

---

## 🚀 Launch Gazebo + BlueROV2

⚠️ **Important:**  
Before starting the LLM planner, you must first launch the Gazebo simulation environment and spawn the BlueROV2 model.

```bash
cd ~/catkin_ws
source devel/setup.bash

roslaunch coral_inspection coral_llm_demo.launch


---

# 🔍 Monitoring & Mission Execution

Once Gazebo and the BlueROV2 are running, the mission framework becomes active.

The system follows this runtime sequence:

1. Receive natural-language instruction  
2. Generate semantic JSON mission plan  
3. Validate plan against allowed action set  
4. Execute actions sequentially  
5. Monitor runtime events  
6. Trigger replanning if necessary  

---

## 📡 Inspect Active ROS Topics

To view all active topics:

```bash
rostopic list

```


---

# 🔍 Runtime Topics & Mission Flow

Your launch file starts the following core nodes:

- `llm_planner`
- `coral_mission_memory`
- `coral_event_monitor`
- `coral_action_executor`

All communication happens under the namespace: /coral_captain/


---

# 🧠 Submitting a Mission Prompt

The LLM planner listens to:


You can publish a natural-language mission using:

```bash
rostopic pub /coral_captain/user_prompt std_msgs/String \
"data: 'Survey site A, inspect site B, then return home.'"

```

## ⚙️ Monitoring Execution

The `coral_action_executor` subscribes to:


It publishes execution status to:

/coral_captain/executor_status


Monitor executor progress:

```bash
rostopic echo /coral_captain/executor_status

```


When a valid semantic mission plan is published to this topic, the executor begins executing the actions sequentially.

---

### 📄 Manually Publish a Test Plan

You can manually trigger the executor by publishing a JSON plan:

```bash
rostopic pub /coral_captain/plan std_msgs/String \
"data: '{\"Plan\": [{\"action\": \"hold\"}]}'"

```
This will cause the executor to receive the plan and execute the hold action.

