############################################################################################################
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources")

import sys
import os
import time
import paramiko
import re
from tqdm import tqdm
import socket
import stat
import multiprocessing
from colorama import Fore, Back, Style, init
import pkg_resources

from enntest.visualization.graph_main import graph_view


############################################################################################################


def auto_str_args(func):
    def wrapper(self, *args, **kwargs):
        new_args = [str(arg) if not isinstance(arg, str) and arg is not None else arg for arg in args]
        new_kwargs = {k: str(v) if not isinstance(v, str) and v is not None else v for k, v in kwargs.items()}
        return func(self, *new_args, **new_kwargs)

    return wrapper


class exynos:
    server_ip = "1.220.53.154"
    port = 63522

    def __init__(self):

        self.ssh = None
        self.remote_directory = "/tmp/enntest"
        self.enntest_cmd_dir = "/data/vendor/enn"
        self.enntest_execution_bin = "/vendor/bin"

    def _enntest_library_binary_push(self, device, nnc_model, input_binary, golden_binary):

        enntest_file = [nnc_model, input_binary, golden_binary]
        for file_ in enntest_file:
            self.upload(device=device, src_path=file_, dst_path=self.enntest_cmd_dir, root_remount=False)

        """ path environment set up """
        enntest_lib_bin = pkg_resources.resource_filename('enntest',
                                                          os.path.join('nnc-model-tester', 'bin', 'EnnTest_v2_lib'))
        enntest_service_bin = pkg_resources.resource_filename('enntest',
                                                              os.path.join('nnc-model-tester', 'bin',
                                                                           'EnnTest_v2_service'))

        enntest_binary = [enntest_lib_bin, enntest_service_bin]
        for file_ in enntest_binary:
            self.upload(device=device, src_path=file_, dst_path=self.enntest_execution_bin, root_remount=False)

    @staticmethod
    def help():

        # Initialize colorama
        init()
        method_prototypes = {
            "quit()": {
                "description": "enntest termination",
                "return": "None",
                "input param.": "None"
            },

            "devices()": {
                "description": "show current available device list",
                "return": "None",
                "input param.": "None"
            },

            "connect(username, password)": {
                "description": "connect to remote server",
                "return": "True: connect success\n            False: connect fail",
                "input param.": "username<str>: authorized user name\n                  password<str>: user password"
            },

            "analyze(device, exe_cmd, nnc_model, input_binary, golden_binary, option, result_dir)": {
                "description": "start enntest with nnc model, input_binary, golden_binary, option",
                "return": "success: full file path for graph visualization\n            False: fail to model analyze",
                "input param.": "device<str>: device for enntest\n                  exe_cmd<str>: cmd for enntest\n             "
                                "       >> EnnTest_v2_lib\n                    >> EnnTest_v2_service\n                "
                                "  nnc_model<str>: full path of nnc model\n                  input_binary<str>: full path of "
                                "input binary\n                  golden_binary<str>: full path of golden_binary\n          "
                                "        optioin<str>: enntest option\n                    >> --profile summary\n          "
                                "          >> --iter #\n                  result_dir<str>: full path where json file "
                                "generated by the enntest reusult is saved"
            },

            "upload(device, src_path, des_path)": {
                "description": "upload file or dir to selected device",
                "return": "True: success\n            False: upload fail",
                "input param.": "device<str>: test device\n                  src_path<str>: source file or directory path\n                  dst_path<str>: destination path for upload "
            },

            "show(profile_file, direction)": {
                "description": "connect to remote server",
                "return": "True: success\n            False: graph view fail",
                "input param.": "profile_file<str>: the full path where the json file generated by the enntest results is "
                                "saved\n                  direction<boolean>: graph direction\n                    >> True: "
                                "horizon view\n                    >> False: vertical view"
            }
        }
        print("\n[Usage: instance.method(...)]")
        for keys, value_s in method_prototypes.items():
            print(Fore.GREEN + rf"{keys}")
            for key, value in value_s.items():
                print(Fore.CYAN + rf"  - {key}: {Fore.WHITE}{value}")
            print(Style.RESET_ALL + "\n")

    def quit(self):
        if self.ssh:
            print("Closing previous connection.")
            self.ssh.close()
            self.ssh = None
            print("Quit Successfully")
        else:
            print("Already disconnected or no connection")

    @staticmethod
    def _normalize_path(user_input_path):
        # 사용자는 "C:\\Work\\tom" 와 같이 \\을 입력하고 또는 r"C:\Work\tom" 과 같이 r을 사용해서 원시 문자열로 넣어 주는 경우
        # 대다수 임. 일반 유저는 \\ 방법을 넣을 것이고 개발자는 r를 사용할 수 있음.
        # 그런데 생각없는 사람은 그냥 PC에서 경로 복사해서 넣으면 윈도우 환경에 따라 "C:\Work\tom" 처럼 r 도 아니고 \도 한개만
        # 입력하는 경우 있음. 이런경우 경로가 n으로 또는 t로 시작하는 경우 \n, \t로 해석이 되는데 이게 엔터 또는 tap으로 해석이 됨.
        # 그래서 아래처럼 replace를 여러번 해 줌

        normalized_path = user_input_path.replace('\n', '/n').replace('\t', '/t').replace('\\', '/')
        return normalized_path

    def __execute_command(self, command):

        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            stdout.channel.recv_exit_status()  # Wait for the command to complete
            output = stdout.read().decode()
            error = stderr.read().decode()
            return output, error
        except Exception as e:
            print(f"An error occurred: {e}")
            return None, str(e)

    def _ensure_remote_dir_exists(self, remote_dir):

        """Ensure the remote directory exists. If it exists, delete it and recreate it."""
        sftp = self.ssh.open_sftp()

        def remove_dir(sftp, path):
            try:
                files = sftp.listdir(path)
                for file in files:
                    file_path = f"{path}/{file}"
                    try:
                        file_attr = sftp.stat(file_path)
                        if stat.S_ISDIR(file_attr.st_mode):
                            remove_dir(sftp, file_path)
                        else:
                            sftp.remove(file_path)
                    except IOError as e:
                        print(f"An error occurred while removing file {file_path}: {e}")
                sftp.rmdir(path)
            except Exception as e:
                print(f"An error occurred while removing directory {path}: {e}")

        try:
            sftp.stat(remote_dir)
            # print(f"Directory {remote_dir} already exists. Removing it.")
            remove_dir(sftp, remote_dir)
        except FileNotFoundError:
            print("")
        except Exception as e:
            print(f"An error occurred: {e}")

        try:
            sftp.mkdir(remote_dir)
            # print(f"Directory {remote_dir} created.")
        except Exception as e:
            print(f"Failed to create directory {remote_dir}: {e}")
        finally:
            sftp.close()

    def _ssh_connect(self, username, password, timeout):

        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(hostname=self.server_ip, port=self.port, username=username, password=password,
                             timeout=timeout)
            print(f"Successfully connected to the server.")
            return True

        except paramiko.AuthenticationException:
            print("Authentication failed")
        except paramiko.SSHException as sshException:
            print(f"SSH error: {sshException}")
        except socket.timeout:
            print("Connection timed out")
        except Exception as e:
            print(f"Other error: {e}")

        if self.ssh:
            # print("Closing previous connection.")
            self.ssh.close()
            self.ssh = None

        return False

    def __upload_directory(self, sftp, local_dir, remote_dir):

        for root, dirs, files in os.walk(local_dir):
            rel_path = os.path.relpath(root, local_dir)
            remote_path = os.path.join(remote_dir, rel_path).replace("\\", "/")
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass  # Directory might already exist
            for file in files:
                local_file = os.path.join(root, file)
                remote_file = os.path.join(remote_path, file).replace("\\", "/")
                # sftp.put(local_file, remote_file)
                self.__upload_file(sftp, local_file, remote_file)

    @staticmethod
    def __upload_file(sftp, local_file, remote_file):

        file_size = os.path.getsize(local_file)
        with tqdm(total=file_size, unit='B', unit_scale=True, desc='Uploading') as pbar:
            def callback(transferred, total):
                pbar.update(transferred - pbar.n)

            sftp.put(local_file, remote_file, callback=callback)

    def _upload2server(self, src_path, remote_directory="/tmp/enntest"):

        if not self.ssh:
            print("No SSH connection. Upload aborted.")
            return False

        dest_path = ""
        try:
            sftp = self.ssh.open_sftp()

            # Ensure the remote directory exists
            self._ensure_remote_dir_exists(remote_directory)

            if os.path.isdir(src_path):
                # src_path가 폴더인 경우
                folder_name = os.path.basename(src_path)
                dest_path = os.path.join(remote_directory, folder_name).replace("\\", "/")
                self._ensure_remote_dir_exists(dest_path)
                self.__upload_directory(sftp, src_path, dest_path)
            elif os.path.isfile(src_path):
                # src_path가 파일인 경우
                dest_path = os.path.join(remote_directory, os.path.basename(src_path)).replace("\\", "/")
                self.__upload_file(sftp, src_path, dest_path)

            sftp.close()
            return True, dest_path
        except Exception as e:
            print(f"Fail to upload: {e}")
            return False, None

    def _download_from_server(self, dst_path, remote_directory="/tmp/enntest"):

        if not self.ssh:
            print("No SSH connection. Download aborted.")
            return None

        try:
            sftp = self.ssh.open_sftp()

            def download_dir(sftp, remote_dir, local_dir):
                os.makedirs(local_dir, exist_ok=True)
                for item in sftp.listdir_attr(remote_dir):
                    remote_item_path = os.path.join(remote_dir, item.filename).replace("\\", "/")
                    local_item_path = os.path.join(local_dir, item.filename)
                    if stat.S_ISDIR(item.st_mode):
                        download_dir(sftp, remote_item_path, local_item_path)
                    else:
                        file_size = item.st_size
                        with tqdm(total=file_size, unit='B', unit_scale=True,
                                  desc=f'Downloading {item.filename}') as pbar:
                            def callback(transferred, total):
                                pbar.update(transferred - pbar.n)

                            sftp.get(remote_item_path, local_item_path, callback=callback)

            if not os.path.exists(dst_path):
                os.makedirs(dst_path, exist_ok=True)

            download_dir(sftp, remote_directory, dst_path)

            sftp.close()
            print(f"Successfully downloaded {remote_directory} to {dst_path}")
            return None
        except Exception as e:
            print(f"Failed to download: {e}")
            return None

    def _device_root_remount(self, device=''):

        if len(device) == 0:
            print("No Device Selected")
            return

        cmds = [
            rf"adb -s {device} root",
            rf"adb -s {device} remount"
        ]
        for cmd in cmds:
            output, error = self.__execute_command(command=cmd)
            print(cmd)
            print(output)

    def _adb_pull_overwrite(self, local_path, remote_path, device_id, root_remount=False):

        if root_remount:
            self._device_root_remount(device=device_id)

        cmds = [
            rf'adb -s {device_id} pull {remote_path} {local_path}'
        ]

        for cmd in cmds:
            output, error = self.__execute_command(command=cmd)
            print(cmd)
            print(output)

    def _adb_push_overwrite(self, local_path, remote_path, device_id, root_remount=False):

        if root_remount:
            self._device_root_remount(device=device_id)

        cmds = [
            rf'adb -s {device_id} push {local_path} {remote_path}',
            rf'adb -s {device_id} shell "chmod -R 777 {remote_path}"'
        ]

        for cmd in cmds:
            output, error = self.__execute_command(command=cmd)
            print(cmd)
            print(output)

    def devices(self):

        if not self.ssh:
            print("No SSH connection.")
            return

        cmd = "adb devices"
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        output = stdout.read().decode()
        error = stderr.read().decode()

        if error:
            print("Devices Error:", error)

        print(output)

    def upload(self, device, src_path, dst_path, root_remount=False):

        if not self.ssh:
            print("No SSH connection.")
            return

        result, path = self._upload2server(src_path=src_path, remote_directory=self.remote_directory)
        if result:
            self._adb_push_overwrite(local_path=path, remote_path=dst_path, device_id=device, root_remount=root_remount)
        else:
            print("Upload Fail")

    def download(self, device, src_path, dst_path, root_remount=False):

        if not self.ssh:
            print("No SSH connection.")
            return

        src_path = self._normalize_path(user_input_path=src_path)
        dst_path = self._normalize_path(user_input_path=dst_path)

        self._adb_pull_overwrite(local_path="/tmp/enntest", remote_path=src_path, device_id=device,
                                 root_remount=root_remount)
        self._download_from_server(dst_path=dst_path, remote_directory=self.remote_directory)

    def connect(self, username, password, timeout=30):

        if self.ssh:
            # print("Closing previous connection.")
            self.ssh.close()
            self.ssh = None

        ret = self._ssh_connect(username=username, password=password, timeout=timeout)

        if ret:
            # Ensure the remote directory exists
            self._ensure_remote_dir_exists(self.remote_directory)

    @auto_str_args
    def analyze(self, device, exe_cmd, nnc_model, input_binary, golden_binary, result_dir='',
                threshold=0.0001, option=''):

        if not self.ssh:
            print("No SSH connection.")
            return

        nnc_model = self._normalize_path(user_input_path=nnc_model)
        input_binary = self._normalize_path(user_input_path=input_binary)
        golden_binary = self._normalize_path(user_input_path=golden_binary)
        result_dir = self._normalize_path(user_input_path=result_dir)

        if not self.ssh:
            print("No SSH connection. Model upload aborted.")
            return False

        if device == '':
            print("No selected device")
            return False
        elif nnc_model == '':
            print("No selected nnc model")
            return False
        elif input_binary == '':
            print("No selected input_binary")
            return False
        elif golden_binary == '':
            print("No selected golden_binary")
            return False
        elif exe_cmd == '':
            print("No EnnTest Command")
            return False

        self._device_root_remount(device=device)

        """ 선택한 device 정상 상태인지 확인 """
        output, error = self.__execute_command(command=rf"adb -s {device} get-state")
        if "device" not in output:
            print(f"device is not available state: {output}")
            return False

        self._enntest_library_binary_push(device=device, nnc_model=nnc_model, input_binary=input_binary,
                                          golden_binary=golden_binary)

        nnc_model = os.path.basename(nnc_model)
        input_binary = os.path.basename(input_binary)
        golden_binary = os.path.basename(golden_binary)

        test_cmd = f'adb -s {device} shell "cd {self.enntest_cmd_dir}; {exe_cmd} --model {nnc_model} --input {input_binary} --golden {golden_binary} {option}"'
        print(f"Executing: {test_cmd}\n")
        enntest_result, enntest_error = self.__execute_command(command=test_cmd)
        if enntest_result:
            print(f"Test Result:\n{enntest_result}")
        if enntest_error:
            print(f"Error:\n{enntest_error}")
            return False

        formatted_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        rename_output = f"{formatted_time}_enntest_result.txt"
        if result_dir == '':
            local_output_path = os.path.join(os.getcwd(), rename_output)
        else:
            local_output_path = os.path.join(result_dir, rename_output)

        # save enntest result
        if enntest_result:
            # ANSI escape codes 제거
            ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
            cleaned_result = ansi_escape.sub('', enntest_result)
            with open(local_output_path, "w") as result_file:
                result_file.write(cleaned_result)

        # print("++++++++++++++++++++++++++++++", local_output_path)
        return local_output_path  # full local path to save generated output.json file

    @auto_str_args
    def show(self, result_file, direction=False):

        if not self.ssh:
            print("No SSH connection.")
            return

        enn_result_file = str(result_file)
        enn_result_file = self._normalize_path(user_input_path=enn_result_file)

        if not os.path.isfile(enn_result_file):
            print(f"{enn_result_file}: File Not Found")
            return False

        self.process = multiprocessing.Process(
            target=graph_view,
            args=(enn_result_file, direction)
        )

        self.process.start()

        return True


