# 🚀 Chạy Meshtastic Network Simulator

## Cách 1: Double-click Batch File (Dễ nhất) ⭐

Tìm và double-click file `run_simulator.bat` trong thư mục này.

```
run_simulator.bat
```

Xong! Simulator sẽ chạy ngay.

---

## Cách 2: Tạo Desktop Shortcut (Optional)

Nếu muốn tạo shortcut trên desktop:

### Step 1: Cài đặt dependencies (chỉ cần 1 lần)
```bash
pip install pywin32 winshell
```

### Step 2: Chạy script tạo shortcut
```bash
python create_shortcut.py
```

Shortcut sẽ xuất hiện trên desktop, double-click để chạy.

---

## Cách 3: Command Line

Nếu thích chạy từ terminal:

```bash
# PowerShell
.\.venv\Scripts\python.exe interactiveDemo.py

# Hoặc Command Prompt (cmd)
.venv\Scripts\python.exe interactiveDemo.py
```

---

## 🎮 Hướng dẫn sử dụng:

### Điều khiển:
- **Double-click**: Đặt node
- **Click**: Chọn node (màu vàng)
- **Right-click**: Broadcast từ node đã chọn
- **'d' + click**: Gửi Direct Message
- **'t' + click**: Traceroute
- **'p' + click**: Ping
- **'c'**: Xóa tất cả
- **'r'**: Xóa routes
- **TextBox**: Nhập message ID để xem chi tiết
- **Hover**: Di chuột qua mũi tên để xem thông tin

### Màu sắc:
- 🟢 **Xanh lá**: Broadcast
- 🔵 **Xanh dương**: Direct Message
- 🔴 **Đỏ đứt nét**: ACK responses

---

## ⚙️ Cấu hình:

Chỉnh sửa `lib/config.py` để thay đổi:
- Spreading Factor (SF)
- Bandwidth (BW)
- Transmit Power
- Pathloss Model
- Các parameters khác

---

## 🐛 Troubleshooting:

### Lỗi: "Virtual environment not found"
```bash
python -m venv .venv
pip install -r requirements.txt
```

### Lỗi: "Module not found"
```bash
.venv\Scripts\pip install -r requirements.txt
```

### Font warnings (không ảnh hưởng)
Các warning về missing glyphs là bình thường, không cần lo.

---

**Enjoy! 🎉**
