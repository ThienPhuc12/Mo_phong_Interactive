#!/usr/bin/env python3
"""
Interactive demo - Mô phỏng Meshtastic network 100% chính xác
Dùng thuật toán vật lý từ lib/phy.py
"""
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
import numpy as np
import math
import random
from datetime import datetime
import sys
sys.path.insert(0, '.')
from lib.config import Config


class LoRaPacket:
    """Represents a LoRa packet with all properties"""
    def __init__(self, packet_id, tx_node_id, sf, bw, freq, tx_power, payload_length, is_ack=False, original_msg_id=None):
        self.packet_id = packet_id
        self.tx_node_id = tx_node_id
        self.sf = sf
        self.bw = bw
        self.freq = freq
        self.tx_power = tx_power
        self.payload_length = payload_length
        self.start_time = 0
        self.end_time = 0
        self.rssi_at_rx = {}
        self.collision_at_rx = {}
        self.is_ack = is_ack
        self.original_msg_id = original_msg_id


class InteractiveDemo:
    def __init__(self):
        self.conf = Config()
        self.fig = plt.figure(figsize=(16, 10))
        gs = self.fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        self.ax_main = self.fig.add_subplot(gs[0:3, 0:2])
        self.ax_stats = self.fig.add_subplot(gs[0, 2])
        # Messages dùng add_axes để điều chỉnh vị trí y
        self.ax_messages = self.fig.add_axes([0.80, 0.15, 0.25, 0.35])
        self.ax_routes = self.fig.add_subplot(gs[2, 2]) 
        
        self.nodes = []
        self.node_circles = []
        self.message_id = 0
        self.messages = []
        self.selected_node = None
        self.route_lines = []
        self.route_arrows = []  # Store FancyArrowPatch objects for hover
        self.route_annots = []  # Store annotations for hover
        self.current_message_view = None
        self.sim_time = 0
        
        self.packets_in_air = []
        
        self.setup_plot()
        self.connect_events()
        
    def setup_plot(self):
        """Thiết lập plot ban đầu"""
        self.ax_main.set_xlim(-1500, 1500)
        self.ax_main.set_ylim(-1500, 1500)
        self.ax_main.set_xlabel('x (m)', fontsize=12)
        self.ax_main.set_ylabel('y (m)', fontsize=12)
        self.ax_main.set_title('Meshtastic Network Simulator (Physics-Accurate)', 
                               fontsize=14, fontweight='bold')
        self.ax_main.grid(True, alpha=0.3)
        self.ax_main.set_aspect('equal')
        
        # Right side panels - separated vertically
        self.ax_stats.axis('off')
        self.ax_stats.set_xlim(0, 1)
        self.ax_stats.set_ylim(0, 1)
        self.stats_text = self.ax_stats.text(0.1, 0.95, self.get_stats_text(), 
                                            verticalalignment='top', fontsize=9,
                                            family='monospace',
                                            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.85, pad=0.5))
        
        self.ax_messages.axis('off')
        self.ax_messages.set_xlim(0, 1)
        self.ax_messages.set_ylim(0, 1)
        self.messages_text = self.ax_messages.text(0.1, 0.95, 'Messages:\n(No messages yet)', 
                                                   verticalalignment='top', fontsize=8,
                                                   family='monospace',
                                                   bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.85, pad=0.5))
        
        self.ax_routes.axis('off')
        self.ax_routes.set_xlim(0, 1)
        self.ax_routes.set_ylim(0, 1)
        self.routes_text = self.ax_routes.text(0.1, 0.95, 'Route Details:\n(Enter Msg ID)', 
                                              verticalalignment='top', fontsize=8,
                                              family='monospace',
                                              bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.85, pad=0.5))
        
        # Controls panel - Left Top
        ax_controls = self.fig.add_axes([0.02, 0.65, 0.25, 0.25])
        ax_controls.axis('off')
        ax_controls.text(0, 1, '🎮 Controls:\n'
                              '• Double click: Place\n'
                              '• Click: Select (yellow)\n'
                              '• Right click: Broadcast\n'
                              '• "d"+click: Send DM\n'
                              '• "t"+click: Traceroute\n'
                              '• "p"+click: Ping\n'
                              '• "c": Clear | "r": Routes',
                        verticalalignment='top', fontsize=8,
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8, pad=0.5),
                        transform=ax_controls.transAxes)
        
        # Legend panel - Left Bottom
        ax_legend = self.fig.add_axes([0.02, 0.35, 0.25, 0.25])
        ax_legend.axis('off')
        ax_legend.text(0, 1, '📊 Legend:\n'
                            '• Green: Broadcast\n'
                            '• Blue: Direct Msg\n'
                            '• Red dash: ACK\n'
                            '• Hover → info',
                      verticalalignment='top', fontsize=8,
                      bbox=dict(boxstyle='round', facecolor='lightcyan', alpha=0.8, pad=0.5),
                      transform=ax_legend.transAxes)
        
    def connect_events(self):
        """Kết nối các event handlers"""
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_hover)
        self.dm_mode = False
        self.traceroute_mode = False
        self.ping_mode = False
        self.zoom_scale = 1.0
        
        # Add TextBox for message ID input
        from matplotlib.widgets import TextBox
        self.fig.subplots_adjust(bottom=0.12)
        axbox = self.fig.add_axes([0.35, 0.02, 0.15, 0.04])
        self.text_box = TextBox(axbox, 'Message ID: ', initial='1', label_pad=0.01)
        self.text_box.on_submit(self.on_textbox_submit)
        
    def get_stats_text(self):
        """Tạo text thống kê"""
        total_msgs = len(self.messages)
        total_nodes = len(self.nodes)
        
        if total_nodes == 0:
            return "📊 Network Stats:\n\nNo nodes yet\n\nPlace nodes to start!"
        
        # Count ACKs
        total_acks = sum(1 for m in self.messages if m['message'].get('is_ack', False))
        total_data_msgs = total_msgs - total_acks
        
        total_transmissions = sum(len(m['receivers']) for m in self.messages)
        avg_receivers = total_transmissions / total_msgs if total_msgs > 0 else 0
        
        reachable_pairs = 0
        total_pairs = total_nodes * (total_nodes - 1)
        
        for i, n1 in enumerate(self.nodes):
            for j, n2 in enumerate(self.nodes):
                if i != j:
                    dist = self._calc_dist_3d(n1['x'], n2['x'], n1['y'], n2['y'], n1['height'], n2['height'])
                    path_loss = self._estimate_path_loss(dist)
                    # Use same logic as calc_receivers: RSSI = PTX + antenna_gain - pathLoss
                    rssi = self.conf.PTX + self.conf.GL - path_loss
                    if rssi >= self.conf.SENSMODEM[self.conf.MODEM]:
                        reachable_pairs += 1
        
        coverage = (reachable_pairs / total_pairs * 100) if total_pairs > 0 else 0
        
        collided = sum(m['collisions'] for m in self.messages)
        success_rate = ((total_transmissions - collided) / total_transmissions * 100) if total_transmissions > 0 else 0
        
        stats = f"""📊 Network Stats:
        
Nodes: {total_nodes}
Messages: {total_data_msgs}
ACKs: {total_acks}
Total: {total_msgs}
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
        
    def _calc_dist_3d(self, x0, x1, y0, y1, z0=0, z1=0):
        """Calculate 3D distance between two points"""
        return np.sqrt(((abs(x0-x1))**2)+((abs(y0-y1))**2)+((abs(z0-z1)**2)))
    
    def _estimate_path_loss(self, dist):
        """Path loss using 3GPP Suburban Macro Model (Model 5)"""
        if dist < 0.001:
            dist = 0.001
            
        freq = self.conf.FREQ
        txZ = self.conf.HM
        rxZ = self.conf.HM
        C = 0
        
        path_loss = (44.9 - 6.55 * math.log10(txZ)) * (math.log10(dist) - 3.0) \
                  + 45.5 + (35.46 - 1.1 * rxZ) * (math.log10(freq) - 6.0) \
                  - 13.82 * math.log10(rxZ) + 0.7 * rxZ + C
        
        return path_loss
    
    def _calculate_airtime(self, payload_length):
        """Calculate airtime based on LoRa spec"""
        sf = self.conf.SFMODEM[self.conf.MODEM]
        bw = self.conf.BWMODEM[self.conf.MODEM]
        cr = self.conf.CRMODEM[self.conf.MODEM]
        pl = payload_length + self.conf.HEADERLENGTH
        
        H = 0
        DE = 0
        
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
        
        return int((Tpream + Tpayload) * 1000)
    
    def _frequency_collision(self, p1, p2):
        """Check frequency collision"""
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
        power_threshold = 6
        rssi1 = p1.rssi_at_rx.get(rx_node_id, -200)
        rssi2 = p2.rssi_at_rx.get(rx_node_id, -200)
        
        if abs(rssi1 - rssi2) < power_threshold:
            return (p1, p2)
        elif rssi1 - rssi2 < power_threshold:
            return (p1,)
        return (p2,)
    
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
        """Check for collisions"""
        collided = False
        
        for existing_packet in self.packets_in_air:
            for rx_node_id in [n['id'] for n in self.nodes]:
                if rx_node_id not in new_packet.rssi_at_rx:
                    continue
                if rx_node_id not in existing_packet.rssi_at_rx:
                    continue
                
                if (self._frequency_collision(new_packet, existing_packet) and
                    self._sf_collision(new_packet, existing_packet) and
                    self._timing_collision(new_packet, existing_packet)):
                    
                    casualties = self._power_collision(new_packet, existing_packet, rx_node_id)
                    for p in casualties:
                        if p.packet_id == new_packet.packet_id:
                            collided = True
                        p.collision_at_rx[rx_node_id] = True
        
        return collided
        
    def update_displays(self):
        """Update all displays"""
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
        """Handle click events"""
        if event.inaxes != self.ax_main:
            return
            
        if event.dblclick:
            self.add_node(event.xdata, event.ydata)
        elif event.button == 1:  # Left click
            if self.dm_mode:
                self.send_dm_to_node(event.xdata, event.ydata)
                self.dm_mode = False
            elif self.traceroute_mode:
                self.send_traceroute_to_node(event.xdata, event.ydata)
                self.traceroute_mode = False
            elif self.ping_mode:
                self.send_ping_to_node(event.xdata, event.ydata)
                self.ping_mode = False
            else:
                self.select_node(event.xdata, event.ydata)
        elif event.button == 3:  # Right click
            self.send_broadcast()
                
    def on_textbox_submit(self, text):
        """Handle TextBox submit"""
        try:
            msg_id = int(text)
            if 1 <= msg_id <= len(self.messages):
                self.show_message_route_detailed(msg_id)
            else:
                print(f"⚠️  Message ID {msg_id} not found. Valid range: 1-{len(self.messages)}")
        except ValueError:
            print("⚠️  Please enter a valid number")
    
    def on_hover(self, event):
        """Handle hover over arrows to show annotations"""
        if event.inaxes != self.ax_main:
            return
            
        found = False
        for i, arrow in enumerate(self.route_arrows):
            if i < len(self.route_annots):
                annot = self.route_annots[i]
                cont, _ = arrow.contains(event)
                if cont:
                    annot.set_visible(True)
                    found = True
                    self.fig.canvas.draw_idle()
                    break
        
        if not found:
            # Hide all annotations if not hovering over any arrow
            for annot in self.route_annots:
                if annot.get_visible():
                    annot.set_visible(False)
                    self.fig.canvas.draw_idle()
    
    def on_key(self, event):
        """Handle key events"""
        if event.key == 'c':
            self.clear_all()
        elif event.key == 'r':
            self.clear_routes()
        elif event.key == 'd':
            if self.selected_node is not None:
                self.dm_mode = True
                print(f"💬 DM mode: Node {self.selected_node} ready - Click ANOTHER node to send DM")
            else:
                print("⚠️  Select a sender node first (click a node)")
        elif event.key == 't':
            # Traceroute mode
            if self.selected_node is not None:
                self.traceroute_mode = True
                print(f"🔍 Traceroute mode: Node {self.selected_node} ready - Click ANOTHER node")
            else:
                print("⚠️  Select a sender node first (click a node)")
        elif event.key == 'p':
            # Ping mode  
            if self.selected_node is not None:
                self.ping_mode = True
                print(f"🏓 Ping mode: Node {self.selected_node} ready - Click ANOTHER node")
            else:
                print("⚠️  Select a sender node first (click a node)")
        elif event.key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            msg_id = int(event.key)
            if msg_id <= len(self.messages):
                self.current_message_view = msg_id - 1
                self.show_message_route(self.current_message_view)
    
    def on_scroll(self, event):
        """Handle zoom (scroll wheel)"""
        if event.inaxes != self.ax_main:
            return
        
        # Get current axis limits
        cur_xlim = self.ax_main.get_xlim()
        cur_ylim = self.ax_main.get_ylim()
        
        # Get event location
        xdata = event.xdata
        ydata = event.ydata
        
        # Zoom factor
        if event.button == 'up':
            scale_factor = 0.8  # Zoom in
        elif event.button == 'down':
            scale_factor = 1.2  # Zoom out
        else:
            return
        
        # Calculate new limits (zoom towards mouse position)
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        
        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
        
        self.ax_main.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * relx])
        self.ax_main.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])
        
        self.fig.canvas.draw()
        print(f"Zoomed: {1/scale_factor:.1f}x")
                
    def select_node(self, x, y):
        """Select nearest node"""
        if len(self.nodes) == 0:
            return
            
        distances = [np.sqrt((n['x'] - x)**2 + (n['y'] - y)**2) for n in self.nodes]
        min_dist = min(distances)
        
        if min_dist < 100:
            clicked_node = distances.index(min_dist)
            
            # If clicking same node, deselect it
            if self.selected_node == clicked_node:
                self.node_circles[self.selected_node][0].set_color('blue')
                self.selected_node = None
                print(f"Deselected Node {clicked_node}")
            else:
                # Deselect old node
                if self.selected_node is not None and self.selected_node < len(self.node_circles):
                    self.node_circles[self.selected_node][0].set_color('blue')
                
                # Select new node
                self.selected_node = clicked_node
                self.node_circles[self.selected_node][0].set_color('yellow')
                print(f"✅ Selected Node {self.selected_node} - Ready to send messages")
            
            self.update_displays()
            
    def add_node(self, x, y):
        """Add a new node"""
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
        
        circle = Circle((x, y), 50, color='blue', alpha=0.7, linewidth=2, edgecolor='darkblue')
        self.ax_main.add_patch(circle)
        self.ax_main.text(x, y, str(node_id), ha='center', va='center', 
                         color='white', fontweight='bold', fontsize=12)
        
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
        """Estimate max range based on link budget"""
        max_path_loss = self.conf.PTX + self.conf.GL - self.conf.SENSMODEM[self.conf.MODEM]
        
        dist = 1
        while self._estimate_path_loss(dist) < max_path_loss and dist < 10000:
            dist += 1
        
        return dist
        
    def send_broadcast(self):
        """Send broadcast from selected node"""
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
        """Send DM to node"""
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
            print(f"⚠️  Cannot send DM to yourself! Node {self.selected_node} is already selected.")
            print(f"   Click on Node {[i for i in range(len(self.nodes)) if i != self.selected_node][0] if len(self.nodes) > 1 else '?'} instead")
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
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_ack': False,
            'request_ack': True
        }
        
        # Gửi DM và nhận ACK response
        success = self.simulate_transmission(message, sender, is_broadcast=False, destination=dest)
        sender['sent_messages'].append(message['id'])
        sender['total_tx'] += 1
        
        # Nếu destination nhận được message, gửi ACK ngược lại
        if success and dest['id'] in [n['id'] for n in self.messages[-1]['receivers']]:
            self.send_ack(dest, sender, message['id'])
        
    def send_traceroute_to_node(self, x, y):
        """Send traceroute to node"""
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
            print(f"⚠️  Cannot traceroute to yourself! Node {self.selected_node} is selected.")
            print(f"   Click on a DIFFERENT node")
            return
            
        sender = self.nodes[self.selected_node]
        dest = self.nodes[dest_idx]
        
        self.message_id += 1
        message = {
            'id': self.message_id,
            'sender': sender['id'],
            'destination': dest['id'],
            'text': f"Traceroute: {sender['id']}→{dest['id']}",
            'portnum': 'TRACEROUTE_APP',
            'hop_limit': sender['hopLimit'],
            'path': [sender['id']],
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_ack': False,
            'request_ack': True
        }
        
        print(f"\n🔍 Traceroute from Node {sender['id']} to Node {dest['id']}")
        success = self.simulate_transmission(message, sender, is_broadcast=False, destination=dest)
        sender['sent_messages'].append(message['id'])
        sender['total_tx'] += 1
        
        if success and dest['id'] in [n['id'] for n in self.messages[-1]['receivers']]:
            self.send_ack(dest, sender, message['id'])
    
    def send_ping_to_node(self, x, y):
        """Send ping to node"""
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
            print(f"⚠️  Cannot ping yourself! Node {self.selected_node} is selected.")
            print(f"   Click on a DIFFERENT node")
            return
            
        sender = self.nodes[self.selected_node]
        dest = self.nodes[dest_idx]
        
        self.message_id += 1
        message = {
            'id': self.message_id,
            'sender': sender['id'],
            'destination': dest['id'],
            'text': f"Ping: {sender['id']}→{dest['id']}",
            'portnum': 'ROUTING_APP',
            'hop_limit': sender['hopLimit'],
            'path': [sender['id']],
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_ack': False,
            'request_ack': True
        }
        
        print(f"\n🏓 Ping from Node {sender['id']} to Node {dest['id']}")
        success = self.simulate_transmission(message, sender, is_broadcast=False, destination=dest)
        sender['sent_messages'].append(message['id'])
        sender['total_tx'] += 1
        
        if success and dest['id'] in [n['id'] for n in self.messages[-1]['receivers']]:
            self.send_ack(dest, sender, message['id'])
    
    def send_ack(self, sender, destination, original_msg_id):
        """Gửi ACK response"""
        self.message_id += 1
        ack_message = {
            'id': self.message_id,
            'sender': sender['id'],
            'destination': destination['id'],
            'text': f"ACK: {sender['id']}→{destination['id']}",
            'portnum': 'ROUTING_APP',
            'hop_limit': sender['hopLimit'],
            'path': [sender['id']],
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'is_ack': True,
            'original_msg_id': original_msg_id
        }
        
        print(f"\n📨 Sending ACK: Node {sender['id']} → Node {destination['id']} (for Msg #{original_msg_id})")
        self.simulate_transmission(ack_message, sender, is_broadcast=False, destination=destination, is_ack=True)
        sender['sent_messages'].append(ack_message['id'])
        sender['total_tx'] += 1
    
    def simulate_transmission(self, message, sender, is_broadcast=True, destination=None, hop=0, is_ack=False):
        """Simulate transmission with collision detection and mesh routing"""
        separator = '='*60
        print(f"\n{separator}")
        hop_text = f" [HOP {hop}]" if hop > 0 else ""
        ack_text = " [ACK]" if is_ack else ""
        print(f"📡 Message #{message['id']} Transmission{hop_text}{ack_text} (Physics-Based)")
        print(f"   Sender: Node {sender['id']} at ({sender['x']:.0f}, {sender['y']:.0f})")
        dest_text = 'BROADCAST' if is_broadcast else f"DM to Node {destination['id']}"
        if is_ack:
            dest_text += f" (ACK for Msg #{message.get('original_msg_id', '?')})"
        print(f"   Type: {dest_text} | HopLimit: {message['hop_limit']}")
        print(separator)
        
        packet = LoRaPacket(
            packet_id=message['id'],
            tx_node_id=sender['id'],
            sf=self.conf.SFMODEM[self.conf.MODEM],
            bw=self.conf.BWMODEM[self.conf.MODEM],
            freq=self.conf.FREQ,
            tx_power=sender['tx_power'],
            payload_length=self.conf.PACKETLENGTH,
            is_ack=is_ack,
            original_msg_id=message.get('original_msg_id')
        )
        
        airtime_ms = self._calculate_airtime(self.conf.PACKETLENGTH)
        packet.start_time = self.sim_time
        packet.end_time = self.sim_time + airtime_ms
        self.sim_time += airtime_ms
        
        print(f"   Airtime: {airtime_ms}ms | SF: {packet.sf} | BW: {packet.bw/1e3:.0f}kHz")
        
        receivers = []
        rssi_values = []
        collision_count = 0
        
        for node in self.nodes:
            if node['id'] == sender['id']:
                continue
            
            # Skip if already received this message (avoid duplicate processing)
            if message['id'] in node.get('received_messages', []):
                continue
                
            # Calculate 3D distance (include height)
            distance = self._calc_dist_3d(sender['x'], node['x'], sender['y'], node['y'], 
                                         sender['height'], node['height'])
            
            # Calculate path loss (same as interactive.py calc_receivers)
            path_loss = self._estimate_path_loss(distance)
            # RSSI = PTX + tx_antenna_gain - pathLoss (interactive.py line 715)
            rssi = self.conf.PTX + sender['antenna_gain'] - path_loss
            
            packet.rssi_at_rx[node['id']] = rssi
            packet.collision_at_rx[node['id']] = False
            
            sensitivity = self.conf.SENSMODEM[self.conf.MODEM]
            
            # Check if can receive (interactive.py line 716)
            if rssi >= sensitivity:
                # SNR = RSSI - NOISE_LEVEL (interactive.py line 717)
                snr = rssi - self.conf.NOISE_LEVEL
                receivers.append(node)
                rssi_values.append(rssi)
                node['received_messages'].append(message['id'])
                node['total_rx'] += 1
                
                print(f"  ✅ RECEIVED: Node {node['id']}")
                print(f"     Dist: {distance:.0f}m | RSSI: {rssi:.1f}dBm | SNR: {snr:.1f}dB")
                
                # Màu sắc: đỏ cho ACK, xanh lá cho broadcast, xanh dương cho DM
                if is_ack:
                    color = 'red'
                    linestyle = '--'
                elif is_broadcast:
                    color = 'green'
                    linestyle = '-'
                else:
                    color = 'blue'
                    linestyle = '-'
                
                # Draw arrow immediately for basic visualization
                # Red curves UP (less), Blue curves DOWN (more)
                if color == 'red':
                    connectionstyle = "arc3,rad=0.1"
                elif color == 'blue':
                    connectionstyle = "arc3,rad=-0.2"
                else:  # green
                    connectionstyle = "arc3,rad=0"
                    
                arrow = FancyArrowPatch((sender['x'], sender['y']), 
                                      (node['x'], node['y']),
                                      arrowstyle='->', mutation_scale=20,
                                      color=color, alpha=0.6, linewidth=2,
                                      linestyle=linestyle, connectionstyle=connectionstyle)
                self.ax_main.add_patch(arrow)
                self.route_lines.append(arrow)
                self.fig.canvas.draw_idle()
                    
                # Store color info for later detailed view
                if not hasattr(self, '_temp_arrow_colors'):
                    self._temp_arrow_colors = {}
                self._temp_arrow_colors[(message['id'], sender['id'], node['id'])] = (color, linestyle)
            else:
                print(f"  🔇 OUT OF RANGE: Node {node['id']} (RSSI={rssi:.1f}dBm < {sensitivity}dBm)")
        
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
        
        # Return success (có node nhận được không)
        success = len(receivers) > 0
        
        # MESH ROUTING: Only Router/Repeater nodes rebroadcast (like real Meshtastic)
        # Không relay ACKs (ACKs chỉ đi direct)
        if not is_ack and message['hop_limit'] > 0 and len(receivers) > 0:
            # Decrement hop limit
            message['hop_limit'] -= 1
            message['path'].append(sender['id'])
            
            # Filter only Router/Repeater nodes that can relay
            relay_capable_nodes = [n for n in receivers if n['role'] in ['Router', 'Repeater']]
            
            if len(relay_capable_nodes) > 0:
                print(f"🔁 MESH ROUTING: {len(relay_capable_nodes)}/{len(receivers)} nodes will rebroadcast (HopLimit: {message['hop_limit']})")
                
                # Each Router/Repeater rebroadcasts the message
                for relay_node in relay_capable_nodes:
                    # Skip if already in path (avoid loops)
                    if relay_node['id'] in message['path']:
                        print(f"   ⏩ Node {relay_node['id']} skipped (already in path)")
                        continue
                    
                    print(f"   🔄 Node {relay_node['id']} ({relay_node['role']}) rebroadcasting...")
                    # Recursive call for mesh routing
                    self.simulate_transmission(message, relay_node, is_broadcast, destination, hop=hop+1)
            else:
                print(f"⚠️  No Router/Repeater nodes to relay (all {len(receivers)} receivers are Clients)")
        
        self.update_displays()
        return success
        
    def show_message_route(self, msg_idx):
        """Show message route details (simple version)"""
        if msg_idx >= len(self.messages):
            return
            
        msg_data = self.messages[msg_idx]
        msg = msg_data['message']
        sender = msg_data['sender']
        receivers = msg_data['receivers']
        
        collision_info = ""
        if msg_data['collisions'] > 0:
            collision_info = f"\n⚠️  COLLISIONS: {msg_data['collisions']}"
        
        ack_info = ""
        if msg.get('is_ack', False):
            ack_info = f"\n📨 ACK for Msg #{msg.get('original_msg_id', '?')}"
        
        route_text = f"""📍 Message #{msg['id']} Route:

