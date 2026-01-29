import paramiko
import sys

def test_ssh(ip, username, password):
    print(f"Testing connection to {username}@{ip}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, username=username, password=password, timeout=10)
        stdin, stdout, stderr = client.exec_command("uname -a")
        print("Success!")
        print(stdout.read().decode())
        client.close()
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

ip = "129.154.41.199"
pwd = "Rr22081993!"

if not test_ssh(ip, "ubuntu", pwd):
    test_ssh(ip, "opc", pwd)
