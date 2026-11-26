# Hệ thống tương tác người–robot đa phương thức trên TurtleBot 4

> Tài liệu này mô tả phiên bản hiện hành của dự án. Hướng dẫn cài/chạy nằm ở [README](../README.md); kết nối robot thật xem [KET_NOI_ROBOT3.md](KET_NOI_ROBOT3.md).

## Mục tiêu

Nghiên cứu và phát triển hệ thống để TurtleBot 4 nhận lệnh bằng **giọng nói** và **cử chỉ tay**, điều hướng đến địa điểm đã dạy trên map, và phản hồi an toàn trong môi trường có người hay vật cản thay đổi.

Hệ thống chạy được ở hai chế độ:

- **Mô phỏng:** ROS 2 Humble, Ignition Gazebo Fortress, map mê cung hoặc phòng lab.
- **Robot thật:** dùng LiDAR, odometry, TF và camera của TurtleBot 4; không khởi động Gazebo hoặc dữ liệu cảm biến giả.

## Kiến trúc

| Khối | Nhiệm vụ |
|---|---|
| SLAM Toolbox / AMCL | Quét map mới; sau khi lưu map thì định vị lại trên map đã lưu. |
| Nav2 | Lập đường khả thi theo costmap, theo dõi đường và lập kế hoạch lại khi vật cản mới xuất hiện. |
| Điều khiển đa phương thức | Whisper tiếng Việt nhận giọng nói liên tục; MediaPipe nhận cử chỉ webcam; bảng điều khiển nhận nút/keyboard. |
| Bộ hợp nhất lệnh | Ghép lệnh giọng nói–cử chỉ cùng mục tiêu trong cửa sổ 0,8 giây; xung đột hoặc lệnh không rõ sẽ hỏi lại. |
| Catalog map/địa điểm | Lưu map, điểm, tên gọi khác và ánh xạ cử chỉ; catalog gắn hash của map để không dùng nhầm tọa độ trên map khác. |
| An toàn xã hội | Cảnh báo, giảm tốc, dừng khi người quá gần; chờ vùng trống ổn định rồi gửi lại mục tiêu cũ. |
| Cổng vận tốc cuối | Tất cả vận tốc Nav2/teleop đều qua `social_safety`; mất LiDAR, dữ liệu người hoặc lệnh mới sẽ phát vận tốc 0. |

## Quy tắc giao tiếp hiện hành

- Nói “Đi đến …” hoặc giơ **1 / 2 / 3 ngón**: robot nhận lệnh và đi ngay nếu đích hợp lệ.
- **Ngón cái**, câu “Xác nhận” hoặc nút xác nhận: chỉ dùng để chốt thao tác **lưu map, lưu/sửa/xóa địa điểm hay tên gọi khác**.
- Khi tới đích, robot dừng và nói “Đã đến …”; **không yêu cầu xác nhận đã đến**.
- Nắm tay/lòng bàn tay hoặc “Dừng lại”: hủy vận tốc, hủy mục tiêu và yêu cầu đang chờ.
- Hai kênh cùng đích: gộp thành một lệnh. Hai kênh khác đích, nhiều tay trong ảnh, tên chưa có hoặc ASR tự tin thấp: robot không tự đoán mà hỏi lại.
- Ở chế độ ồn/nhiều người, người dùng gọi “Robot” trước câu lệnh. Hệ thống chưa xác thực danh tính hay tách hoàn hảo hai người nói chồng nhau.

## Luồng thực hiện đề tài

1. **Kết nối:** cấu hình Wi-Fi/DDS, domain và namespace; chỉ kiểm tra scan/odom/TF trước khi gửi vận tốc.
2. **Quét map:** chọn quét tự động bằng frontier hoặc lái tay. Map phục hồi được tự lưu sau khi dừng quét; map chính thức cần người dùng đặt tên và xác nhận.
3. **Dạy địa điểm:** lưu vị trí hiện tại của robot hoặc dùng công cụ `Publish Point` trên RViz; đặt tên, bí danh, cập nhật hoặc xóa có xác nhận.
4. **Điều hướng:** gọi bằng giọng nói, cử chỉ hoặc bảng; Nav2 xử lý đường đi và vật cản động trong costmap.
5. **Tương tác xã hội và an toàn:** vùng cảnh báo mặc định 1,5 m, vùng dừng 0,8 m; tham số phải hiệu chỉnh lại trên robot thật.
6. **Đánh giá:** ghi nhận tỷ lệ hoàn thành, sai số đến đích, thời gian phản hồi, số lần hỏi lại và hành vi dừng/đi tiếp.

## Chạy để học trên mô phỏng

Từ thư mục gốc repository sau khi đã build:

```bash
# Tạo một map SLAM mới trong mê cung
bash scripts/start_project.sh sim --scene maze --new-scan

# Hoặc chạy map mê cung mẫu có sẵn
bash scripts/run_maze.sh
```

Trong bảng điều khiển, chọn **QUÉT TỰ ĐỘNG** hoặc **THỦ CÔNG**. Sau khi quét xong: **DỪNG QUÉT** → đặt tên → **LƯU MAP** → xác nhận. Sau đó lưu địa điểm từ vị trí robot hoặc `Publish Point` trong RViz, rồi thử lệnh giọng nói/cử chỉ.

## Đưa sang robot thật

Không dùng map mô phỏng cho phòng thật. Trình tự tối thiểu:

1. Làm theo [KET_NOI_ROBOT3.md](KET_NOI_ROBOT3.md) để kiểm tra LiDAR, odometry và teleop tốc độ thấp.
2. Chỉnh `config/profiles/robot.yaml` cho đúng namespace, topic RGB/CameraInfo và ngưỡng an toàn của robot.
3. Chạy `bash scripts/start_project.sh robot --profile config/profiles/robot.yaml --new-scan` để quét map thật.
4. Lưu map, mở lại map và dùng **2D Pose Estimate** trong RViz trước bất kỳ lệnh điều hướng nào.
5. Chạy `scripts/robot_preflight.py` khi phiên đã mở. Chỉ thử đích gần ở tốc độ thấp khi kiểm tra trả về `passed: true`.

## An toàn, quyền riêng tư và giới hạn

- Luôn có người giám sát, vùng chạy thông thoáng và quyền dừng vật lý khi thử robot thật. Không chạy teleop, SLAM/Nav2 cũ và phiên dự án mới cùng một namespace.
- Âm thanh/video không được lưu mặc định. Bật `TB4_LOG_TRANSCRIPTS=1` mới ghi transcript; cần được sự đồng ý trước khi thu dữ liệu người dùng.
- Nhận biết người trong Gazebo dựa vào dữ liệu mô phỏng. Adapter YOLO RGB–LiDAR cho robot thật mới được kiểm tra nạp model/suy luận cơ bản, chưa được đánh giá độ chính xác ngoài đời và không phải cảm biến 360°.
- Nav2 tối ưu chi phí và khoảng trống theo bản đồ/costmap hiện thời, không cam kết đường ngắn nhất tuyệt đối trong mọi tình huống thay đổi.

## Kết quả cần báo cáo

Mỗi thí nghiệm nên ghi: điều kiện môi trường, loại đầu vào, map/đích, quãng đường, thời gian, sai số đến đích, số lần hỏi lại, phản hồi an toàn, lỗi và cách phục hồi. So sánh ít nhất: điều khiển giọng nói, cử chỉ, hai kênh cùng mục tiêu và hai kênh mâu thuẫn.
