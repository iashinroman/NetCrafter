from netmiko import ConnectHandler

# test connection to arista_eos
router = {
    'device_type': 'arista_eos',
    'host': 'clab-switch_3_clab-ceos',
    'username': 'admin',
    'password': 'admin',
    'port': 22,  # по дефолту порт 22
}

net_connect = ConnectHandler(**router)
net_connect.enable()

output = net_connect.send_command('show version')

print(output)

net_connect.exit_enable_mode()
