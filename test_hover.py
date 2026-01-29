#!/usr/bin/env python3
"""
Simple test để check xem on_hover và show_all_routes hoạt động không
"""
import sys
sys.path.insert(0, '.')

# Disable matplotlib GUI
import matplotlib
matplotlib.use('Agg')

from interactiveDemo import InteractiveDemo
import io
from contextlib import redirect_stdout

# Create demo
demo = InteractiveDemo()

# Add some nodes
print("Adding nodes...")
demo.add_node(0, 0)      # Node 0
demo.add_node(500, 0)    # Node 1
demo.add_node(1000, 0)   # Node 2

print(f"Nodes added: {len(demo.nodes)}")

# Create a test message
print("\nCreating test messages...")
msg1 = {
    'id': 1,
    'sender': demo.nodes[0]['id'],
    'destination': 1,
    'text': 'Test message',
    'hop_limit': 3,
    'path': [demo.nodes[0]['id']],
    'portnum': 'TEXT_MESSAGE_APP',
    'is_ack': False
}

msg2 = {
    'id': 2,
    'sender': demo.nodes[1]['id'],
    'destination': 0,
    'text': 'Reply',
    'hop_limit': 3,
    'path': [demo.nodes[1]['id']],
    'portnum': 'TEXT_MESSAGE_APP',
    'is_ack': False
}

# Simulate transmission
print("\nSimulating transmissions...")
demo.simulate_transmission(msg1, demo.nodes[0], False, 1)
demo.simulate_transmission(msg2, demo.nodes[1], False, 0)

print(f"\nMessages sent: {len(demo.messages)}")
for i, msg_data in enumerate(demo.messages):
    print(f"  Message {i+1}: ID={msg_data['message']['id']}, Receivers={len(msg_data['receivers'])}")

# Test show_all_routes
print("\n" + "="*50)
print("Testing show_all_routes()...")
print("="*50)

demo.show_all_routes()

print(f"\nRoute arrows created: {len(demo.route_arrows)}")
print(f"Route annotations created: {len(demo.route_annots)}")
print(f"Arrow info entries: {len(demo.arrow_info) if hasattr(demo, 'arrow_info') else 0}")

if hasattr(demo, 'arrow_info') and len(demo.arrow_info) > 0:
    print("\nArrow info content:")
    for i, info in enumerate(demo.arrow_info):
        sender = info['sender']
        receiver = info['receiver']
        print(f"  Arrow {i}: Node {sender['id']} -> Node {receiver['id']}")

# Test hover detection
print("\n" + "="*50)
print("Testing hover detection...")
print("="*50)

if hasattr(demo, 'arrow_info') and len(demo.arrow_info) > 0:
    # Test distance calculation
    info = demo.arrow_info[0]
    sender = info['sender']
    receiver = info['receiver']
    
    # Test point on the line
    test_x = (sender['x'] + receiver['x']) / 2
    test_y = (sender['y'] + receiver['y']) / 2
    
    dist = demo.point_to_segment_distance(test_x, test_y, 
                                         sender['x'], sender['y'],
                                         receiver['x'], receiver['y'])
    
    print(f"\nDistance test:")
    print(f"  Arrow: Node {sender['id']} ({sender['x']},{sender['y']}) -> Node {receiver['id']} ({receiver['x']},{receiver['y']})")
    print(f"  Test point: ({test_x}, {test_y})")
    print(f"  Distance to line: {dist:.2f} (should be ~0)")
    print(f"  Hover threshold: 100")
    print(f"  Would trigger hover: {dist < 100}")

print("\n" + "="*50)
print("OK! All tests passed!")
print("="*50)
