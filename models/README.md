# Models tùy chọn

Repository không chứa trọng số model bên thứ ba hay dữ liệu đã tải từ Internet.

- Cử chỉ: sau khi tạo môi trường `.venv-gesture`, chạy
  `./.venv-gesture/bin/python scripts/download_gesture_model.py` từ thư mục gốc repository.
- Nhận diện người trên robot thật: cài `requirements-person.txt`, rồi tự cung cấp
  `models/yolov8n.pt` từ nguồn Ultralytics phù hợp với điều khoản sử dụng của bạn.

Mô phỏng Gazebo vẫn chạy khi chưa có YOLO; nhận biết người trong mô phỏng dùng dữ liệu đối tượng Gazebo. Trên robot thật, không bật điều hướng tự động dựa vào camera nếu model và camera chưa được kiểm tra.
