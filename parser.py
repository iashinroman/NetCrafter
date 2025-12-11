import yaml
from netmiko import ConnectHandler


def mikrotik_routeros_version_parser(show_version_output):
    version_position = (show_version_output.find('version:'))
    return show_version_output[version_position:version_position+30].rstrip()


def device_detector(show_version_output):
    '''
    Определяет устройство по выводу команды просмотра версии.

    Args:
        show_version_output: Вывод команды просмотра версии.

    Returns: Название устройсва или unknown output,
             если устройство не определено.
    '''

    # Словарь с ключивыми отличиями разных выводов разных вендоров.
    devices = {
        'Arista': 'arista_eos',
        'MikroTik': 'mikrotik_routeros',
        'Cisco': 'cisco_ios',
        'SR Linux': 'nokia_srl'
    }
    output = 'unknown_output'  # Значение поумолчанию.
    # Ищем в тексте харрактерные особенности, соответствующие устройству.
    for k, v in devices.items():
        if k in show_version_output:
            return v
    return output


def connection_info_parser(
        show_version_command: str,
        hostname: str,
        username: str,
        passowrd: str
):
    '''
    Устанавливет соединение с коммутатор для получения 
    вывода команды просмотра информации об устройстве.

    Args:
        show_version_command: Команда просмотра версии.
        hostname: Имя коммутатора.
        username: Имя пользователя.
        password: Пароль от коммутатора.

    Returns: Вывод команды просмотра версии.
    '''
    with open("string_router.yaml", "r") as file:
        # Считываем файл с описанием.
        # Команда просмотра версии - список коммутаторов,
        # которые соответствуют этой команде.
        data = yaml.safe_load(file)

    device_group = data[show_version_command]  # Список возможных коммутаторов.
    # Можно взять первый коммутатор, т.к команда просмотра версии одинаковая.
    one_connection_device_type = device_group[0]

    router = {
        'device_type': one_connection_device_type,  # Подбираем
        'host': hostname,  # Известно
        'username': username,  # Известно
        'password': passowrd,  # Известно
        'port': 22,  # По дефолту порт 22.
    }

    net_connect = ConnectHandler(**router)  # Уствновка соединения.

    # Отправка команды просмотра версии.
    output = net_connect.send_command(show_version_command)

    net_connect.disconnect()  # Разрыв соединения.

    return output


# Тест
show_version_output = connection_info_parser('system/resource/print',
                                             'clab-switch_3_clab-mtr1',
                                             'admin',
                                             'admin'
                                             )

device_version = device_detector(show_version_output)
print(device_version)
print(mikrotik_routeros_version_parser(show_version_output))