# 함수 실행 예시
if __name__ == "__main__":
    server_ip = "1.220.53.154"  # 원격 서버 IP 주소
    port = 63522  # SSH 포트
    username = "sam"  # SSH 사용자 이름
    password = "Thunder$@88"  # SSH 비밀번호
    device = "000011b5ceac6013"

    ssh_test = exynos()
    ssh_test.connect(username, password)

    ssh_test.devices()


    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    cmd =  "EnnTest_v2_lib"   #"EnnTest_v2_service"

    
    model = rf"{BASE_DIR}\nnc-model-tester\sample_model\NPU_EdgeTPU\Mobilenet_Edgetpu_O2_Multicore.nnc\Mobilenet_Edgetpu_O2_Multicore.nnc"
    input = rf"{BASE_DIR}\nnc-model-tester\sample_model\NPU_EdgeTPU\Mobilenet_Edgetpu_O2_Multicore.nnc\Mobilenet_Edgetpu_O2_Multicore_input_data.bin"
    gold = rf"{BASE_DIR}\nnc-model-tester\sample_model\NPU_EdgeTPU\Mobilenet_Edgetpu_O2_Multicore.nnc\Mobilenet_Edgetpu_O2_Multicore_golden_data.bin"
    option = "--profile summary --iter 3"
    result_file = ssh_test.analyze(device=device, exe_cmd=cmd, nnc_model=model, input_binary=input, golden_binary=gold,
                                   option=option)
    
    ssh_test.show(result_file)
