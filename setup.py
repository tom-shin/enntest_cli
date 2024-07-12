try:
    from setuptools import setup, find_packages
except ModuleNotFoundError:
    print("setuptools not found. Installing...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "setuptools"])
    from setuptools import setup, find_packages

import os
import shutil

destination_dir = 'package'

if not os.path.exists(destination_dir):
    os.makedirs(destination_dir)
else:
    shutil.rmtree(destination_dir)
    os.makedirs(destination_dir)

setup(
    name='enntest',  # wheel 파일 package 이름 설정
    version='0.0.7',
    packages=find_packages(),    
    install_requires=[  # wheel 파일 설치하면서 함께 설치되어야 하는 package 정리           
        'paramiko',
        'tqdm',
        'easygui',
        'PyQt5',
        # 'PyQt5==5.15.7',
        # 'pyqt5-tools',   #python3.12 호환성 이슈
    ],
    include_package_data=True,

    # S.LSI에서 전달해주는 enntest를 위한 라이브로리가 저장된 위치
    # 우리 소스 코드는 enntest 아래 모든 코드가 존재하기에 최상위 root는
    # enntest 임. 따라서 package_data를 옆과 같은 형태로 표시
    package_data={
        'enntest': [
            'nnc-model-tester/bin/*',  # enntest 실행 binary             
            'visualization/*'  # Include all files in the visualization folder
        ],
    },
    description='Exynos Test Tool',
    author='ThunderSoft Korea',
    python_requires='>=3.9',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
        'License :: OSI Approved :: MIT License',
        # 여기에 필요한 추가 classifiers를 추가할 수 있습니다.
    ],
)
