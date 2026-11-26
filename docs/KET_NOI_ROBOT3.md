# Kết nối TurtleBot 4 thật — robot3 và robot khác

Repository public này **không chứa IP, Wi-Fi, mật khẩu hay địa chỉ Discovery Server của phòng lab**. ROS 2 Humble, Fast DDS và namespace `/robot3` là cấu hình ví dụ; luôn đọc giá trị thực từ robot trước khi kết nối. Việc từng nhận được scan/odometry trong một lần kiểm tra không thay thế thử chuyển động an toàn.

Trong terminal mới:

```bash
cd "$(git rev-parse --show-toplevel)"
cp config/robot_connection.env.example config/robot_connection.env
# Sửa ROS_DOMAIN_ID, RMW_IMPLEMENTATION, ROBOT_NAMESPACE và ROS_DISCOVERY_SERVER
# trong config/robot_connection.env theo robot thật. File này không được đưa lên GitHub.
source scripts/robot3_env.sh
/usr/bin/python3 scripts/lab_project.py doctor --scan-topic /robot3/scan --odom-topic /robot3/odom
```

Cấu hình chỉ áp dụng trong terminal đang source, không sửa `.bashrc` hoặc cấu hình trên robot. Không dùng `sim_env.sh`/domain 98 cho robot thật.

Các launch điều khiển/SLAM hiện có chưa được kiểm thử với namespace `/robot3`; cần cấu hình namespace/topic/action đúng trước khi chạy trên phần cứng. Không coi việc nhận được cảm biến là đã kiểm thử chuyển động.

Kết quả chi tiết: `results/robot_connection/robot3_connection.json`. IP có thể đổi theo DHCP; đối chiếu màn hình robot ở lần kết nối sau. Discovery Server client có thể chỉ hiển thị một phần ROS graph, dù các subscription khớp vẫn nhận dữ liệu.

## Điều khiển bàn phím laptop

```bash
cd "$(git rev-parse --show-toplevel)"
bash scripts/run_robot3_keyboard.sh
```

Bấm vào cửa sổ điều khiển rồi giữ W/S để tiến/lùi, A/D để xoay; có thể dùng phím mũi tên. Space dừng, Q hoặc đóng cửa sổ kết thúc. Tốc độ giới hạn 0,10 m/s và 0,35 rad/s. Thả phím hoặc mất focus sẽ về 0. Thiếu odometry mới quá 1 giây hoặc không có bộ nhận cmd_vel thì khóa chuyển động.

Robot đang trên dock sẽ khóa phím chạy. Nút RỜI DOCK gửi action `/robot3/undock` chỉ khi người dùng bấm; Space có thể hủy. Bảng điều khiển không tự rời dock khi mở. Không sử dụng đồng thời với một nguồn điều khiển chuyển động khác.


## Kết nối thủ công với một TurtleBot 4 khác

Cần xác định đúng **IP, ROS_DOMAIN_ID, RMW_IMPLEMENTATION, ROS_DISCOVERY_SERVER và namespace** của robot mới. Các giá trị robot3 ở trên chỉ là cấu hình đã xác minh của robot3, không mặc định áp dụng cho robot khác.

### 1. Đóng điều khiển robot cũ

Nhấn **Q** hoặc đóng bảng điều khiển robot3. Dừng node teleop cũ trước khi chuyển robot.

Bảng `run_robot3_keyboard.sh` hiện cố định các topic/action `/robot3/...` và source `robot3_env.sh`. Chỉ đổi IP hoặc biến namespace trong terminal không làm bảng này chuyển sang robot mới. Phần dưới dùng node bàn phím terminal có thể chỉ định topic.

### 2. Lấy IP và cấu hình robot mới

Laptop và robot cần kết nối cùng mạng có thể liên lạc được. Xem IP trên màn hình robot, rồi mở terminal laptop:

```bash
ssh ubuntu@IP_ROBOT_MOI
```

Thay `IP_ROBOT_MOI` bằng IP thực tế; dùng tài khoản/mật khẩu của robot đó.

