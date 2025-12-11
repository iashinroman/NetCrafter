# output = '''
#             uptime: 32m58s
#             version: 7.2 (stable)
#                build-time: Mar/31/2022 09:11:50
#          factory-software: 6.49.3
#               free-memory: 145.8MiB
#              total-memory: 192.0MiB
#                       cpu: QEMU
#                 cpu-count: 1
#             cpu-frequency: 3792MHz
#                  cpu-load: 0%
#            free-hdd-space: 72.0MiB
#           total-hdd-space: 89.2MiB
#   write-sect-since-reboot: 1320
#          write-sect-total: 1320
#         architecture-name: x86_64
#                board-name: CHR
#                  platform: MikroTik
#             '''


# def mikrotik_routeros_version_parser(show_version_output):
#     version_position = (show_version_output.find('version:'))
#     print(show_version_output[version_position:version_position+30].rstrip())

# mikrotik_routeros_version_parser(output)


from netmiko import ConnectHandler
from netmiko.ssh_autodetect import SSHDetect
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
from paramiko.ssh_exception import SSHException

def detect_device_type(host, username, key_file, port=22):
    device = {
        "device_type": "autodetect",
        "host": host,
        "username": username,
        "port": port,
        "use_keys": True,          # использовать ключ
        "key_file": key_file,      # путь к приватному ключу, например "~/.ssh/id_rsa"
        "allow_agent": True,       # можно использовать ssh-agent, если есть
        "password": "",            # пароля нет
    }

d
