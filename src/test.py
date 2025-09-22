import os

pa="E:\\00Egraduationdesign\PcdAgent\pcd_agent"
target_markdown_path = os.path.join(pa, "a", "b")
print(target_markdown_path)
os.makedirs(target_markdown_path, exist_ok=True)
