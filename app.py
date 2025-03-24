import cv2
import queue
from threading import Thread

from flask import Flask, render_template, Response, request, jsonify
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge, CvBridgeError

# --- Global Queue for Frame Data ---
frame_queue = queue.Queue(maxsize=1)
map_queue = queue.Queue(maxsize=1)

# --- ROS2 Node: Web GUI ---
class WebGuiNode(Node):
    def __init__(self):
        super().__init__("webgui")

        self.img = None  # Son alınan görüntü mesajı
        self.img_flag = False
        self.map = None
        self.map_flag = False
        
        self.cv_bridge = CvBridge()

        # Twist mesajları için yayıncı oluşturuyoruz
        self.cmd_vel_pubber = self.create_publisher(Twist, 'cmd_vel', 10)

        # Kamera görüntülerini dinlemek için abonelik
        self.create_subscription(
            Image,
            "camera/image_raw",
            self.img_cb,
            3
        )
        self.create_subscription(
            Image,
            "map_image",
            self.map_img_cb,
            3
        )

    def start(self) -> None:
        """
        Arka planda sürekli görüntü işleme işlemi başlatır.
        """
        def func():
            while rclpy.ok():
                if self.img_flag:
                    self.process_image()
                if self.map_flag:
                    self.process_map()

        Thread(target=func, daemon=True).start()

    def img_cb(self, msg: Image) -> None:
        """
        ROS2 görüntü mesajı geldiğinde çağrılır.
        """
        self.img = msg
        self.img_flag = True

    def map_img_cb(self, msg: Image) -> None:
        self.map = msg
        self.map_flag = True

    def process_map(self) -> None:
        frame = self.cv_bridge.imgmsg_to_cv2(self.map, desired_encoding='bgr8')
        map_queue.put(frame)

    def process_image(self) -> None:
        """
        ROS2 görüntü mesajını OpenCV görüntüsüne çevirir ve kuyruğa ekler.
        """
        try:
            frame = self.cv_bridge.imgmsg_to_cv2(self.img, desired_encoding='bgr8')
            # Kuyruk dolu ise eski görüntüyü çıkar
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
            frame_queue.put(frame)
            self.img_flag = False  # İşlem tamamlandı
        except CvBridgeError as e:
            self.get_logger().error(f"CvBridge Error: {e}")

    def pub_cmd_vel(self, linear_x: float, angular_z: float) -> None:
        """
        Gelen hız verilerini kullanarak Twist mesajı yayınlar.
        """
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self.cmd_vel_pubber.publish(twist)
        self.get_logger().info(f"Published cmd_vel: linear_x={linear_x}, angular_z={angular_z}")


# --- Flask Uygulaması ---
app = Flask(__name__)
ros_node: WebGuiNode = None  # Global referans, main bloğunda atanacak

def gen_frames():
    """
    Sürekli güncellenen görüntü akışı oluşturur.
    """
    while True:
        try:
            frame = frame_queue.get(timeout=1)
        except queue.Empty:
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def get_map_frames():
    while True:
        try:
            frame = map_queue.get(timeout=1)
        except queue.Empty:
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/')
def index():
    """
    Ana sayfa: index.html render edilir.
    """
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """
    Video akışını sağlayan endpoint.
    """
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/map_feed')
def map_feed():
    """
    Video akışını sağlayan endpoint.
    """
    return Response(get_map_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/cmd_vel', methods=['POST'])
def cmd_vel():
    """
    Joystick üzerinden gelen komutları alır ve ROS2 üzerinden cmd_vel yayınlar.
    """
    data = request.get_json()
    if data is None:
        return jsonify({"status": "error", "message": "No JSON provided"}), 400

    try:
        linear = float(data.get('linear_x', 0.0))
        angular = float(data.get('angular_z', 0.0))
    except (ValueError, TypeError) as e:
        return jsonify({"status": "error", "message": f"Invalid data: {e}"}), 400

    ros_node.pub_cmd_vel(linear, angular)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # ROS2 başlatılıyor
    rclpy.init()
    ros_node = WebGuiNode()
    ros_node.start()
    # ROS2 işlemleri ayrı bir thread üzerinden çalıştırılıyor
    ros_thread = Thread(target=lambda: rclpy.spin(ros_node), daemon=True)
    ros_thread.start()

    try:
        # Flask uygulaması çalıştırılıyor
        app.run(host='0.0.0.0', port=4242)
    except KeyboardInterrupt:
        pass
    finally:
        # Kapatma işlemleri
        ros_node.destroy_node()
        rclpy.shutdown()