Sender: Node {msg['sender']}
Location: ({sender['x']:.0f}, {sender['y']:.0f})
Type: {msg['destination']}{ack_info}
HopLimit: {msg['hop_limit']}
Airtime: {msg_data['airtime']}ms{collision_info}

RSSI: {msg_data['avg_rssi']:.1f} dBm

Receivers ({len(receivers)}):
"""
        for i, (rcv, rssi) in enumerate(zip(receivers, msg_data.get('rssi_values', []))):
            route_text += f"  {i+1}. Node {rcv['id']} ({rssi:.1f}dBm)\n"
            
        self.routes_text.set_text(route_text)
        self.fig.canvas.draw()
    
    def show_message_route_detailed(self, message_id):
        """Show message route with interactive arrows and hover annotations"""
        # Clear previous routes
        self.clear_routes()
        
        # Find all messages with this ID (including ACKs and relays)
        matching_msgs = [m for m in self.messages if m['message']['id'] == message_id or 
                        m['message'].get('original_msg_id') == message_id]
        
        if len(matching_msgs) == 0:
            print(f'Could not find message ID {message_id}.')
            return
        
        print(f'\n📍 Plotting route for message {message_id} and ACKs...')
        print('Hover over arrows to see details, click to hide annotations.')
        
        # Track arrow counts between node pairs to create arc effect
        pair_counts = {}
        
        for msg_data in matching_msgs:
            msg = msg_data['message']
            sender = msg_data['sender']
            receivers = msg_data['receivers']
            
            for ri, receiver in enumerate(receivers):
                # Determine arc radius based on how many arrows between this pair
                pair_key = (sender['id'], receiver['id'])
                if pair_key not in pair_counts:
                    pair_counts[pair_key] = 0
                pair_counts[pair_key] += 1
                arc_count = pair_counts[pair_key]
                
                # Determine color
                color_key = (msg['id'], sender['id'], receiver['id'])
                if hasattr(self, '_temp_arrow_colors') and color_key in self._temp_arrow_colors:
                    color, linestyle = self._temp_arrow_colors[color_key]
                else:
                    # Fallback
                    if msg.get('is_ack', False):
                        color, linestyle = 'red', '--'
                    elif msg['destination'] == 'BROADCAST':
                        color, linestyle = 'green', '-'
                    else:
                        color, linestyle = 'blue', '-'
                
                # Create arc-style arrow: red curves up (less), blue curves down (more)
                if color == 'red':
                    rad_value = 0.1  # Less curve UP
                elif color == 'blue':
                    rad_value = -0.2  # More curve DOWN
                else:  # green
                    rad_value = 0
                connectionstyle = f"arc3,rad={rad_value}"
                
                arrow = FancyArrowPatch(
                    (sender['x'], sender['y']),
                    (receiver['x'], receiver['y']),
                    arrowstyle='->', 
                    mutation_scale=20,
                    connectionstyle=connectionstyle,
                    color=color,
                    linestyle=linestyle,
                    alpha=0.7,
                    linewidth=2.5
                )
                self.ax_main.add_patch(arrow)
                self.route_arrows.append(arrow)
                
                # Determine message type (like interactive.py)
                if msg.get('is_ack', False):
                    if msg['sender'] == receiver['id']:
                        msg_type = "Implicit ACK"
                    else:
                        msg_type = "Real ACK"
                elif msg['sender'] == sender['id']:
                    msg_type = "Original message"
                else:
                    if msg['destination'] == 'BROADCAST':
                        msg_type = "Rebroadcast"
                    else:
                        msg_type = "Forwarding message"
                
                # Create annotation
                rssi_val = msg_data['rssi_values'][ri] if ri < len(msg_data['rssi_values']) else 0
                snr_val = rssi_val - self.conf.NOISE_LEVEL
                
                dest_text = msg['destination'] if msg['destination'] != 'BROADCAST' else 'All'
                portnum = msg.get('portnum', 'TEXT_MESSAGE_APP')
                
                annotation_text = (
                    f"Type: {msg_type}\n"
                    f"From Node: {sender['id']}\n"
                    f"To Node: {receiver['id']}\n"
                    f"Destination: {dest_text}\n"
                    f"Portnum: {portnum}\n"
                    f"HopLimit: {msg['hop_limit']}\n"
                    f"RSSI: {rssi_val:.1f} dBm\n"
                    f"SNR: {snr_val:.1f} dB"
                )
                
                # Position annotation at midpoint
                mid_x = (sender['x'] + receiver['x']) / 2
                mid_y = (sender['y'] + receiver['y']) / 2 + 100
                
                annot = self.ax_main.annotate(
                    annotation_text,
                    xy=(mid_x, mid_y),
                    xytext=(mid_x, mid_y),
                    bbox=dict(boxstyle="round,pad=0.5", fc=color, alpha=0.3, ec=color),
                    fontsize=8,
                    visible=False
                )
                self.route_annots.append(annot)
        
        self.ax_main.set_title(f'Route of message {message_id} and ACKs - Hover over arrows for details', 
                              fontsize=12, fontweight='bold')
        self.fig.canvas.draw_idle()
        
        # Update stats display
        self.update_displays()
        
    def clear_routes(self):
        """Clear routes"""
        for line in self.route_lines:
            if line in self.ax_main.patches:
                line.remove()
        self.route_lines = []
        
        for arrow in self.route_arrows:
            if arrow in self.ax_main.patches:
                arrow.remove()
        self.route_arrows = []
        
        for annot in self.route_annots:
            annot.remove()
        self.route_annots = []
        
        self.ax_main.set_title('Meshtastic Network Simulator (Physics-Accurate) - Double click to place nodes',
                              fontsize=14, fontweight='bold')
        self.fig.canvas.draw()
        print("Routes cleared")
        
    def clear_all(self):
        """Clear all"""
        self.ax_main.clear()
        self.nodes = []
        self.node_circles = []
        self.messages = []
        self.packets_in_air = []
        self.message_id = 0
        self.selected_node = None
        self.route_lines = []
        self.route_arrows = []
        self.route_annots = []
        self.current_message_view = None
        self.sim_time = 0
        if hasattr(self, '_temp_arrow_colors'):
            self._temp_arrow_colors = {}
        
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
        """Run demo"""
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


if __name__ == "__main__":
    demo = InteractiveDemo()
    demo.run()
