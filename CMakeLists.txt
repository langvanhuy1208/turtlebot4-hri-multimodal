cmake_minimum_required(VERSION 3.8)
project(tb4_cuoiky)
find_package(ament_cmake REQUIRED)
install(DIRECTORY launch maps models config scripts urdf worlds DESTINATION share/${PROJECT_NAME})
install(PROGRAMS
  scripts/lab_catalog.py
  scripts/hri_confirmation.py
  scripts/lab_project.py
  scripts/interaction_core.py
  scripts/social_safety.py
  scripts/safety_node.py
  scripts/sim_people.py
  scripts/frontier_core.py
  scripts/frontier_explorer.py
  scripts/local_speech.py
  scripts/feedback_node.py
  scripts/mapping_ready.py
  scripts/person_perception.py
  scripts/robot_preflight.py
  scripts/session_storage.py
  scripts/project_session.py
  scripts/lab_hri_node.py
  scripts/arrival_control.py
  scripts/finger_count.py
  scripts/hri_panel.py
  scripts/panel_voice_worker.py
  scripts/continuous_voice_core.py
  scripts/continuous_voice_worker.py
  scripts/slam_scan_lab.py
  scripts/mapping_geometry.py
  scripts/lab_sim_ready.py
  scripts/lab_teleop.py
  scripts/keyboard_control.py
  scripts/robot3_keyboard_panel.py
  scripts/voice_navigation_node.py
  scripts/voice_input.py
  scripts/voice_audio.py
  scripts/voice_demo_ready.py
  scripts/gesture_core.py
  scripts/gesture_recognition_node.py
  scripts/download_gesture_model.py
  scripts/semantic_map.py
  scripts/segment_map.py
  scripts/map_from_world.py
  scripts/scan_retimestamp.py
  scripts/odom_tf_broadcaster.py
  DESTINATION lib/${PROJECT_NAME})
ament_package()