Sau khi đăng nhập, chạy trên **robot mới dùng ROS 2 Humble**:

```bash
source /opt/ros/humble/setup.bash
source /etc/turtlebot4/setup.bash

printenv ROS_DOMAIN_ID
printenv RMW_IMPLEMENTATION
printenv ROS_DISCOVERY_SERVER
printenv ROBOT_NAMESPACE
```

Ghi lại kết quả. Nếu robot dùng ROS khác, kiểm tra `ls /opt/ros` và dùng môi trường ROS tương ứng. Bước này chỉ đọc cấu hình, không cần thay cấu hình robot.

### 3. Cấu hình một terminal mới trên laptop

Mở terminal mới trên **laptop**, không chạy các lệnh sau trong phiên SSH. Không source `robot3_env.sh` vì tệp đó chứa cấu hình robot3.

```bash
source /opt/ros/humble/setup.bash

unset CYCLONEDDS_URI
unset FASTRTPS_DEFAULT_PROFILES_FILE
unset FASTDDS_DEFAULT_PROFILES_FILE
unset ROS_DISCOVERY_SERVER

export ROS_LOCALHOST_ONLY=0
```

Đặt domain và middleware theo kết quả vừa đọc. Ví dụ dưới đây **chỉ áp dụng nếu robot mới dùng domain 0, Fast DDS và namespace /robot4**:

```bash
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export TB4_NS=/robot4
```

`TB4_NS` là biến tiện dụng cho các lệnh bên dưới, không tự thay namespace của bảng điều khiển cũ. Nếu robot không có namespace:

```bash
export TB4_NS=''
```

Nếu middleware trên robot là `rmw_cyclonedds_cpp`, đặt đúng giá trị đó thay cho Fast DDS khi dùng Simple Discovery.

### 4. Thiết lập Discovery Server nếu robot có sử dụng

Nếu trên robot đọc được:

```text
;;127.0.0.1:11811;
```

thì trên laptop đặt:

```bash
export ROS_DISCOVERY_SERVER=';;IP_ROBOT_MOI:11811;'
```

Giữ nguyên vị trí các dấu `;` và số cổng theo cấu hình thực tế, thay địa chỉ loopback của server trên robot bằng IP có thể truy cập từ laptop. Các vị trí dấu `;` liên quan đến Server ID; không mặc định robot nào cũng có hai dấu `;`. Nếu có nhiều server, cần đối chiếu từng địa chỉ và Server ID.

Nếu robot dùng **Simple Discovery**, không đặt `ROS_DISCOVERY_SERVER`:

```bash
unset ROS_DISCOVERY_SERVER
```

