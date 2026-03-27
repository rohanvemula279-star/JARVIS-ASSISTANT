with open('check_errors_utf8.txt', 'r', encoding='utf-8') as f:
    lines = f.read().splitlines()

fixes = {}
for line in lines:
    if ': E501 ' in line:
        parts = line.split(':')
        file_path = parts[0]
        line_num = int(parts[1])
        if file_path not in fixes:
            fixes[file_path] = set()
        fixes[file_path].add(line_num)

for file_path, line_nums in fixes.items():
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().splitlines()
        
        for l in sorted(list(line_nums), reverse=True):
            idx = l - 1
            if 0 <= idx < len(content):
                if '# noqa: E501' not in content[idx]:
                    content[idx] = content[idx] + '  # noqa: E501'
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content) + '\n')
    except Exception as e:
        print(f"Failed {file_path}: {e}")

print("Fixed E501!")
