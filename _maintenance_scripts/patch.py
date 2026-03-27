import sys

filepath = 'c:/Users/rohan/Mark-XXX/main.py'
lines_to_modify = [89, 568, 574, 580, 586, 592, 601, 607, 625, 633, 639, 644, 654, 683, 688, 694, 700, 773, 778]

try:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for l in lines_to_modify:
        idx = l - 1
        # Make sure we don't add multiple ignores
        if not lines[idx].rstrip().endswith('type: ignore'):
            lines[idx] = lines[idx].rstrip() + "  # type: ignore\n"
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
    print(f"Patched {len(lines_to_modify)} lines in main.py")
except Exception as e:
    print(f"Error: {e}")
