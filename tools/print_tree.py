import os

def print_tree(start_path, prefix=""):
    files = []
    dirs = []
    for name in sorted(os.listdir(start_path)):
        full = os.path.join(start_path, name)
        if os.path.isdir(full):
            dirs.append(name)
        else:
            files.append(name)

    for d in dirs:
        print(prefix + "📁 " + d)
        print_tree(os.path.join(start_path, d), prefix + "    ")

    for f in files:
        print(prefix + "📄 " + f)

print_tree(".")
