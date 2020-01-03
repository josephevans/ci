"""Dependency installer for Windwos"""
import argparse
import errno
import logging
import os
import psutil
import shutil
import subprocess
import urllib
import stat
import tempfile
import zipfile
from time import sleep
from urllib.error import HTTPError
import logging
from subprocess import check_output
import re

log = logging.getLogger(__name__)


DEPS = {
        'openblas': 'https://windows-post-install.s3-us-west-2.amazonaws.com/OpenBLAS-windows-v0_2_19.zip',
        'opencv': 'https://windows-post-install.s3-us-west-2.amazonaws.com/OpenCV-windows-v3_4_1-vc14.zip',
        'cudnn': 'https://windows-post-install.s3-us-west-2.amazonaws.com/cudnn-9.2-windows10-x64-v7.4.2.24.zip',
        'nvdriver': 'https://windows-post-install.s3-us-west-2.amazonaws.com/nvidia_display_drivers_398.75_server2016.zip',
        'cmake': 'https://windows-post-install.s3-us-west-2.amazonaws.com/cmake-3.15.5-win64-x64.msi'
}


def retry(target_exception, tries=4, delay_s=1, backoff=2):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param target_exception: the exception to check. may be a tuple of
        exceptions to check
    :type target_exception: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay_s: initial delay between retries in seconds
    :type delay_s: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    """
    import time
    from functools import wraps

    def decorated_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay_s
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except target_exception as e:
                    logging.warning("Exception: %s, Retrying in %d seconds...", str(e), mdelay)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return decorated_retry


@retry((ValueError, OSError, HTTPError), tries=5, delay_s=2, backoff=5)
def download(url, dest=None, progress=True) -> str:
    from urllib.request import urlopen
    from urllib.parse import (urlparse, urlunparse)
    import progressbar
    import http.client

    class ProgressCB():
        def __init__(self):
            self.pbar = None

        def __call__(self, block_num, block_size, total_size):
            if not self.pbar and total_size > 0:
                self.pbar = progressbar.bar.ProgressBar(max_value=total_size)
            downloaded = block_num * block_size
            if self.pbar:
                if downloaded < total_size:
                    self.pbar.update(downloaded)
                else:
                    self.pbar.finish()
    if dest and os.path.isdir(dest):
        local_file = os.path.split(urlparse(url).path)[1]
        local_path = os.path.join(dest, local_file)
    else:
        local_path = dest
    with urlopen(url) as c:
        content_length = c.getheader('content-length')
        length = int(content_length) if content_length and isinstance(c, http.client.HTTPResponse) else None
        if length and local_path and os.path.exists(local_path) and os.stat(local_path).st_size == length:
            log.debug(f"download('{url}'): Already downloaded.")
            return local_path
    log.debug(f"download({url}, {local_path}): downloading {length} bytes")
    if local_path:
        with tempfile.NamedTemporaryFile(delete=False) as tmpfd:
            urllib.request.urlretrieve(url, filename=tmpfd.name, reporthook=ProgressCB() if progress else None)
            shutil.move(tmpfd.name, local_path)
    else:
        (local_path, _) = urllib.request.urlretrieve(url, reporthook=ProgressCB())
    log.debug(f"download({url}, {local_path}'): done.")
    return local_path


# Takes arguments and runs command on host.  Shell is disabled by default.
# TODO: Move timeout to args
def run_command(args, shell=False):
    try:
        logging.info("Issuing command: {}".format(args))
        res = subprocess.check_output(args, shell=shell, timeout=1800).decode("utf-8").replace("\r\n", "")
        logging.info("Output: {}".format(res))
    except subprocess.CalledProcessError as e:
        raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    return res


# Copies source directory recursively to destination.
def copy(src, dest):
    try:
        shutil.copytree(src, dest)
        logging.info("Moved {} to {}".format(src, dest))
    except OSError as e:
        # If the error was caused because the source wasn't a directory
        if e.errno == errno.ENOTDIR:
            shutil.copy(src, dest)
            logging.info("Moved {} to {}".format(src, dest))
        else:
            raise RuntimeError("copy return with error: {}".format(e))


# Workaround for windows readonly attribute error
def on_rm_error( func, path, exc_info):
    # path contains the path of the file that couldn't be removed
    # let's just assume that it's read-only and unlink it.
    os.chmod( path, stat.S_IWRITE )
    os.unlink( path )


def install_vs():
    # Visual Studio CE 2017
    # Path: C:\Program Files (x86)\Microsoft Visual Studio 14.0
    # Components: https://docs.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-community?view=vs-2017#visual-studio-core-editor-included-with-visual-studio-community-2017
    logging.info("Installing Visual Studio CE 2017...")
    vs_file_path = download('https://aka.ms/eac464')
    run_command("PowerShell Rename-Item -Path {} -NewName \"{}.exe\"".format(vs_file_path, vs_file_path.split('\\')[-1]), shell=True)
    vs_file_path = vs_file_path + '.exe'
    run_command(vs_file_path + \
        ' --add Microsoft.VisualStudio.Workload.ManagedDesktop' \
        ' --add Microsoft.VisualStudio.Workload.NetCoreTools' \
        ' --add Microsoft.VisualStudio.Workload.NetWeb' \
        ' --add Microsoft.VisualStudio.Workload.Node' \
        ' --add Microsoft.VisualStudio.Workload.Office' \
        ' --add Microsoft.VisualStudio.Component.TypeScript.2.0' \
        ' --add Microsoft.VisualStudio.Component.TestTools.WebLoadTest' \
        ' --add Component.GitHub.VisualStudio' \
        ' --add Microsoft.VisualStudio.ComponentGroup.NativeDesktop.Core' \
        ' --add Microsoft.VisualStudio.Component.Static.Analysis.Tools' \
        ' --add Microsoft.VisualStudio.Component.VC.CMake.Project' \
        ' --add Microsoft.VisualStudio.Component.VC.140' \
        ' --add Microsoft.VisualStudio.Component.Windows10SDK.15063.Desktop' \
        ' --add Microsoft.VisualStudio.Component.Windows10SDK.15063.UWP' \
        ' --add Microsoft.VisualStudio.Component.Windows10SDK.15063.UWP.Native' \
        ' --add Microsoft.VisualStudio.ComponentGroup.Windows10SDK.15063' \
        ' --wait' \
        ' --passive' \
        ' --norestart'
    )
    # Workaround for --wait sometimes ignoring the subprocesses doing component installs
    timer = 0
    while {'vs_installer.exe', 'vs_installershell.exe', 'vs_setup_bootstrapper.exe'} & set(map(lambda process: process.name(), psutil.process_iter())):
        if timer % 60 == 0:
            logging.info("Waiting for Visual Studio to install for the last {} seconds".format(str(timer)))
        timer += 1



def install_cmake():
    logging.info("Installing CMAKE")
    cmake_file_path = download(DEPS['cmake'])
    run_command("msiexec /i {} /quiet /norestart ADD_CMAKE_TO_PATH=System".format(cmake_file_path))


def install_openblas():
    logging.info("Installing OpenBLAS")
    local_file = download(DEPS['openblas'])
    with zipfile.ZipFile(local_file, 'r') as zip:
        zip.extractall("C:\\Program Files")
    run_command("PowerShell Set-ItemProperty -path 'hklm:\\system\\currentcontrolset\\control\\session manager\\environment' -Name OpenBLAS_HOME -Value 'C:\\Program Files\\OpenBLAS-windows-v0_2_19'")


def install_mkl():
    logging.info("Installing MKL 2019.3.203...")
    file_path = download("http://registrationcenter-download.intel.com/akdlm/irc_nas/tec/15247/w_mkl_2019.3.203.exe")
    run_command("{} --silent --remove-extracted-files yes --a install -output=C:\mkl-install-log.txt -eula=accept".format(file_path))



def install_opencv():
    logging.info("Installing OpenCV")
    local_file = download(DEPS['opencv'])
    with zipfile.ZipFile(local_file, 'r') as zip:
        zip.extractall("C:\\Program Files")
    run_command("PowerShell Set-ItemProperty -path 'hklm:\\system\\currentcontrolset\\control\\session manager\\environment' -Name OpenCV_DIR -Value 'C:\\Program Files\\OpenCV-windows-v3_4_1-vc14'")


def install_cudnn():
    # cuDNN
    logging.info("Installing cuDNN")
    with tempfile.TemporaryDirectory() as tmpdir:
        local_file = download(DEPS['cudnn'])
        with zipfile.ZipFile(local_file, 'r') as zip:
            zip.extractall(tmpdir)
        copy(tmpdir+"\\cuda\\bin\\cudnn64_7.dll","C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v9.2\\bin")
        copy(tmpdir+"\\cuda\\include\\cudnn.h","C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v9.2\\include")
        copy(tmpdir+"\\cuda\\lib\\x64\\cudnn.lib","C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v9.2\\lib\\x64")


def install_nvdriver():
    logging.info("Installing Nvidia Display Drivers...")
    with tempfile.TemporaryDirectory() as tmpdir:
        local_file = download(DEPS['nvdriver'])
        with zipfile.ZipFile(local_file, 'r') as zip:
            zip.extractall(tmpdir)
        run_command(tmpdir + "\\setup.exe /n /s /noeula /nofinish")


def install_cuda():
    # CUDA 9.2 and patches
    logging.info("Installing CUDA 9.2 and Patches...")
    cuda_9_2_file_path = download('https://developer.nvidia.com/compute/cuda/9.2/Prod2/network_installers2/cuda_9.2.148_win10_network')
    run_command("PowerShell Rename-Item -Path {} -NewName \"{}.exe\"".format(cuda_9_2_file_path, cuda_9_2_file_path.split('\\')[-1]), shell=True)
    cuda_9_2_file_path = cuda_9_2_file_path + '.exe'
    run_command(cuda_9_2_file_path \
    + ' -s nvcc_9.2' \
    + ' cuobjdump_9.2' \
    + ' nvprune_9.2' \
    + ' cupti_9.2' \
    + ' gpu_library_advisor_9.2' \
    + ' memcheck_9.2' \
    + ' nvdisasm_9.2' \
    + ' nvprof_9.2' \
    + ' visual_profiler_9.2' \
    + ' visual_studio_integration_9.2' \
    + ' demo_suite_9.2' \
    + ' documentation_9.2' \
    + ' cublas_9.2' \
    + ' cublas_dev_9.2' \
    + ' cudart_9.2' \
    + ' cufft_9.2' \
    + ' cufft_dev_9.2' \
    + ' curand_9.2' \
    + ' curand_dev_9.2' \
    + ' cusolver_9.2' \
    + ' cusolver_dev_9.2' \
    + ' cusparse_9.2' \
    + ' cusparse_dev_9.2' \
    + ' nvgraph_9.2' \
    + ' nvgraph_dev_9.2' \
    + ' npp_9.2' \
    + ' npp_dev_9.2' \
    + ' nvrtc_9.2' \
    + ' nvrtc_dev_9.2' \
    + ' nvml_dev_9.2' \
    + ' occupancy_calculator_9.2'
    )
    # Download patches and assume less than 100 patches exist
    for patch_number in range(1, 100):
        if patch_number == 100:
            raise Exception('Probable patch loop: CUDA patch downloader is downloading at least 100 patches!')
        cuda_9_2_patch_file_path = download("https://developer.nvidia.com/compute/cuda/9.2/Prod2/patches/{0}/cuda_9.2.148.{0}_windows".format(patch_number))
        if cuda_9_2_patch_file_path == 404:
            break
        run_command("PowerShell Rename-Item -Path {} -NewName \"{}.exe\"".format(cuda_9_2_patch_file_path, cuda_9_2_patch_file_path.split('\\')[-1]), shell=True)
        cuda_9_2_patch_file_path = cuda_9_2_patch_file_path + '.exe'
        run_command("{} -s".format(cuda_9_2_patch_file_path))


def add_paths():
    # TODO: Add python paths (python -> C:\\Python37\\python.exe, python2 -> C:\\Python27\\python.exe)
    logging.info("Adding Windows Kits to PATH...")
    current_path = run_command("PowerShell (Get-Itemproperty -path 'hklm:\\system\\currentcontrolset\\control\\session manager\\environment' -Name Path).Path")
    logging.debug("current_path: {}".format(current_path))
    new_path = current_path + ";C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.16299.0\\x86;C:\\Program Files\\OpenBLAS-windows-v0_2_19\\bin"
    logging.debug("new_path: {}".format(new_path))
    run_command("PowerShell Set-ItemProperty -path 'hklm:\\system\\currentcontrolset\\control\\session manager\\environment' -Name Path -Value '" + new_path + "'")


def has_gpu():
    hwinfo = check_output(['powershell','gwmi', 'win32_pnpEntity'])
    m = re.search('3D Video', hwinfo.decode())
    if m:
        return True
    return False


def script_name() -> str:
    """:returns: script name with leading paths removed"""
    return os.path.split(sys.argv[0])[1]


def main():
    logging.getLogger().setLevel(os.environ.get('LOGLEVEL', logging.DEBUG))
    logging.basicConfig(format='{}: %(asctime)sZ %(levelname)s %(message)s'.format(script_name()))


    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--gpu',
                        help='GPU install',
                        default=False,
			action='store_true')
    args = parser.parse_args()
    #if args.gpu:
    if has_gpu():
        logging.info("GPU detected")
        install_nvdriver()
        install_cuda()
        install_cudnn()
    else:
        logging.info("GPU not detected")
    install_vs()
    install_cmake()
    install_openblas()
    install_mkl()
    install_opencv()
    add_paths()


if __name__ == "__main__":
    exit (main())