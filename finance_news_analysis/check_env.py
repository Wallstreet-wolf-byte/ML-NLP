# 验证所有依赖是否能正常导入
import sys

print(f"Python 版本: {sys.version}")

modules = [
    ("requests", "requests"),
    ("beautifulsoup4", "bs4"),
    ("lxml", "lxml"),
    ("jieba", "jieba"),
    ("flask", "flask"),
    ("pandas", "pandas"),
    ("schedule", "schedule"),
]

all_ok = True
for name, import_name in modules:
    try:
        mod = __import__(import_name)
        version = getattr(mod, "__version__", "OK")
        print(f"  [OK] {name}: {version}")
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        all_ok = False

print()
if all_ok:
    print("所有依赖验证通过！")
else:
    print("部分依赖验证失败，请检查。")