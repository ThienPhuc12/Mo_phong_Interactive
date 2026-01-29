#!/usr/bin/env python3
"""Test if FancyArrowPatch.contains() works with motion_notify_event"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots()

# Create FancyArrowPatch
arrow = patches.FancyArrowPatch((0, 0), (100, 100), 
                               arrowstyle='->', 
                               color='blue',
                               mutation_scale=20)
ax.add_patch(arrow)

ax.set_xlim(-50, 150)
ax.set_ylim(-50, 150)

# Simulate motion event
class FakeEvent:
    def __init__(self, x, y, inaxes):
        self.xdata = x
        self.ydata = y
        self.inaxes = inaxes
        
    def __repr__(self):
        return f"Event({self.xdata}, {self.ydata})"

# Test 1: Point on the arrow line (should be contained)
event1 = FakeEvent(50, 50, ax)
try:
    cont1, _ = arrow.contains(event1)
    print(f"Test 1 - Point (50,50) on line: contains={cont1}")
except Exception as e:
    print(f"Test 1 - Error: {e}")

# Test 2: Point far from arrow (should not be contained)
event2 = FakeEvent(150, 50, ax)
try:
    cont2, _ = arrow.contains(event2)
    print(f"Test 2 - Point (150,50) far away: contains={cont2}")
except Exception as e:
    print(f"Test 2 - Error: {e}")

# Test 3: Point near arrow (close to line)
event3 = FakeEvent(55, 50, ax)
try:
    cont3, _ = arrow.contains(event3)
    print(f"Test 3 - Point (55,50) near line: contains={cont3}")
except Exception as e:
    print(f"Test 3 - Error: {e}")

print("\nConclusion: FancyArrowPatch.contains() should work with real events")
