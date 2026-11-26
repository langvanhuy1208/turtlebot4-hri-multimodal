# TurtleBot 4 — Tương tác người–robot đa phương thức

ROS 2 Humble · Ignition Gazebo Fortress · SLAM Toolbox · Nav2 · Whisper tiếng Việt · MediaPipe · phản hồi tiếng Việt cục bộ.

**Lệnh giọng nói hoặc 1/2/3 ngón → điều hướng → thông báo “Đã đến …” → tự hoàn thành.** Không xác nhận trước khi xuất phát hoặc sau khi đến. Ngón cái, câu “Xác nhận” và nút **XÁC NHẬN LƯU** chỉ dùng khi lưu bản đồ, địa điểm hoặc thay đổi tên gọi.

## Cài và chạy sau khi clone

Yêu cầu chính: Ubuntu 22.04, ROS 2 Humble, các gói TurtleBot 4/Gazebo Fortress, Nav2 và SLAM Toolbox. Cài TurtleBot 4 theo [hướng dẫn chính thức](https://turtlebot.github.io/turtlebot4-user-manual/) trước; repository này không cài hoặc thay đổi hệ điều hành của robot.

```bash
git clone https://github.com/langvanhuy1208/turtlebot4-hri-multimodal.git
cd turtlebot4-hri-multimodal

source /opt/ros/humble/setup.bash
rosdep install --from-paths . --ignore-src -r -y
colcon build --packages-select tb4_cuoiky --symlink-install
source install/setup.bash
```

Để bật giọng nói/cử chỉ trên laptop, cài thêm các môi trường cục bộ sau. Mô phỏng vẫn có thể học phần ROS/Nav2 khi chưa bật micro hoặc webcam.

```bash
python3 -m venv .venv-voice
.venv-voice/bin/pip install -r requirements-voice.txt

python3 -m venv .venv-gesture
.venv-gesture/bin/pip install -r requirements-gesture.txt
.venv-gesture/bin/python scripts/download_gesture_model.py
```

Khởi động mô phỏng mê cung mới:

```bash
bash scripts/start_project.sh sim --scene maze --new-scan
```

Mọi đường dẫn dưới đây là **tương đối từ thư mục gốc repository**. Tài liệu kết nối robot thật: [docs/KET_NOI_ROBOT3.md](docs/KET_NOI_ROBOT3.md). Kiến trúc và luồng HRI: [docs/DU_AN_HRI_LAB.md](docs/DU_AN_HRI_LAB.md).

## Tự lưu, mở lại và xóa địa điểm

Khi quét tự động kết thúc hoặc chọn **DỪNG QUÉT**, robot đứng yên sẽ tự ghi một **map phục hồi** vào `maps/recovery/`. Bản tự lưu là ảnh occupancy của phần đã quét, không phải pose graph để tiếp tục đúng phiên SLAM cũ. Không tự ghi đè map có tên. Muốn hoàn tất map chính thức, nhập tên, **LƯU MAP** và xác nhận như trước.

Lần sau chạy cùng lệnh `start_project.sh sim --scene maze`, phần mềm tự mở map hợp lệ gần nhất của đúng cảnh đó và nạp địa điểm đã lưu; không quét lại. Nếu chưa có map hợp lệ thì bắt đầu quét mới. Cảnh lab/maze và các namespace robot thật được lưu riêng. Với robot thật, mở lại map vẫn cần **2D Pose Estimate** để xác định vị trí robot hiện tại; không tự áp dụng vị trí cũ sau khi robot đã được di chuyển.

Muốn quét lại từ đầu, thêm `--new-scan`. Muốn chỉ định map khác, dùng `--catalog "maps/user_saved/TEN_MAP/destinations.yaml"` trong đúng cảnh/robot.

Trong tab **MAP VÀ ĐỊA ĐIỂM**, chọn tên trong danh sách → **XÓA ĐỊA ĐIỂM ĐÃ CHỌN** → **XÁC NHẬN XÓA** (hoặc nói “Xác nhận”, giơ ngón cái). Cũng có thể nói “Xóa địa điểm cửa phòng”. Trước khi xác nhận, dữ liệu vẫn được giữ. Sau khi xóa, tên gọi, dấu trên RViz và ánh xạ cử chỉ tới địa điểm đó được cập nhật; đóng/mở lại không làm địa điểm đã xóa xuất hiện lại.

## Khởi động dự án: Gazebo → quét → lưu → đặt địa điểm tùy ý

Đây là luồng dành cho một phiên làm việc mới, không nạp sẵn tọa độ ba bàn:

```bash
bash scripts/stop_sim.sh
bash scripts/start_project.sh sim --scene maze --new-scan
```

Cùng lúc mở Gazebo 3D, RViz và bảng điều khiển. Gazebo có toàn bộ mê cung; RViz hiển thị **bản đồ SLAM đang quét**, mở rộng theo LiDAR, không nạp ảnh map tham chiếu làm kết quả quét.

1. Ở tab **ĐIỀU KHIỂN**, chọn **QUÉT TỰ ĐỘNG** hoặc **THỦ CÔNG**. Khi thủ công, giữ nút mũi tên hoặc W/A/S/D lúc cửa sổ điều khiển có focus; không điều khiển khi đang gõ tên. Thả phím, rời nút hoặc mất focus sẽ dừng.
2. Chọn **DỪNG QUÉT**, chờ xe đứng yên. Sang tab **MAP VÀ ĐỊA ĐIỂM**, nhập tên map và bấm **LƯU MAP**; cũng có thể nói “Lưu bản đồ phòng lab”.
3. Giơ ngón cái, nói “Xác nhận” hoặc bấm **XÁC NHẬN LƯU**. Phần mềm lưu map, dừng SLAM, chuyển sang AMCL và giữ nguyên Gazebo; không cần khởi động lại thế giới hay đưa xe về điểm đầu.
4. Khi giao diện báo map đã lưu và đủ dữ liệu định vị/odometry, tự đặt địa điểm theo một trong hai cách dưới. Phiên mới có catalog trống, không ép dùng ba vị trí mẫu.

**Cách A — lưu vị trí xe:** chọn **THỦ CÔNG**, đưa xe đến chỗ mong muốn, thả phím cho xe đứng yên. Nhập tên ở tab map và bấm **LƯU VỊ TRÍ XE**, hoặc nói “Lưu địa điểm cửa phòng”. Xác nhận để lưu.

**Cách B — chọn trên bản đồ:** trong RViz bấm **Publish Point**, click vùng trắng muốn đặt đích. Một dấu màu xanh lam–lục hiện ở điểm được chọn. Nhập tên ở tab map, bấm **LƯU ĐIỂM ĐÃ CHỌN**, rồi xác nhận. Cũng có thể nói “Lưu điểm đã chọn quầy lễ tân”. Click điểm chỉ chọn tọa độ, không ra lệnh cho xe chạy. Điểm ngoài map, vùng chưa biết hoặc quá sát vật cản bị từ chối; điểm trống nhưng không có đường tới sẽ được Nav2 báo thất bại khi điều hướng.

Các tên đã lưu xuất hiện trong danh sách. Chọn tên và bấm **ĐI ĐẾN ĐỊA ĐIỂM ĐÃ CHỌN**, hoặc nói “Đi đến cửa phòng”. Ba cử chỉ 1/2/3 ngón được gán dần theo các địa điểm bạn tạo, lưu cùng catalog. Mục tiêu mới tự chuyển từ điều khiển tay sang điều hướng. Đến đích chỉ phản hồi, không yêu cầu xác nhận.

Muốn dùng phòng nhỏ thay mê cung, thay `--scene maze` bằng `--scene lab`. Muốn bắt đầu quét tự động ngay, thêm `--auto`. Mặc định chờ người dùng chọn chế độ. `--no-ui --no-gazebo-gui` chỉ dành cho kiểm thử không mở cửa sổ.

**Cùng luồng trên robot thật sau khi kết nối:** mở terminal đúng DDS/domain của robot, chỉnh namespace và topic cảm biến trong profile rồi chạy:

```bash
bash scripts/start_project.sh robot --profile config/profiles/robot.yaml
```

Chế độ robot không khởi chạy Gazebo, `/clock`, odom TF giả hoặc dữ liệu người giả. Nó dùng LiDAR/odometry/TF/RGB thực, quét SLAM, lưu map và chuyển sang AMCL tại chính vị trí hiện tại rồi mở cùng giao diện đặt địa điểm. Không tự kết nối hay sửa Wi-Fi/DDS. Nếu robot đã có SLAM/Nav2/cùng namespace đang chạy, cần dừng phiên trùng trước. Phần cứng, đồng bộ thời gian, topic camera/CameraInfo và vùng an toàn vẫn phải kiểm chứng trên robot thật; đợt kiểm thử hiện tại chỉ chạy mô phỏng.

Map ở `maps/user_saved/<tên>/`, địa điểm trong `destinations.yaml`; đường dẫn phiên và báo cáo chuyển trạng thái ở `results/latest_project_session.txt`. Dừng mô phỏng bằng `bash scripts/stop_sim.sh`; phiên robot thật chạy foreground, dùng Ctrl+C trong terminal của phiên đó.

## Mở đúng map mê cung có sẵn 20 × 20 m

```bash
bash scripts/stop_sim.sh
bash scripts/run_maze.sh
```

Map đầy đủ trong `maps/bai7/map.pgm`, khớp môi trường `worlds/maze_hri.sdf`. Ba đích và các địa điểm dạy thêm lưu riêng ở `maps/maze/destinations.yaml`. RViz dùng `config/nav_maze.rviz` để thấy toàn bộ mê cung. Đây là map tham chiếu có sẵn, không phải bản SLAM mới. Các chức năng giọng nói, cử chỉ, xác nhận lưu và bộ lọc an toàn vẫn hoạt động.

## Chạy mô phỏng trên bản đồ có ba bàn

```bash
bash scripts/resume_lab.sh
```

Mở Gazebo headless, RViz, bảng điều khiển nghe micro và webcam. Dùng ROS domain 98 cùng DDS loopback, tách khỏi robot thật. Muốn chạy không mở micro/camera: `CUOIKY_HEADLESS=true bash scripts/resume_lab.sh`.

```bash
bash scripts/stop_sim.sh
```

## Điều khiển và hội thoại

| Đầu vào | Hành vi |
|---|---|
| “Đi đến bàn số 1 / 2 / 3” | Chọn đích, không cần bấm thu âm |
| 1 ngón trỏ / 2 ngón trỏ–giữa / 3 ngón trỏ–giữa–áp út | Chọn ba địa điểm đã gán |
| Lòng bàn tay, nắm tay, “Dừng lại”, nút DỪNG | Ưu tiên hủy chuyển động và yêu cầu đang chờ |
| Hai kênh cùng một đích | Ghép thành một lệnh |
| Hai kênh khác đích | Hỏi lại; nói tên đích muốn chọn |
| Tên đích chưa có hoặc không rõ | Hỏi lại, không tự đoán hay tự lưu |
| “Lưu địa điểm quầy lễ tân” | Đề nghị ghi tọa độ hiện tại từ TF |
| “Cập nhật địa điểm quầy lễ tân” | Đề nghị thay tọa độ đã lưu |
| “Gọi quầy lễ tân là bàn kiểm tra” | Dạy tên gọi khác cho cùng một vị trí |
| “Xóa địa điểm quầy lễ tân” | Đề nghị xóa địa điểm |
| “Lưu bản đồ phòng lab” | Đề nghị lưu bản đồ đang có trên `/map` |
| Ngón cái / “Xác nhận” / nút XÁC NHẬN LƯU | Ghi thay đổi đang chờ trong 30 giây |

Trước mỗi cử chỉ, bỏ tay khỏi khung ít nhất 0,35 giây. Cử chỉ giữ nguyên không lặp lệnh. Nhiều bàn tay trong khung được coi là mơ hồ, không chọn đích. Đây chưa phải xác thực danh tính người điều khiển.

Cửa sổ ghép lệnh mặc định 0,8 giây. Nếu micro đang thu/ASR đang xử lý, cử chỉ chờ kết quả tối đa 12 giây để giọng nói đến muộn vẫn được đối chiếu. Lệnh dừng không chờ cửa sổ này. Khi robot đã chạy, muốn đổi đích cần dừng trước.

Robot phải đứng yên và odometry còn mới khi yêu cầu/xác nhận lưu. Lưu địa điểm và điều hướng cần TF định vị còn mới. Yêu cầu lưu có ID riêng; nút cũ hoặc xác nhận lặp không ghi lại dữ liệu. Vị trí phải là ô trống và cách vật cản tối thiểu theo catalog. Ba ánh xạ cử chỉ được cập nhật khi dạy thêm địa điểm và lưu cùng catalog; có thể đặt rõ `gesture_destinations` khi chạy node.

## Tự quét hoặc quét thủ công

Dừng phiên cũ trước, rồi chọn:

```bash
bash scripts/run_mapping.sh auto
# Hoặc:
bash scripts/run_mapping.sh manual
```

Thuật toán tự động tìm biên giữa ô trống đã biết và vùng chưa biết, chọn biên có thể tiếp cận, rồi dùng Nav2 để đến đó. Không đọc bản đồ tham chiếu hoặc tuyến điểm đặt sẵn. Dừng khi hết biên chưa thử có thể tiếp cận hoặc hết giới hạn 10 phút. Không bảo đảm mọi góc khuất đều được khám phá; kết thúc cần xem lại bản đồ.

Trong phiên quét, nói “Robot tự động quét”, “Robot điều khiển thủ công”, “Robot dừng quét” hoặc dùng nút tương ứng. Chuyển sang thủ công sẽ hủy mục tiêu tự động và chờ action kết thúc trước khi nhận vận tốc thủ công. Mở terminal khác:

```bash
source scripts/sim_env.sh
python3 scripts/lab_teleop.py --topic /cmd_vel_manual
```

Giữ W/S để tiến/lùi, A/D để quay, Space dừng, Q thoát; ngừng lặp phím thì dừng trong tối đa 0,35 giây. Mọi vận tốc đều qua bộ lọc an toàn.

Dừng quét và chờ xe đứng yên. Nói **“Lưu bản đồ phòng lab”**, rồi giơ ngón cái hoặc nói **“Xác nhận”**. Map ở `maps/user_saved/phong_lab/`, gồm ảnh, YAML, catalog và thông tin hệ tọa độ. Map mới không ghi đè map cùng tên. Đường dẫn map mới nhất ở `results/latest_user_map.txt`.

Dừng phiên quét và mở map đã lưu:

```bash
bash scripts/stop_sim.sh
bash scripts/resume_lab.sh "$PWD/maps/user_saved/phong_lab"
```

Sau đó dạy các địa điểm bằng giọng nói. Vị trí quét ban đầu đã được lưu để định vị lại cùng điểm sinh robot trong mô phỏng. Trên robot thật phải xác định vị trí ban đầu thực tế, không áp dụng lại vị trí sinh mô phỏng. `scripts/run_slam_workflow.sh` vẫn giữ tuyến quét định sẵn trước đây để tham khảo/đối chiếu.

## Người, vật cản và môi trường thay đổi

- Trong phạm vi cảnh báo mặc định 1,5 m: giảm vận tốc còn 35% và phản hồi. Trong 0,8 m: dừng. Người đứng yên vẫn là người.
- Vùng phải trống ổn định 1 giây mới tiếp tục. Nhiệm vụ bị tạm dừng sẽ hủy action hiện tại, chờ kết quả cuối, rồi lập đường mới đến đúng đích cũ. Nếu người dùng hủy lúc chờ, robot không tự chạy lại.
- Vật thể mới trên đường được LiDAR đưa vào costmap; Nav2 lập lại đường đi. Nếu không tìm được đường hoặc thất bại, robot báo lỗi và chờ lệnh. Vật quá gần dưới 0,35 m sẽ chặn chuyển động; không cố lách khỏi tình huống chưa đủ an toàn.
- Mất dữ liệu người hoặc LiDAR quá 1 giây, hoặc lệnh vận tốc quá 0,5 giây: đầu ra vận tốc bằng 0. Bộ lọc cuối là nguồn xuất `/cmd_vel`; Nav2, hành vi phục hồi và điều khiển tay phải đi qua đầu vào đã kiểm soát.
- Bản đồ đã lưu là nền tĩnh, costmap xử lý thay đổi tạm thời. Thay đổi cấu trúc lớn cần quét/lưu phiên bản mới và kiểm tra/dạy lại địa điểm. Catalog gắn mã SHA-256 của map; sửa map ngoài luồng sẽ bị từ chối thay vì dùng tọa độ cũ một cách âm thầm.

Nav2 tối ưu đường khả thi theo chi phí, khoảng trống và vật cản cập nhật. Không bảo đảm đường ngắn nhất tuyệt đối trong môi trường thay đổi. Các ngưỡng khoảng cách là cấu hình thử nghiệm, cần hiệu chỉnh trên phần cứng.

**Nhận biết người trong mô phỏng lấy nhãn và khoảng cách từ Gazebo**, có mô hình va chạm thật. Đây là dữ liệu chuẩn của mô phỏng để kiểm tra hành vi, không phải kết quả nhận diện người bằng camera. Adapter `person_perception.py` cho robot dùng YOLO RGB và ghép khoảng cách LiDAR theo hướng; đã kiểm tra tải model/suy luận ảnh trống, chưa kiểm chứng độ chính xác trên camera TurtleBot. Camera chỉ phân loại người trong trường nhìn; không được coi là cảm biến người 360°.

## Phòng ồn, nhiều người và quyền riêng tư

Bật **“Phòng ồn / nhiều người: gọi Robot trước mỗi câu lệnh”**. Lệnh độ tin cậy thấp yêu cầu nói lại hoặc dùng cử chỉ. Tên đích vẫn được đối chiếu catalog; không suy đoán gần đúng. Có ô gõ lệnh/trả lời khi micro không rõ.

Whisper, MediaPipe, YOLO và tổng hợp giọng nói đều xử lý cục bộ. Có nút tạm dừng micro và camera; tạm dừng camera giải phóng thiết bị. Âm thanh/video không lưu mặc định. Chỉ khi đặt `TB4_LOG_TRANSCRIPTS=1` mới ghi file transcript; log ROS vẫn có thể chứa lệnh/tên địa điểm. `results/live_input/` là các bản thu thử cũ đã có từ trước; không phải bản thu liên tục mới.

Chưa tách giọng hai người nói chồng nhau hoặc xác thực người nói. Kiểm thử nhiễu hiện dùng hai bản thu cũ cộng nhiễu Gaussian: SNR 20 dB đúng 2/2, 10 dB đúng 1/2, 0 dB đúng 0/2. Các câu nhận sai không phân giải thành đích hợp lệ. Đây là mẫu nhỏ, không đại diện cho phòng đông người thực tế.

## Chuyển sang TurtleBot thật

Giữ nguyên các module HRI, catalog, action Nav2 và bộ lọc vận tốc. Profile ở `config/profiles/robot.yaml` đặt namespace, nguồn ảnh và các ngưỡng; chỉnh theo robot thực tế. Không chạy world Gazebo, nguồn người giả hoặc bộ phát odom→base của mô phỏng trên robot thật.

1. Cấu hình Wi-Fi/DDS/domain theo [hướng dẫn kết nối](docs/KET_NOI_ROBOT3.md). Không dùng `sim_env.sh` cho robot thật.
2. Quét map phòng thật, lưu và tạo catalog tương ứng; không dùng tọa độ ba bàn mô phỏng.
3. Trong terminal đã cấu hình DDS robot, chạy:

```bash
bash scripts/run_robot_hri.sh config/profiles/robot.yaml /duong/dan/map_that/destinations.yaml
```

Launch mở Nav2, định vị, HRI, adapter người, bộ lọc, bảng điều khiển, webcam và RViz theo namespace. Định vị robot thật bằng **2D Pose Estimate** ở RViz trước khi điều hướng. Khung TF hiện dùng tên `map`, `odom`, `base_link`; cần đối chiếu cây TF robot, không chỉ namespace.

Kiểm tra chỉ đọc ở terminal cùng môi trường:

```bash
python3 scripts/robot_preflight.py --profile config/profiles/robot.yaml \
  --catalog /duong/dan/map_that/destinations.yaml
```

Cần xác minh topic ảnh/CameraInfo, đồng bộ thời gian, TF cảm biến, độ chính xác khoảng cách, nguồn xuất vận tốc duy nhất và thử chạy chậm trên robot thật. Profile robot **chưa được kiểm thử chuyển động trên phần cứng trong đợt này**. Không thể bảo đảm chỉ biết IP là chạy đúng ngay. Model người cục bộ ở `models/yolov8n.pt`; phụ thuộc thêm trong `requirements-person.txt`.

## Build và kiểm thử

```bash
source /opt/ros/humble/setup.bash
colcon build --packages-select tb4_cuoiky --symlink-install
source install/setup.bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_*.py
```

ROS/action với Nav2 giả, không xuất vận tốc:

```bash
ROS_DOMAIN_ID=96 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
CYCLONEDDS_URI="file://$PWD/config/cyclonedds_local.xml" \
python3 tests/ros_lab_hri_smoke.py
```

Di chuyển trong Gazebo, gồm ba đích và hoàn thành tự động:

```bash
CUOIKY_AUTOTEST=true bash scripts/resume_lab.sh
```

Các kịch bản còn lại chạy trong đúng phiên tương ứng, sau `source scripts/sim_env.sh`: `tests/gazebo_people_scenario.py`, `tests/gazebo_obstacle_scenario.py`, `tests/mapping_scenario.py`, `tests/manual_mapping_scenario.py`, `tests/place_learning_scenario.py`. Không mở micro/webcam khi chạy thử tự động để tránh lệnh bên ngoài. Các bài thử này thực sự có thể cho robot mô phỏng di chuyển.

Bằng chứng hiện hành:

| File trong `results/` | Phạm vi |
|---|---|
| `interaction_ros_results.json` | Hội thoại, hai kênh, ASR đến muộn, xác nhận lưu, tạm dừng/tiếp tục; Nav2 giả |
| `direct_arrival_sim/navigation_results.json` | Ba đích, Gazebo + Nav2 + AMCL; không xác nhận đến nơi |
| `people_gazebo_results.json` | Người gần, dừng, người đứng yên và tiếp tục |
| `obstacle_gazebo_results.json` | Vật cản mới, đường vòng từ LiDAR/costmap và tới đích |
| `mapping_frontier_results.json` | Quét biên SLAM, quãng đường, diện tích và xác nhận lưu map |
| `manual_mapping_results.json` | Chọn nguồn vận tốc theo chế độ thủ công/dừng |
| `place_learning_gazebo_results.json` | Mở map mới, dạy/cập nhật/tên gọi địa điểm và điều hướng |
| `noise_replay_results.json` | Đo ASR với nhiễu tổng hợp, không phải thử phòng đông người |

Các test Gazebo dùng văn bản/nhãn cử chỉ tự động để thử luồng điều khiển; không giả làm lần thử micro/webcam trực tiếp mới. Báo cáo cũ nói “xác nhận đã đến” chỉ là dữ liệu lịch sử, không mô tả luồng hiện tại.
