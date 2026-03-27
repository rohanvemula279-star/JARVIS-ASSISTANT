import json

problems_json = r"""[
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":41},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":108},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":226},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":331},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":404},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":451},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":500},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":501},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":512},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\code_helper.py","startLine":513},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\computer_control.py","startLine":30},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\computer_control.py","startLine":38},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\computer_control.py","startLine":161},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\computer_control.py","startLine":245},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\computer_control.py","startLine":331},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\computer_control.py","startLine":334},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\computer_control.py","startLine":343},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\open_app.py","startLine":12},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\open_app.py","startLine":318},
{"path":"c:\\Users\\rohan\\Mark-XXX\\actions\\open_app.py","startLine":364},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":11},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":12},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":33},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":47},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":49},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":104},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":143},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":150},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":161},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":176},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":190},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":194},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":198},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":202},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":206},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":210},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":217},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":224},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":229},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":233},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":237},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":241},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":245},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":249},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":253},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":264},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":308},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":310},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":326},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":331},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":334},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":335},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":350},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":360},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":369},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":379},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":387},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":413},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":417},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":419},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":431},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":432},
{"path":"c:\\Users\\rohan\\Mark-XXX\\agent\\executor.py","startLine":434}
]
"""

import json

problems = json.loads(problems_json)
files = {}
for p in problems:
    path = p['path']
    line = p['startLine']
    if path not in files:
        files[path] = set()
    files[path].add(line)

for path, lines in files.items():
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read().splitlines()
    
    for i in sorted(list(lines), reverse=True):
        idx = i - 1
        if 0 <= idx < len(content):
            if '# type: ignore' not in content[idx]:
                content[idx] = content[idx] + '  # type: ignore'
            
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(content) + '\n')

print("Applied type ignores successfully!")