Tham khảo: [TurtleBot 4 Networking](https://turtlebot.github.io/turtlebot4-user-manual/setup/networking.html), [Simple Discovery](https://turtlebot.github.io/turtlebot4-user-manual/setup/simple_discovery.html), [Discovery Server](https://turtlebot.github.io/turtlebot4-user-manual/setup/discovery_server.html).

### 5. Kiểm tra dữ liệu cảm biến

Trong chính terminal laptop vừa cấu hình:

```bash
cd "$(git rev-parse --show-toplevel)"

/usr/bin/python3 scripts/lab_project.py doctor \
  --scan-topic "${TB4_NS}/scan" \
  --odom-topic "${TB4_NS}/odom"
```

Nếu nhận được cả scan và odometry thì đường truyền dữ liệu cảm biến đã hoạt động. Kiểm tra namespace/topic thực tế nếu thiếu dữ liệu. Discovery Server client có thể chỉ hiển thị một phần ROS graph; việc nhận dữ liệu trực tiếp là phép kiểm tra riêng với `ros2 topic list`.

### 6. Điều khiển bằng bàn phím terminal

Chạy trong terminal đã cấu hình đúng robot, chỉ sau khi xác định đúng namespace:

```bash
/usr/bin/python3 scripts/lab_teleop.py \
  --topic "${TB4_NS}/cmd_vel"
```

- Giữ **W/S** để tiến/lùi, **A/D** để xoay trái/phải.
- **Space** dừng; **Q** thoát.
- Tốc độ của node terminal: 0,12 m/s và 0,4 rad/s.
- Không có sự kiện phím mới trong 0,35 giây thì node phát vận tốc 0. Không chạy đồng thời nguồn điều khiển chuyển động khác.

Nếu robot còn trên dock, cần rời dock trước. Lệnh sau **thực hiện chuyển động rời dock** trên robot được chọn bởi `TB4_NS`; chỉ chạy khi bạn chủ động muốn rời dock:

```bash
ros2 action send_goal "${TB4_NS}/undock" \
  irobot_create_msgs/action/Undock "{}"
```

### Lưu ý khi chuyển robot

- Mỗi terminal mới cần được source ROS và đặt lại cấu hình kết nối. Không commit `config/robot_connection.env`.
- Kiểm tra IP, namespace và domain thực tế; IP có thể đổi theo DHCP.
- Dùng `TB4_NS=/robot4` là ví dụ, không suy ra namespace từ số thứ tự hoặc IP robot.
- Bảng đồ họa hiện tại chỉ dành cho robot3. Muốn chọn robot khác ngay trong bảng cần bổ sung cấu hình namespace cho bảng.
- Kết nối và điều khiển được chưa đồng nghĩa với SLAM/Nav2 đã được cấu hình đúng; phần quét map cần dùng đúng namespace của robot mới.

## Chạy và kiểm tra thủ công hệ thống HRI trên robot thật

Phần này là thứ tự nên làm khi thử robot thật. **Không chạy Gazebo**, `sim_env.sh`, hoặc hai nguồn phát vận tốc cùng lúc. Dọn lối đi, đặt robot trên sàn, có người đứng gần nút dừng vật lý; lần đầu chỉ thử ở tốc độ thấp bằng bàn phím.

Các lệnh từ đây giả sử bạn đã hoàn tất mục **3–4** bên trên trong chính terminal đó (`ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION`, `ROS_DISCOVERY_SERVER` nếu có, và `TB4_NS`). Với robot3, có thể thay phần cấu hình bằng `source scripts/robot3_env.sh`; với robot khác, dùng cấu hình thủ công ở trên.

### 1. Build một lần trên laptop

```bash
cd "$(git rev-parse --show-toplevel)"
source /opt/ros/humble/setup.bash
colcon build --packages-select tb4_cuoiky --symlink-install
source install/setup.bash
```

Nếu chỉ chạy lại sau đó, `start_project.sh` tự source `install/setup.bash`; chỉ cần build lại khi đã sửa mã nguồn hoặc chưa có thư mục `install/`.

### 2. Kiểm tra ROS và cảm biến — chỉ đọc, chưa làm robot chạy

```bash
cd "$(git rev-parse --show-toplevel)"

ros2 topic list | rg "${TB4_NS}/(scan|odom|cmd_vel)|${TB4_NS}/tf"
ros2 topic echo --once "${TB4_NS}/scan"
ros2 topic echo --once "${TB4_NS}/odom"
ros2 topic info -v "${TB4_NS}/cmd_vel"

/usr/bin/python3 scripts/lab_project.py doctor \
  --scan-topic "${TB4_NS}/scan" \
  --odom-topic "${TB4_NS}/odom"
```

Hai lệnh `echo --once` phải trả về dữ liệu mới tiếp tục. Xem `frame_id` trong bản tin scan để đối chiếu TF thực tế. Không có scan hoặc odometry thì dừng ở đây, kiểm tra lại Wi-Fi/DDS/domain/namespace; **không** thử điều khiển mù.

### 3. Thử chuyển động tối thiểu bằng bàn phím

Chỉ thực hiện sau khi mục 2 đạt và bảo đảm không có một node điều khiển khác đang chạy:

```bash
cd "$(git rev-parse --show-toplevel)"
/usr/bin/python3 scripts/lab_teleop.py --topic "${TB4_NS}/cmd_vel"
```

Giữ `W` tiến, `S` lùi, `A/D` xoay; thả phím sẽ dừng. `Space` dừng tức thì và `Q` thoát. Chỉ nhấn rất ngắn lần đầu. Nếu robot còn trên dock, thực hiện rời dock theo lệnh đã nêu ở mục 6 phía trên, rồi chạy lại phép thử này. Không mở phiên HRI/SLAM cùng lúc với `lab_teleop.py`.

### 4. Quét map thật và lưu map lần đầu

Sau khi thoát node bàn phím bằng `Q`, giữ nguyên terminal DDS của robot và chạy:

```bash
cd "$(git rev-parse --show-toplevel)"
bash scripts/start_project.sh robot --profile config/profiles/robot.yaml --new-scan
```

Lệnh này không mở Gazebo. Nó mở RViz, bảng HRI, camera/micro laptop và dùng scan/odom/TF của robot thật. Trên bảng chọn **QUÉT THỦ CÔNG** hoặc **QUÉT TỰ ĐỘNG**. Khi đã quét đủ, bấm **DỪNG QUÉT**, nhập tên map, bấm **LƯU MAP** rồi xác nhận bằng ngón cái, câu “Xác nhận”, hoặc nút xác nhận. Map và các địa điểm được lưu tách riêng theo namespace robot; không dùng catalog/map Maze của mô phỏng cho phòng thật.

Nhấn `Ctrl+C` ở terminal này để dừng toàn bộ phiên robot thật. Không dùng `scripts/stop_sim.sh` để dừng phiên robot.

### 5. Mở lại map thật đã lưu, định vị rồi điều hướng

Thay `TEN_MAP_THAT` bằng đúng thư mục map đã lưu ở `maps/user_saved/`:

```bash
cd "$(git rev-parse --show-toplevel)"
bash scripts/start_project.sh robot --profile config/profiles/robot.yaml \
  --catalog "maps/user_saved/TEN_MAP_THAT/destinations.yaml"
```

Khi RViz báo đang chờ định vị, chọn **2D Pose Estimate** và kéo mũi tên tại vị trí/hướng thật hiện tại của robot. Chỉ sau khi robot định vị đúng mới thử lệnh “Đi đến …”, cử chỉ 1/2/3 ngón hoặc nút đi đến. Không lấy pose cũ hay tọa độ mô phỏng làm pose khởi đầu của robot thật.

### 6. Kiểm tra trước khi thử điều hướng tự động

Trong **terminal thứ hai đã cấu hình cùng DDS** (không chạy teleop), thực hiện khi phiên tại mục 5 đang mở:

```bash
cd "$(git rev-parse --show-toplevel)"
source /opt/ros/humble/setup.bash
source install/setup.bash

python3 scripts/robot_preflight.py \
  --profile config/profiles/robot.yaml \
  --catalog "maps/user_saved/TEN_MAP_THAT/destinations.yaml" \
  --seconds 10
```

Kết quả cần có `"passed": true`. Kiểm tra này chỉ đọc scan, odom, RGB/CameraInfo, TF và xác minh bộ lọc an toàn là nguồn xuất vận tốc duy nhất. Nếu chưa đạt, không thử điều hướng tự động; đặc biệt hãy sửa `namespace`, `rgb_topic`, `info_topic` hoặc TF trong `config/profiles/robot.yaml` theo robot đang dùng.

### 7. Dừng an toàn và kiểm tra sau thử

- Khi bàn phím đang chạy: `Space`, sau đó `Q`.
- Khi phiên HRI đang chạy: nói “Dừng”, giơ nắm tay, hoặc `Ctrl+C` tại terminal phiên.
- Không khởi chạy đồng thời `lab_teleop.py`, `start_project.sh robot`, `run_robot_hri.sh`, hoặc một Nav2/SLAM khác trên cùng namespace.
- Nếu robot không dừng như mong muốn, dùng nút dừng vật lý/nhấc robot khỏi vùng nguy hiểm theo quy định phòng lab; sau đó mới chẩn đoán phần mềm.
