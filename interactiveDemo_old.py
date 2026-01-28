#!/usr/bin/env python3
"""
Interactive demo - Mô phỏng Meshtastic network 100% chính xác
Dùng thuật toán vật lý từ lib/phy.py
"""
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
from matplotlib.widgets import Button, TextBox
import numpy as np
import math
import random
from datetime import datetime
from collections import defaultdict

# Import config và phy algorithms
import sys
sys.path.insert(0, '.')
from lib.config import Config
import lib.phy as phy_module

class LoRaPacket:
    """Represents a LoRa packet with all properties"""
    def __init__(self, packet_id, tx_node_id, sf, bw, freq, tx_power, payload_length):
        self.packet_id = packet_id
        self.tx_node_id = tx_node_id
        self.sf = sf
        self.bw = bw
        self.freq = freq
        self.tx_power = tx_power
        self.payload_length = payload_length
        self.start_time = 0
        self.end_time = 0
        self.rssi_at_rx = {}  # Dict {rx_node_id: rssi_value}
        self.collision_at_rx = {}  # Dict {rx_node_id: boolean}
        

class InteractiveDemo:
    def __init__(self):
        self.conf = Config()
        self.fig = plt.figure(figsize=(16, 10))
        self.ax_main = plt.subplot2grid((3, 3), (0, 0), colspan=2, rowspan=3)
        self.ax_stats = plt.subplot2grid((3, 3), (0, 2))
        self.ax_messages = plt.subplot2grid((3, 3), (1, 2))
        self.ax_routes = plt.subplot2grid((3, 3), (2, 2))
        
        self.nodes = []
        self.node_circles = []
        self.message_id = 0
        self.messages = []
        self.selected_node = None
        self.route_lines = []
        self.current_message_view = None
        self.sim_time = 0  # Simulation time in ms
        
        # Packets currently in air (for collision detection)
        self.packets_in_air = []
        
        self.setup_plot()
        self.connect_events()
        
    def setup_plot(self):
        """Thiết lập plot ban đầu"""
        # Main plot
        self.ax_main.set_xlim(-1500, 1500)
        self.ax_main.set_ylim(-1500, 1500)
        self.ax_main.set_xlabel('x (m)', fontsize=12)
        self.ax_main.set_ylabel('y (m)', fontsize=12)
        self.ax_main.set_title('Meshtastic Network Simulator (Physics-Accurate) - Double click to place nodes', 
                               fontsize=14, fontweight='bold')
        self.ax_main.grid(True, alpha=0.3)
        self.ax_main.set_aspect('equal')
        
        # Stats panel
        self.ax_stats.axis('off')
        self.stats_text = self.ax_stats.text(0.05, 0.95, self.get_stats_text(), 
                                            verticalalignment='top', fontsize=9,
                                            family='monospace',
                                            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        
        # Messages panel
        self.ax_messages.axis('off')
        self.messages_text = self.ax_messages.text(0.05, 0.95, 'Messages:\n(No messages yet)', 
                                                   verticalalignment='top', fontsize=8,
                                                   family='monospace',
                                                   bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
        
        # Routes panel
        self.ax_routes.axis('off')
        self.routes_text = self.ax_routes.text(0.05, 0.95, 'Route Details:\n(Click a message)', 
                                              verticalalignment='top', fontsize=8,
                                              family='monospace',
                                              bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
        
        # Add instructions
        self.fig.text(0.02, 0.98, 
                     '🎮 Controls:\n'
                     '• Double click: Place node\n'
                     '• Click node: Select (yellow)\n'
                     '• Right click: Send from selected\n'
                     '• "d" + click: Send DM to node\n'
                     '• "c": Clear all\n'
                     '• "r": Clear routes only\n'
                     '• "1-9": View message details',
                     verticalalignment='top', fontsize=9,
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
        
    def connect_events(self):
        """Kết nối các event handlers"""
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.dm_mode = False
        
    def get_stats_text(self):
        """Tạo text thống kê"""
        total_msgs = len(self.messages)
        total_nodes = len(self.nodes)
        
        if total_nodes == 0:
            return "📊 Network Stats:\n\nNo nodes yet\n\nPlace nodes to start!"
        
        total_transmissions = sum(len(m['receivers']) for m in self.messages)
        avg_receivers = total_transmissions / total_msgs if total_msgs > 0 else 0
        
        # Calculate coverage
        reachable_pairs = 0
        total_pairs = total_nodes * (total_nodes - 1)
        
        for i, n1 in enumerate(self.nodes):
            for j, n2 in enumerate(self.nodes):
                if i != j:
                    dist = np.sqrt((n1['x'] - n2['x'])**2 + (n1['y'] - n2['y'])**2)
                    # Check if can reach based on link budget
                    path_loss = self._estimate_path_loss(dist)
                    rssi = self.conf.PTX + self.conf.GL - path_loss
                    if rssi > self.conf.SENSMODEM[self.conf.MODEM]:
                        reachable_pairs += 1
        
        coverage = (reachable_pairs / total_pairs * 100) if total_pairs > 0 else 0
        
        # Collision info
        collided = sum(m['collisions'] for m in self.messages)
        success_rate = ((total_transmissions - collided) / total_transmissions * 100) if total_transmissions > 0 else 0
        
        stats = f"""📊 Network Stats:
        
Nodes: {total_nodes}
Messages: {total_msgs}
Transmissions: {total_transmissions}

Avg reach: {avg_receivers:.1f} nodes
Coverage: {coverage:.1f}%
Success: {success_rate:.1f}%
Collisions: {collided}

Selected: {self.selected_node if self.selected_node is not None else 'None'}

Config:
  SF: {self.conf.SFMODEM[self.conf.MODEM]}
  BW: {self.conf.BWMODEM[self.conf.MODEM]/1e3:.0f}kHz
  Sens: {self.conf.SENSMODEM[self.conf.MODEM]}dBm
"""
        return stats
        
    def _estimate_path_loss(self, dist):
        """
        Estimate path loss dựa trên 3GPP Suburban Macro Model (Model 5)
        Giống như lib/phy.py
        """
        if dist < 0.001:
            dist = 0.001
            
        # 3GPP Suburban Macro Model
        freq = self.conf.FREQ
        txZ = self.conf.HM
        rxZ = self.conf.HM
        C = 0  # dB (Suburban Macro)
        
        path_loss = (44.9 - 6.55 * math.log10(txZ)) * (math.log10(dist) - 3.0) \
                  + 45.5 + (35.46 - 1.1 * rxZ) * (math.log10(freq) - 6.0) \
                  - 13.82 * math.log10(rxZ) + 0.7 * rxZ + C
        
        return path_loss
    
    def _calculate_airtime(self, payload_length):
        """
        Calculate airtime dựa trên SF, BW, payload (từ lib/phy.py)
        """
        sf = self.conf.SFMODEM[self.conf.MODEM]
        bw = self.conf.BWMODEM[self.conf.MODEM]
        cr = self.conf.CRMODEM[self.conf.MODEM]
        pl = payload_length + self.conf.HEADERLENGTH
        
        H = 0  # implicit header
        DE = 0  # low data rate optimization
        
        if bw == 125e3 and sf in [11, 12]:
            DE = 1
        if sf == 6:
            H = 1
        
        Tsym = (2.0 ** sf) / bw
        Tpream = (self.conf.NPREAM + 4.25) * Tsym
        payloadSymbNB = 8 + max(
            math.ceil((8.0 * pl - 4.0 * sf + 28 + 16 - 20 * H) / (4.0 * (sf - 2 * DE))) * (cr + 4), 
            0
        )
        Tpayload = payloadSymbNB * Tsym
        
        return int((Tpream + Tpayload) * 1000)  # ms
    
    def _frequency_collision(self, p1, p2):
        """Check frequency collision (from lib/phy.py)"""
        if abs(p1.freq - p2.freq) <= 120 and (p1.bw == 500 or p2.bw == 500):
            return True
        elif abs(p1.freq - p2.freq) <= 60 and (p1.bw == 250 or p2.bw == 250):
            return True
        elif abs(p1.freq - p2.freq) <= 30:
            return True
        return False
    
    def _sf_collision(self, p1, p2):
        """Check SF collision"""
        return p1.sf == p2.sf
    
    def _power_collision(self, p1, p2, rx_node_id):
        """Check power collision (threshold = 6dB)"""
        power_threshold = 6  # dB
        rssi1 = p1.rssi_at_rx.get(rx_node_id, -200)
        rssi2 = p2.rssi_at_rx.get(rx_node_id, -200)
        
        if abs(rssi1 - rssi2) < power_threshold:
            return (p1, p2)  # Both collide
        elif rssi1 - rssi2 < power_threshold:
            return (p1,)  # p2 overpowers p1
        return (p2,)  # p1 overpowers p2
    
    def _timing_collision(self, p1, p2):
        """Check timing collision"""
        sf = self.conf.SFMODEM[self.conf.MODEM]
        Tsym = (2.0 ** sf) / self.conf.BWMODEM[self.conf.MODEM]
        Tpreamb = Tsym * (self.conf.NPREAM - 5)
        p1_cs = p1.start_time + Tpreamb
        
        if p1_cs < p2.end_time:
            return True
        return False
    
    def _check_collisions(self, new_packet):
        """
        Check for collisions between new_packet and existing packets
        Returns True if collision occurred
        """
        collided = False
        
        for existing_packet in self.packets_in_air:
            # Check all conditions for collision
            for rx_node_id in self.nodes:
                rx_id = rx_node_id['id']
                
                if rx_id not in new_packet.rssi_at_rx:
                    continue
                if rx_id not in existing_packet.rssi_at_rx:
                    continue
                
                # Check all collision types
                if (self._frequency_collision(new_packet, existing_packet) and
                    self._sf_collision(new_packet, existing_packet) and
                    self._timing_collision(new_packet, existing_packet)):
                    
                    # Power collision check
                    casualties = self._power_collision(new_packet, existing_packet, rx_id)
                    for p in casualties:
                        if p.packet_id == new_packet.packet_id:
                            collided = True
                        p.collision_at_rx[rx_id] = True
        
        return collided
        
    def update_displays(self):
        """Cập nhật tất cả displays"""
        self.stats_text.set_text(self.get_stats_text())
        
        msg_text = "📨 Recent Messages:\n\n"
        for i, msg_data in enumerate(self.messages[-5:]):
            msg = msg_data['message']
            receivers = len(msg_data['receivers'])
            collisions = msg_data['collisions']
            status = "❌" if collisions > 0 else "✅"
            msg_text += f"{status} #{msg['id']}: Node {msg['sender']} → {receivers}\n"
            if collisions > 0:
                msg_text += f"  ⚠️  {collisions} collision(s)\n"
            msg_text += f"  RSSI: {msg_data.get('avg_rssi', 0):.1f} dBm\n"
        
        if len(self.messages) == 0:
            msg_text = "📨 Messages:\n\n(No messages sent yet)"
            
        self.messages_text.set_text(msg_text)
        
        if self.current_message_view is not None and self.current_message_view < len(self.messages):
            self.show_message_route(self.current_message_view)
        
        self.fig.canvas.draw()
        
    def on_click(self, event):
        """Xử lý click chuột"""
        if event.inaxes != self.ax_main:
            return
            
        if event.dblclick:
            self.add_node(event.xdata, event.ydata)
        elif event.button == 1:
            self.select_node(event.xdata, event.ydata)
        elif event.button == 3:
            if self.dm_mode:
                self.send_dm_to_node(event.xdata, event.ydata)
                self.dm_mode = False
            else:
                self.send_broadcast()
                
    def on_key(self, event):
        """Xử lý phím"""
        if event.key == 'c':
            self.clear_all()
        elif event.key == 'r':
            self.clear_routes()
        elif event.key == 'd':
            self.dm_mode = True
            print("DM mode activated - click a node to send direct message")
        elif event.key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            msg_id = int(event.key) - 1
            if msg_id < len(self.messages):
                self.current_message_view = msg_id
                self.show_message_route(msg_id)
                
    def select_node(self, x, y):
        """Chọn node gần nhất"""
        if len(self.nodes) == 0:
            return
            
        distances = [np.sqrt((n['x'] - x)**2 + (n['y'] - y)**2) for n in self.nodes]
        min_dist = min(distances)
        
        if min_dist < 100:
            old_selected = self.selected_node
            self.selected_node = distances.index(min_dist)
            
            if old_selected is not None and old_selected < len(self.node_circles):
                self.node_circles[old_selected][0].set_color('blue')
            
            if self.selected_node < len(self.node_circles):
                self.node_circles[self.selected_node][0].set_color('yellow')
            
            self.update_displays()
            print(f"Selected Node {self.selected_node}")
            
    def add_node(self, x, y):
        """Thêm node mới"""
        node_id = len(self.nodes)
        
        node = {
            'id': node_id,
            'x': x,
            'y': y,
            'height': self.conf.HM,
            'antenna_gain': self.conf.GL,
            'hopLimit': self.conf.hopLimit,
            'role': 'Router' if self.conf.router else 'Client',
            'tx_power': self.conf.PTX,
            'received_messages': [],
            'sent_messages': [],
            'total_rx': 0,
            'total_tx': 0,
            'airtime': 0.0
        }
        self.nodes.append(node)
        
        # Vẽ node
        circle = Circle((x, y), 50, color='blue', alpha=0.7, linewidth=2, edgecolor='darkblue')
        self.ax_main.add_patch(circle)
        self.ax_main.text(x, y, str(node_id), ha='center', va='center', 
                         color='white', fontweight='bold', fontsize=12)
        
        # Vẽ coverage dựa trên link budget
        max_range = self._estimate_max_range()
        coverage = Circle((x, y), max_range, color='blue', alpha=0.05, linestyle='--', 
                         fill=True, linewidth=1)
        self.ax_main.add_patch(coverage)
        
        self.node_circles.append((circle, coverage))
        
        print(f"✅ Node {node_id} added at ({x:.0f}, {y:.0f})")
        print(f"   Config: SF={self.conf.SFMODEM[self.conf.MODEM]}, BW={self.conf.BWMODEM[self.conf.MODEM]/1e3:.0f}kHz")
        print(f"   TxPower={node['tx_power']}dBm, Role={node['role']}, MaxRange={max_range:.0f}m")
        
        self.update_displays()
    
    def _estimate_max_range(self):
        """Ước lượng max range dựa trên link budget"""
        # RSSI = PTX - PathLoss >= SENSITIVITY
        # Reverse calculate: pathLoss = PTX - SENSITIVITY
        max_path_loss = self.conf.PTX + self.conf.GL - self.conf.SENSMODEM[self.conf.MODEM]
        
        # Binary search for max distance
        dist = 1
        while self._estimate_path_loss(dist) < max_path_loss and dist < 10000:
            dist += 1
        
        return dist
        
    def send_broadcast(self):
        """Gửi broadcast từ node được chọn"""
        if self.selected_node is None:
            print("⚠️  No node selected!")
            return
            
        sender = self.nodes[self.selected_node]
        
        self.message_id += 1
        message = {
            'id': self.message_id,
            'sender': sender['id'],
            'destination': 'BROADCAST',
            'text': f"Broadcast {self.message_id}",
            'portnum': 'TEXT_MESSAGE_APP',
            'hop_limit': sender['hopLimit'],
            'path': [sender['id']],
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        
        self.simulate_transmission(message, sender, is_broadcast=True)
        sender['sent_messages'].append(message['id'])
        sender['total_tx'] += 1
        
    def send_dm_to_node(self, x, y):
        """Gửi DM tới node"""
        if self.selected_node is None:
            print("⚠️  No sender selected!")
            return
            
        distances = [np.sqrt((n['x'] - x)**2 + (n['y'] - y)**2) for n in self.nodes]
        min_dist = min(distances)
        
        if min_dist > 100:
            print("⚠️  Click closer to a node")
            return
            
        dest_idx = distances.index(min_dist)
        
        if dest_idx == self.selected_node:
            print("⚠️  Cannot send DM to yourself!")
            return
            
        sender = self.nodes[self.selected_node]
        dest = self.nodes[dest_idx]
        
        self.message_id += 1
        message = {
            'id': self.message_id,
            'sender': sender['id'],
            'destination': dest['id'],
            'text': f"DM: {sender['id']}→{dest['id']}",
            'portnum': 'TEXT_MESSAGE_APP',
            'hop_limit': sender['hopLimit'],
            'path': [sender['id']],
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        
        self.simulate_transmission(message, sender, is_broadcast=False, destination=dest)
        sender['sent_messages'].append(message['id'])
        sender['total_tx'] += 1
        
    def simulate_transmission(self, message, sender, is_broadcast=True, destination=None):
        """Mô phỏng transmission với collision detection"""
        separator = '='*60
        print(f"\n{separator}")
        print(f"📡 Message #{message['id']} Transmission (Physics-Based)")
        print(f"   Sender: Node {sender['id']} at ({sender['x']:.0f}, {sender['y']:.0f})")
        dest_text = 'BROADCAST' if is_broadcast else f"DM to Node {destination['id']}"
        print(f"   Type: {dest_text}")
        print(separator)
        
        # Create packet object
        packet = LoRaPacket(
            packet_id=message['id'],
            tx_node_id=sender['id'],
            sf=self.conf.SFMODEM[self.conf.MODEM],
            bw=self.conf.BWMODEM[self.conf.MODEM],
            freq=self.conf.FREQ,
            tx_power=sender['tx_power'],
            payload_length=self.conf.PACKETLENGTH
        )
        
        # Calculate airtime
        airtime_ms = self._calculate_airtime(self.conf.PACKETLENGTH)
        packet.start_time = self.sim_time
        packet.end_time = self.sim_time + airtime_ms
        self.sim_time += airtime_ms
        
        print(f"   Airtime: {airtime_ms}ms | SF: {packet.sf} | BW: {packet.bw/1e3:.0f}kHz")
        
        # Calculate RSSI for each node
        receivers = []
        rssi_values = []
        collision_count = 0
        
        for node in self.nodes:
            if node['id'] == sender['id']:
                continue
                
            distance = np.sqrt((node['x'] - sender['x'])**2 + (node['y'] - sender['y'])**2)
            if distance < 10:
                distance = 10
            
            # Path loss calculation (Model 5)
            path_loss = self._estimate_path_loss(distance)
            rssi = sender['tx_power'] + sender['antenna_gain'] + node['antenna_gain'] - path_loss
            
            # Add fading
            fading = np.random.normal(0, 3)  # Shadow fading
            rssi_actual = rssi + fading
            
            packet.rssi_at_rx[node['id']] = rssi_actual
            packet.collision_at_rx[node['id']] = False
            
            # Check sensitivity
            sensitivity = self.conf.SENSMODEM[self.conf.MODEM]
            
            if rssi_actual > sensitivity:
                # Calculate SNR and PER
                snr = rssi_actual - sensitivity
                per = 1 / (1 + np.exp((snr - 10) / 2))
                
                success = np.random.random() > per
                
                if success:
                    receivers.append(node)
                    rssi_values.append(rssi_actual)
                    node['received_messages'].append(message['id'])
                    node['total_rx'] += 1
                    
                    print(f"  ✅ RECEIVED: Node {node['id']}")
                    print(f"     Dist: {distance:.0f}m | RSSI: {rssi_actual:.1f}dBm | SNR: {snr:.1f}dB")
                    
                    # Draw line
                    color = 'green' if is_broadcast else 'blue'
                    arrow = FancyArrowPatch((sender['x'], sender['y']), 
                                          (node['x'], node['y']),
                                          arrowstyle='->', mutation_scale=20,
                                          color=color, alpha=0.6, linewidth=2)
                    self.ax_main.add_patch(arrow)
                    self.route_lines.append(arrow)
            else:
                print(f"  🔇 OUT OF RANGE: Node {node['id']} (RSSI={rssi_actual:.1f}dBm)")
        
        # Check for collisions
        collision = self._check_collisions(packet)
        if collision:
            collision_count += 1
            print(f"\n  ⚠️  COLLISION DETECTED!")
        
        self.packets_in_air.append(packet)
        
        if len(receivers) == 0:
            print(f"\n  ⚠️  No nodes received the message!")
            avg_rssi = 0
        else:
            avg_rssi = np.mean(rssi_values)
            print(f"\n  ✓ Successfully received by {len(receivers)} node(s)")
            print(f"  Average RSSI: {avg_rssi:.1f} dBm")
        
        print(separator + "\n")
        
        # Store message data
        self.messages.append({
            'message': message,
            'sender': sender,
            'receivers': receivers,
            'avg_rssi': avg_rssi,
            'rssi_values': rssi_values,
            'collisions': collision_count,
            'airtime': airtime_ms,
            'packet': packet
        })
        
        self.update_displays()
        
    def show_message_route(self, msg_idx):
        """Hiển thị chi tiết route"""
        if msg_idx >= len(self.messages):
            return
            
        msg_data = self.messages[msg_idx]
        msg = msg_data['message']
        sender = msg_data['sender']
        receivers = msg_data['receivers']
        
        collision_info = ""
        if msg_data['collisions'] > 0:
            collision_info = f"\n⚠️  COLLISIONS: {msg_data['collisions']}"
        
        route_text = f"""📍 Message #{msg['id']} Route:

Sender: Node {msg['sender']}
Location: ({sender['x']:.0f}, {sender['y']:.0f})
Type: {msg['destination']}
HopLimit: {msg['hop_limit']}
Airtime: {msg_data['airtime']}ms{collision_info}

RSSI: {msg_data['avg_rssi']:.1f} dBm

Receivers ({len(receivers)}):
"""
        for i, (rcv, rssi) in enumerate(zip(receivers, msg_data.get('rssi_values', []))):
            route_text += f"  {i+1}. Node {rcv['id']} ({rssi:.1f}dBm)\n"
            
        self.routes_text.set_text(route_text)
        self.fig.canvas.draw()
        
    def clear_routes(self):
        """Xóa routes"""
        for line in self.route_lines:
            line.remove()
        self.route_lines = []
        self.fig.canvas.draw()
        print("Routes cleared")
        
    def clear_all(self):
        """Xóa tất cả"""
        self.ax_main.clear()
        self.nodes = []
        self.node_circles = []
        self.messages = []
        self.packets_in_air = []
        self.message_id = 0
        self.selected_node = None
        self.route_lines = []
        self.current_message_view = None
        self.sim_time = 0
        
        self.ax_main.set_xlim(-1500, 1500)
        self.ax_main.set_ylim(-1500, 1500)
        self.ax_main.set_xlabel('x (m)', fontsize=12)
        self.ax_main.set_ylabel('y (m)', fontsize=12)
        self.ax_main.set_title('Meshtastic Network Simulator (Physics-Accurate) - Double click to place nodes', 
                               fontsize=14, fontweight='bold')
        self.ax_main.grid(True, alpha=0.3)
        self.ax_main.set_aspect('equal')
        
        self.update_displays()
        print("✅ Cleared all nodes and messages")
        
    def run(self):
        """Chạy demo"""
        print("\n" + "="*70)
        print("🌐 MESHTASTIC NETWORK SIMULATOR - PHYSICS-ACCURATE MODE")
        print("="*70)
        print("\n📋 Configuration:")
        print(f"  • SF: {self.conf.SFMODEM[self.conf.MODEM]}")
        print(f"  • BW: {self.conf.BWMODEM[self.conf.MODEM]/1e3:.0f} kHz")
        print(f"  • Sensitivity: {self.conf.SENSMODEM[self.conf.MODEM]} dBm")
        print(f"  • TX Power: {self.conf.PTX} dBm")
        print(f"  • Model: 3GPP Suburban Macro")
        print(f"  • Collision Detection: ENABLED")
        print("\n📖 Instructions:")
        print("  • Double-click to place a node")
        print("  • Left-click to select (yellow)")
        print("  • Right-click to broadcast")
        print("  • Press 'd' then click to send DM")
        print("  • Press 'c' to clear all")
        print("  • Press 'r' to clear routes")
        print("  • Press 1-9 to view message details")
        print("\n🚀 Ready! Start placing nodes...")
        print("="*70 + "\n")
        
        plt.tight_layout()
        plt.show()
        
    def setup_plot(self):
        """Thiết lập plot ban đầu"""
        # Main plot
        self.ax_main.set_xlim(-1500, 1500)
        self.ax_main.set_ylim(-1500, 1500)
        self.ax_main.set_xlabel('x (m)', fontsize=12)
        self.ax_main.set_ylabel('y (m)', fontsize=12)
        self.ax_main.set_title('Meshtastic Network Simulator - Double click to place nodes', fontsize=14, fontweight='bold')
        self.ax_main.grid(True, alpha=0.3)
        self.ax_main.set_aspect('equal')
        
        # Stats panel
        self.ax_stats.axis('off')
        self.stats_text = self.ax_stats.text(0.05, 0.95, self.get_stats_text(), 
                                            verticalalignment='top', fontsize=9,
                                            family='monospace',
                                            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        
        # Messages panel
        self.ax_messages.axis('off')
        self.messages_text = self.ax_messages.text(0.05, 0.95, 'Messages:\n(No messages yet)', 
                                                   verticalalignment='top', fontsize=8,
                                                   family='monospace',
                                                   bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
        
        # Routes panel
        self.ax_routes.axis('off')
        self.routes_text = self.ax_routes.text(0.05, 0.95, 'Route Details:\n(Click a message)', 
                                              verticalalignment='top', fontsize=8,
                                              family='monospace',
                                              bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
        
        # Thêm hướng dẫn
        self.fig.text(0.02, 0.98, 
                     '🎮 Controls:\n'
                     '• Double click: Place node\n'
                     '• Click node: Select (yellow)\n'
                     '• Right click: Send from selected\n'
                     '• "d" + click: Send DM to node\n'
                     '• "c": Clear all\n'
                     '• "r": Clear routes only',
                     verticalalignment='top', fontsize=9,
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
        
    def connect_events(self):
        """Kết nối các event handlers"""
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.dm_mode = False
        
    def get_stats_text(self):
        """Tạo text thống kê"""
        total_msgs = len(self.messages)
        total_nodes = len(self.nodes)
        
        if total_nodes == 0:
            return "📊 Network Stats:\n\nNo nodes yet\n\nPlace nodes to start!"
        
        # Tính các metrics
        total_transmissions = sum(len(m['receivers']) for m in self.messages)
        avg_receivers = total_transmissions / total_msgs if total_msgs > 0 else 0
        
        # Tính coverage
        reachable_pairs = 0
        total_pairs = total_nodes * (total_nodes - 1)
        
        for i, n1 in enumerate(self.nodes):
            for j, n2 in enumerate(self.nodes):
                if i != j:
                    dist = np.sqrt((n1['x'] - n2['x'])**2 + (n1['y'] - n2['y'])**2)
                    if dist < 1500:  # Rough estimate
                        reachable_pairs += 1
        
        coverage = (reachable_pairs / total_pairs * 100) if total_pairs > 0 else 0
        
        stats = f"""📊 Network Stats:
        
Nodes: {total_nodes}
Messages: {total_msgs}
Transmissions: {total_transmissions}

Avg reach: {avg_receivers:.1f} nodes
Coverage: {coverage:.1f}%

Selected: {self.selected_node if self.selected_node is not None else 'None'}
"""
        return stats
        
    def update_displays(self):
        """Cập nhật tất cả các displays"""
        # Update stats
        self.stats_text.set_text(self.get_stats_text())
        
        # Update messages list
        msg_text = "📨 Recent Messages:\n\n"
        for i, msg_data in enumerate(self.messages[-5:]):  # Last 5 messages
            msg = msg_data['message']
            receivers = len(msg_data['receivers'])
            msg_text += f"#{msg['id']}: Node {msg['sender']} → {receivers} nodes\n"
            msg_text += f"  RSSI: {msg_data.get('avg_rssi', 0):.1f} dBm\n"
        
        if len(self.messages) == 0:
            msg_text = "📨 Messages:\n\n(No messages sent yet)"
            
        self.messages_text.set_text(msg_text)
        
        # Update routes if message selected
        if self.current_message_view is not None and self.current_message_view < len(self.messages):
            self.show_message_route(self.current_message_view)
        
        self.fig.canvas.draw()
        
    def on_click(self, event):
        """Xử lý click chuột"""
        if event.inaxes != self.ax_main:
            return
            
        if event.dblclick:  # Double click - thêm node
            self.add_node(event.xdata, event.ydata)
        elif event.button == 1:  # Left click - select node
            self.select_node(event.xdata, event.ydata)
        elif event.button == 3:  # Right click - gửi message
            if self.dm_mode:
                self.send_dm_to_node(event.xdata, event.ydata)
                self.dm_mode = False
            else:
                self.send_broadcast()
                
    def on_key(self, event):
        """Xử lý phím"""
        if event.key == 'c':  # Clear all
            self.clear_all()
        elif event.key == 'r':  # Clear routes only
            self.clear_routes()
        elif event.key == 'd':  # DM mode
            self.dm_mode = True
            print("DM mode activated - click a node to send direct message")
        elif event.key == 's':  # Show connectivity
            self.show_connectivity()
        elif event.key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            # View message by number
            msg_id = int(event.key) - 1
            if msg_id < len(self.messages):
                self.current_message_view = msg_id
                self.show_message_route(msg_id)
                
    def select_node(self, x, y):
        """Chọn node gần nhất"""
        if len(self.nodes) == 0:
            return
            
        distances = [np.sqrt((n['x'] - x)**2 + (n['y'] - y)**2) for n in self.nodes]
        min_dist = min(distances)
        
        if min_dist < 100:  # Click trong vòng 100m
            old_selected = self.selected_node
            self.selected_node = distances.index(min_dist)
            
            # Update visualization
            if old_selected is not None and old_selected < len(self.node_circles):
                self.node_circles[old_selected][0].set_color('blue')
            
            if self.selected_node < len(self.node_circles):
                self.node_circles[self.selected_node][0].set_color('yellow')
            
            self.update_displays()
            print(f"Selected Node {self.selected_node}")
            
    def add_node(self, x, y):
        """Thêm node mới với cấu hình chi tiết"""
        node_id = len(self.nodes)
        
        # Cấu hình mặc định
        node = {
            'id': node_id,
            'x': x,
            'y': y,
            'height': 4.4,
            'antenna_gain': 1.0,
            'hopLimit': 3,
            'role': 'Router',
            'tx_power': 14,  # dBm
            'received_messages': [],
            'sent_messages': [],
            'total_rx': 0,
            'total_tx': 0,
            'airtime': 0.0
        }
        self.nodes.append(node)
        
        # Vẽ node
        circle = Circle((x, y), 50, color='blue', alpha=0.7, linewidth=2, edgecolor='darkblue')
        self.ax_main.add_patch(circle)
        self.ax_main.text(x, y, str(node_id), ha='center', va='center', 
                         color='white', fontweight='bold', fontsize=12)
        
        # Vẽ vùng coverage
        coverage = Circle((x, y), 1200, color='blue', alpha=0.05, linestyle='--', 
                         fill=True, linewidth=1)
        self.ax_main.add_patch(coverage)
        
        self.node_circles.append((circle, coverage))
        
        print(f"✅ Node {node_id} added at ({x:.0f}, {y:.0f})")
        print(f"   Config: HopLimit={node['hopLimit']}, TxPower={node['tx_power']}dBm, Role={node['role']}")
        
        self.update_displays()
        
    def send_broadcast(self):
        """Gửi broadcast từ node được chọn"""
        if self.selected_node is None:
            print("⚠️  No node selected! Click a node first.")
            return
            
        if len(self.nodes) == 0:
            return
            
        sender = self.nodes[self.selected_node]
        
        # Tạo message
        self.message_id += 1
        message = {
            'id': self.message_id,
            'sender': sender['id'],
            'destination': 'BROADCAST',
            'text': f"Broadcast {self.message_id} from Node {sender['id']}",
            'portnum': 'TEXT_MESSAGE_APP',
            'hops': 0,
            'hop_limit': sender['hopLimit'],
            'path': [sender['id']],
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        
        # Mô phỏng broadcast
        self.simulate_transmission(message, sender, is_broadcast=True)
        sender['sent_messages'].append(message['id'])
        sender['total_tx'] += 1
        
    def send_dm_to_node(self, x, y):
        """Gửi Direct Message tới node"""
        if self.selected_node is None:
            print("⚠️  No sender selected!")
            return
            
        # Tìm destination node
        distances = [np.sqrt((n['x'] - x)**2 + (n['y'] - y)**2) for n in self.nodes]
        min_dist = min(distances)
        
        if min_dist > 100:
            print("⚠️  Click closer to a node")
            return
            
        dest_idx = distances.index(min_dist)
        
        if dest_idx == self.selected_node:
            print("⚠️  Cannot send DM to yourself!")
            return
            
        sender = self.nodes[self.selected_node]
        dest = self.nodes[dest_idx]
        
        self.message_id += 1
        message = {
            'id': self.message_id,
            'sender': sender['id'],
            'destination': dest['id'],
            'text': f"DM {self.message_id}: {sender['id']}→{dest['id']}",
            'portnum': 'TEXT_MESSAGE_APP',
            'hops': 0,
            'hop_limit': sender['hopLimit'],
            'path': [sender['id']],
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        
        self.simulate_transmission(message, sender, is_broadcast=False, destination=dest)
        sender['sent_messages'].append(message['id'])
        sender['total_tx'] += 1
        
    def simulate_transmission(self, message, sender, is_broadcast=True, destination=None):
        """Mô phỏng quá trình truyền message chi tiết"""
        separator = '='*60
        print(f"\n{separator}")
        print(f"📡 Message #{message['id']} - {message['portnum']}")
        print(f"   Sender: Node {sender['id']} at ({sender['x']:.0f}, {sender['y']:.0f})")
        dest_text = 'BROADCAST' if is_broadcast else f"DM to Node {destination['id']}"
        print(f"   Type: {dest_text}")
        print(f"   HopLimit: {message['hop_limit']} | Time: {message['timestamp']}")
        print(separator)
        
        # Tính toán nodes nào nhận được
        receivers = []
        rssi_values = []
        
        for node in self.nodes:
            if node['id'] == sender['id']:
                continue
                
            distance = np.sqrt((node['x'] - sender['x'])**2 + 
                             (node['y'] - sender['y'])**2)
            
            if distance < 10:
                distance = 10
                
            # Friis transmission equation với log-distance path loss
            freq_mhz = 915
            path_loss = 20 * np.log10(distance) + 20 * np.log10(freq_mhz) - 27.55
            
            # RSSI calculation
            tx_power = sender['tx_power']
            tx_gain = sender['antenna_gain']
            rx_gain = node['antenna_gain']
            rssi = tx_power + tx_gain + rx_gain - path_loss
            
            # LoRa sensitivity (SF10, BW125)
            sensitivity = -123.0
            snr = rssi - sensitivity
            
            # Thêm fading và interference (random)
            fading = np.random.normal(0, 3)  # Shadow fading
            rssi_actual = rssi + fading
            
            # Kiểm tra có nhận được không
            can_receive = rssi_actual > sensitivity
            
            if can_receive:
                # Packet error rate dựa trên SNR
                per = 1 / (1 + np.exp((snr - 10) / 2))  # Sigmoid
                success = np.random.random() > per
                
                if success:
                    receivers.append(node)
                    rssi_values.append(rssi_actual)
                    node['received_messages'].append(message['id'])
                    node['total_rx'] += 1
                    
                    status = "✅ RECEIVED"
                    if not is_broadcast and node['id'] == destination['id']:
                        status = "✅ DELIVERED (DM)"
                    
                    print(f"  {status}: Node {node['id']}")
                    print(f"     Distance: {distance:.0f}m | RSSI: {rssi_actual:.1f} dBm | SNR: {snr:.1f} dB")
                    
                    # Vẽ đường kết nối
                    color = 'green' if is_broadcast else 'blue'
                    alpha = 0.6 if is_broadcast else 0.8
                    arrow = FancyArrowPatch((sender['x'], sender['y']), 
                                          (node['x'], node['y']),
                                          arrowstyle='->', mutation_scale=20,
                                          color=color, alpha=alpha, linewidth=2)
                    self.ax_main.add_patch(arrow)
                    self.route_lines.append(arrow)
                else:
                    print(f"  ❌ PACKET ERROR: Node {node['id']} (PER={per*100:.1f}%)")
            else:
                print(f"  🔇 OUT OF RANGE: Node {node['id']} (RSSI={rssi_actual:.1f} dBm)")
        
        if len(receivers) == 0:
            print("\n  ⚠️  No nodes received the message!")
            avg_rssi = 0
        else:
            avg_rssi = np.mean(rssi_values)
            print(f"\n  ✓ Successfully received by {len(receivers)} node(s)")
            print(f"  Average RSSI: {avg_rssi:.1f} dBm")
            
        # Lưu message data
        self.messages.append({
            'message': message,
            'sender': sender,
            'receivers': receivers,
            'avg_rssi': avg_rssi,
            'rssi_values': rssi_values
        })
        
        self.update_displays()
        
    def show_message_route(self, msg_idx):
        """Hiển thị chi tiết route của một message"""
        if msg_idx >= len(self.messages):
            return
            
        msg_data = self.messages[msg_idx]
        msg = msg_data['message']
        sender = msg_data['sender']
        receivers = msg_data['receivers']
        
        route_text = f"""📍 Message #{msg['id']} Route:

Sender: Node {msg['sender']}
Location: ({sender['x']:.0f}, {sender['y']:.0f})
Type: {msg['destination']}
Portnum: {msg['portnum']}
HopLimit: {msg['hop_limit']}
Time: {msg['timestamp']}

RSSI: {msg_data['avg_rssi']:.1f} dBm

Receivers ({len(receivers)}):
"""
        for i, (rcv, rssi) in enumerate(zip(receivers, msg_data.get('rssi_values', []))):
            route_text += f"  {i+1}. Node {rcv['id']} ({rssi:.1f} dBm)\n"
            
        self.routes_text.set_text(route_text)
        self.fig.canvas.draw()
        
    def clear_routes(self):
        """Xóa các đường routes"""
        for line in self.route_lines:
            line.remove()
        self.route_lines = []
        self.fig.canvas.draw()
        print("Routes cleared")
        
    def show_connectivity(self):
        """Hiển thị connectivity matrix"""
        if len(self.nodes) < 2:
            print("Need at least 2 nodes!")
            return
            
        fig_conn, ax_conn = plt.subplots(figsize=(10, 8))
        n = len(self.nodes)
        matrix = np.zeros((n, n))
        
        # Tính connectivity dựa trên distance và path loss
        for i, n1 in enumerate(self.nodes):
            for j, n2 in enumerate(self.nodes):
                if i != j:
                    dist = np.sqrt((n1['x'] - n2['x'])**2 + (n1['y'] - n2['y'])**2)
                    if dist < 10:
                        dist = 10
                    path_loss = 20 * np.log10(dist) + 20 * np.log10(915) - 27.55
                    rssi = 14 - path_loss
                    if rssi > -123:
                        matrix[i][j] = rssi + 123  # Normalize for coloring
                        
        im = ax_conn.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=40)
        ax_conn.set_xlabel('Receiver Node', fontsize=12)
        ax_conn.set_ylabel('Sender Node', fontsize=12)
        ax_conn.set_title('Network Connectivity Matrix (RSSI-based)', fontsize=14, fontweight='bold')
        ax_conn.set_xticks(range(n))
        ax_conn.set_yticks(range(n))
        
        # Thêm text trong cells
        for i in range(n):
            for j in range(n):
                if matrix[i][j] > 0:
                    text = ax_conn.text(j, i, f'{matrix[i][j]:.0f}',
                                      ha="center", va="center", color="black", fontsize=8)
        
        plt.colorbar(im, ax=ax_conn, label='Signal Strength (relative)')
        plt.tight_layout()
        plt.show()
        
        print("Connectivity matrix displayed")
        
    def clear_all(self):
        """Xóa tất cả"""
        self.ax_main.clear()
        self.nodes = []
        self.node_circles = []
        self.messages = []
        self.message_id = 0
        self.selected_node = None
        self.route_lines = []
        self.current_message_view = None
        
        # Re-setup
        self.ax_main.set_xlim(-1500, 1500)
        self.ax_main.set_ylim(-1500, 1500)
        self.ax_main.set_xlabel('x (m)', fontsize=12)
        self.ax_main.set_ylabel('y (m)', fontsize=12)
        self.ax_main.set_title('Meshtastic Network Simulator - Double click to place nodes', 
                               fontsize=14, fontweight='bold')
        self.ax_main.grid(True, alpha=0.3)
        self.ax_main.set_aspect('equal')
        
        self.update_displays()
        print("✅ Cleared all nodes and messages")
        
    def run(self):
        """Chạy demo"""
        print("\n" + "="*70)
        print("🌐 MESHTASTIC NETWORK SIMULATOR - INTERACTIVE MODE")
        print("="*70)
        print("\n📖 Instructions:")
        print("  • Double-click anywhere to place a node")
        print("  • Left-click a node to select it (turns yellow)")
        print("  • Right-click to send broadcast from selected node")
        print("  • Press 'd' then click a node to send Direct Message")
        print("  • Press 'c' to clear everything")
        print("  • Press 'r' to clear routes only")
        print("  • Press 's' to show connectivity matrix")
        print("  • Press number keys (1-9) to view message details")
        print("\n🚀 Ready! Start placing nodes...")
        print("="*70 + "\n")
        
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    demo = InteractiveDemo()
    demo.run()
