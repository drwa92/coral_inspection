# 🪸 Coral Inspection  
### LLM-Guided Adaptive Mission Planning for Autonomous Underwater Coral Reef Monitoring


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
- ✅ Simulation validation using uuv_simulator  

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

## 1️⃣ Install ROS Noetic

```bash
sudo apt update
sudo apt install ros-noetic-desktop-full


mkdir -p ~/catkin_ws/src
cd ~/catkin_ws
catkin_make
source devel/setup.bash


---

##  Install & Setup Environment

```bash
# Update system
sudo apt update

# Install ROS Noetic
sudo apt install ros-noetic-desktop-full

# Initialize rosdep
sudo rosdep init
rosdep update

# Source ROS
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc

# Create catkin workspace
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws
catkin_make

# Source workspace
echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc
source ~/.bashrc

# Install uuv_simulator
cd ~/catkin_ws/src
git clone https://github.com/uuvsimulator/uuv_simulator.git
cd ~/catkin_ws
rosdep install --from-paths src --ignore-src -r -y
catkin_make

# Clone coral_inspection
cd ~/catkin_ws/src
git clone https://github.com/drwa92/coral_inspection.git


# Final build
cd ~/catkin_ws
catkin_make
source devel/setup.bash

# Verify installation
rospack list | grep coral_inspection

---




# ▶️ Running the Simulation

After completing installation and building the workspace, follow the steps below.

---

##  Source the Workspace

⚠️ Important:
Before starting the LLM planner, you must first launch the Gazebo simulation environment and spawn the BlueROV2 model.


```bash
cd ~/catkin_ws
source devel/setup.bash

roslaunch coral_inspection coral_llm_demo.launch

