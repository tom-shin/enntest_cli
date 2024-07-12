import sys


def get_os_type():
    if sys.platform.startswith('win'):
        return "Windows"
    elif sys.platform.startswith('linux'):
        return "Linux"
    elif sys.platform.startswith('darwin'):
        return "MacOS"
    else:
        return "Unknown"


import os
import subprocess

if get_os_type() == "Windows":
    subprocess.run(["python", "-m", "pip", "install", "--upgrade", "setuptools"])
    subprocess.run(["python", "-m", "pip", "install", "--upgrade", "wheel"])
else:
    subprocess.run(["python3", "-m", "pip3", "install", "--upgrade", "setuptools"])
    subprocess.run(["python3", "-m", "pip3", "install", "--upgrade", "wheel"])

import shutil
import re
import glob

# package data 생성
subprocess.run("python setup.py bdist_wheel")

destination_dir = 'package'
source_dir = os.getcwd()  # 폴더들이 있는 소스 디렉토리 경로

if not os.path.exists(destination_dir):
    os.makedirs(destination_dir)
else:
    shutil.rmtree(destination_dir)
    os.makedirs(destination_dir)

# 패턴 정의
patterns = ["*egg-info", "build", "dist"]
folders_to_move = []

for pattern in patterns:
    folders_to_move.extend(glob.glob(os.path.join(source_dir, pattern)))

# 각 폴더를 목적지 디렉토리로 이동
for folder in folders_to_move:
    try:
        shutil.move(folder, destination_dir)
        print(f"Moved: {folder} to {destination_dir}")
    except Exception as e:
        print(f"Error moving {folder}: {e}")

# dist에 wheel install할 수 있는 bat 파일을 만들어 줌
# package/dist 디렉토리에서 .whl 파일 찾기
whl_files = glob.glob(os.path.join(destination_dir, "dist", "*.whl"))
package_name = ''

if whl_files:
    print("Found .whl files:")
    for whl_file in whl_files:
        package_name = os.path.basename(whl_file)
        print(package_name)
        break
else:
    print("No .whl files found in package/dist.")

win_batch_contents = [
    "@echo off",
    "REM Step 1: Upgrade pip to the latest version for all users",
    "python -m pip install --upgrade pip",
    "REM Step 2: Install setuptools if not already installed",
    'python -c "import setuptools" || python -m pip install setuptools',
    "REM Step 3: Install or force-reinstall for all users",
    rf"python -m pip install --upgrade --force-reinstall {package_name}",
    "REM Pause to see the output",
    "pause"
]

# 파일 생성 및 쓰기
file_path = rf"{destination_dir}/dist/install_whl_package_window.bat"
with open(file_path, "w", encoding="utf-8") as install_file:
    install_file.write("\n".join(win_batch_contents))

print(f"Created {file_path}")

linux_batch_contents = [
    "#!/bin/bash",
    # "cp -r /mnt/c/Work/tom/Project/AI_Application_Servie_Team/ExynosTestTool /home/tom/",  # copy cmd
    # "sudo apt update && sudo apt install --reinstall libqt5core5a libqt5gui5 libqt5widgets5",  # Qt plug in error xcb...
    "# Update the package list",
    "sudo apt update",
    "# Install Python3 and pip3",
    "sudo apt install -y python3-pip",
    "# Upgrade pip3",
    "pip3 install --upgrade pip",
    "# Install setuptools and wheel packages",
    "pip3 install --upgrade setuptools",
    "pip3 install wheel",
    f"pip3 install --upgrade --force-reinstall {package_name}",
    "echo Installation complete!"
]

# 파일 생성 및 쓰기
file_path = f"{destination_dir}/dist/install_whl_package_linux.sh"
with open(file_path, "w", encoding="utf-8", newline='\n') as install_file:
    install_file.write("\n".join(linux_batch_contents))

# 파일 생성 및 쓰기
file_path = f"{destination_dir}/dist/install_whl_package_linux.sh"
with open(file_path, "w", encoding="utf-8", newline='\n') as install_file:
    install_file.write("\n".join(linux_batch_contents))  # <-==== 리눅스용일 때 \n 있는거 주의 할 것 아니면 dos2unix로 .sh을 변경해야 함

print(f"Created {file_path}")
