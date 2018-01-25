import subprocess


def execute_list(cmd, silent=False):
    try:
        return subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode("utf-8")
    except Exception as e:
        if not silent:
            raise e

def execute(cmd, silent=False):
    return execute_list(cmd.split(" "), silent)
            

