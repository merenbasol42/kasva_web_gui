// Global değişkenler
let linearSpeed = 0;
let angularSpeed = 0;

const MAX_LINEAR_SPEED = 1.0;
const MAX_ANGULAR_SPEED = 1.5;

// Zaman kontrolü için değişken (komut gönderme sıklığını sınırlandırmak için)
let lastCommandTime = 0;

// Buton elementlerini seç
const forwardBtn = document.getElementById('btn-forward');
const backwardBtn = document.getElementById('btn-backward');
const leftBtn = document.getElementById('btn-left');
const rightBtn = document.getElementById('btn-right');
const stopBtn = document.getElementById('btn-stop');

// Hız göstergesi elementleri (isteğe bağlı)
const linearDisplay = document.getElementById('linear-display');
const angularDisplay = document.getElementById('angular-display');

function updateDisplays() {
  if (linearDisplay) {
    linearDisplay.textContent = linearSpeed.toFixed(2);
  }
  if (angularDisplay) {
    angularDisplay.textContent = angularSpeed.toFixed(2);
  }
}

// Sunucuya komut gönderen fonksiyon (endpoint: /cmd_vel)
function sendJoystickCommand(linear, angular) {
    const currentTime = performance.now();
    if (currentTime - lastCommandTime >= 100) { // Her 100ms'de bir komut gönder
        lastCommandTime = currentTime;

        fetch('/cmd_vel', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              linear_x: linear,
              angular_z: angular
            })
        })
        .then(response => response.json())
        .then(data => console.log("Komut gönderildi:", data))
        .catch(error => console.error("Hata:", error));
    } else {
        // Henüz 0.1 saniye geçmediyse komut gönderme
        console.log("Komut gönderme aralığı: ", currentTime - lastCommandTime);
    }
}

// Butonlara tıklama olayları ekle
forwardBtn.addEventListener('click', function() {
    linearSpeed = MAX_LINEAR_SPEED;
    angularSpeed = 0;
    updateDisplays();
    sendJoystickCommand(linearSpeed, angularSpeed);
});

backwardBtn.addEventListener('click', function() {
    linearSpeed = -MAX_LINEAR_SPEED;
    angularSpeed = 0;
    updateDisplays();
    sendJoystickCommand(linearSpeed, angularSpeed);
});

leftBtn.addEventListener('click', function() {
    // ROS'ta sola dönüş için pozitif angular hız kullanılıyor
    linearSpeed = 0;
    angularSpeed = MAX_ANGULAR_SPEED;
    updateDisplays();
    sendJoystickCommand(linearSpeed, angularSpeed);
});

rightBtn.addEventListener('click', function() {
    // ROS'ta sağa dönüş için negatif angular hız kullanılıyor
    linearSpeed = 0;
    angularSpeed = -MAX_ANGULAR_SPEED;
    updateDisplays();
    sendJoystickCommand(linearSpeed, angularSpeed);
});

stopBtn.addEventListener('click', function() {
    linearSpeed = 0;
    angularSpeed = 0;
    updateDisplays();
    sendJoystickCommand(linearSpeed, angularSpeed);
});

// Sayfa yüklendiğinde ve kapatılırken robotu durdur
window.onload = function() {
    sendJoystickCommand(0, 0);
};

window.onbeforeunload = function() {
    sendJoystickCommand(0, 0);
};
