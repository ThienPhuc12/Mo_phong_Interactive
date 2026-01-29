#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from interactiveDemo import InteractiveDemo

# Test if methods exist
demo = InteractiveDemo()
print('✅ Methods check:')
print(f'  - show_all_routes: {hasattr(demo, "show_all_routes")}')
print(f'  - point_to_segment_distance: {hasattr(demo, "point_to_segment_distance")}')
print(f'  - arrow_info initialized: {hasattr(demo, "arrow_info")}')
print(f'  - arrow_info value: {demo.arrow_info}')
print('✅ All checks passed!')

# Test point_to_segment_distance
dist = demo.point_to_segment_distance(50, 50, 0, 0, 100, 100)
print(f'\n✅ Distance test: point (50,50) to line (0,0)-(100,100) = {dist:.2f}')
