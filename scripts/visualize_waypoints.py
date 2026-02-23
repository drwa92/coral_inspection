#!/usr/bin/env python3
# Publish CSV survey waypoints as nav_msgs/Path and visualization markers for RViz.
# Usage:
#   rosrun coral_inspection visualize_waypoints.py _csv_glob:='/absolute/path/to/*.csv' _frame_id:=world
#
import glob, csv, os, re
import rospy
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped, Point
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import ColorRGBA

SITE_TAG_RE = re.compile(r'_(A|B|C|D)(?:_|$)')

def site_suffix(name):
    m = SITE_TAG_RE.search(name)
    return m.group(1) if m else None

def color_for_site(name):
    s = site_suffix(name)
    if s == 'A': return ColorRGBA(1.0, 0.0, 0.0, 1.0)  # red
    if s == 'B': return ColorRGBA(0.0, 1.0, 0.0, 1.0)  # green
    if s == 'C': return ColorRGBA(0.0, 0.0, 1.0, 1.0)  # blue
    if s == 'D': return ColorRGBA(1.0, 1.0, 0.0, 1.0)  # yellow
    return ColorRGBA(1.0, 1.0, 1.0, 1.0)              # white fallback

def load_csv(csv_path):
    pts = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row.get('x_m', row.get('x', '0')))
                y = float(row.get('y_m', row.get('y', '0')))
                z = float(row.get('z_m', row.get('z', '0')))
            except Exception:
                continue
            pts.append((x,y,z))
    return pts

def main():
    rospy.init_node('visualize_waypoints')
    csv_glob = rospy.get_param('~csv_glob', '')
    frame_id = rospy.get_param('~frame_id', 'world')
    line_width = float(rospy.get_param('~line_width', 0.1))
    marker_ns = rospy.get_param('~marker_ns', 'survey_markers')

    if not csv_glob:
        rospy.logerr('Parameter ~csv_glob is required (e.g., /home/user/coral_inspection/data/*.csv)')
        return

    csv_files = sorted(glob.glob(os.path.expanduser(csv_glob)))
    if not csv_files:
        rospy.logerr('No CSV files matched: %s', csv_glob)
        return
    rospy.loginfo('Found %d CSV files', len(csv_files))

    path_pubs = {}
    marker_pub = rospy.Publisher('survey/markers', MarkerArray, queue_size=1, latch=True)

    marr = MarkerArray()
    mid = 0

    for csv_path in csv_files:
        site_name = os.path.splitext(os.path.basename(csv_path))[0]  # e.g., coral_bed_A_survey
        color = color_for_site(site_name)

        # Publish Path
        path_topic = 'survey/path/' + site_name
        path_pub = rospy.Publisher(path_topic, Path, queue_size=1, latch=True)
        pts = load_csv(csv_path)

        path = Path()
        path.header.frame_id = frame_id
        for (x,y,z) in pts:
            ps = PoseStamped()
            ps.header.frame_id = frame_id
            ps.pose.position.x = x
            ps.pose.position.y = y
            ps.pose.position.z = z
            ps.pose.orientation.w = 1.0
            path.poses.append(ps)
        rospy.sleep(0.05)
        path_pub.publish(path)
        path_pubs[site_name] = path_pub
        rospy.loginfo('Published %d poses on /%s', len(path.poses), path_topic)

        # Points Marker
        m_pts = Marker()
        m_pts.header.frame_id = frame_id
        m_pts.ns = marker_ns
        m_pts.id = mid; mid += 1
        m_pts.type = Marker.POINTS
        m_pts.action = Marker.ADD
        m_pts.scale.x = line_width*2.0
        m_pts.scale.y = line_width*2.0
        m_pts.color = color
        m_pts.pose.orientation.w = 1.0
        for (x,y,z) in pts:
            m_pts.points.append(Point(x=x, y=y, z=z))
        marr.markers.append(m_pts)

        # Line strip Marker
        m_line = Marker()
        m_line.header.frame_id = frame_id
        m_line.ns = marker_ns
        m_line.id = mid; mid += 1
        m_line.type = Marker.LINE_STRIP
        m_line.action = Marker.ADD
        m_line.scale.x = line_width
        m_line.color = color
        m_line.pose.orientation.w = 1.0
        for (x,y,z) in pts:
            m_line.points.append(Point(x=x, y=y, z=z))
        marr.markers.append(m_line)

    rospy.sleep(0.1)
    marker_pub.publish(marr)
    rospy.loginfo('Published MarkerArray with %d markers', len(marr.markers))
    rospy.loginfo('Ready. In RViz, add Marker (/survey/markers) and Path topics as needed.')

    rospy.spin()

if __name__ == '__main__':
    main()
