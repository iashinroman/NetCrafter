from netmiko import ConnectHandler
from netmiko.ssh_autodetect import SSHDetect
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
from paramiko.ssh_exception import SSHException


def detect_device_type(host, username, use_keys, password, key_file,
                       allow_agent, port=22):
    """
    Автоматически определяет тип сетевого устройства (device_type) для Netmiko
    на основе SSH-баннера и характеристик подключения.

    Args:
        host (str): IP-адрес или hostname коммутатора/роутера.
        username (str): Имя пользователя для SSH-подключения.
        use_keys (bool): Использовать SSH-ключи для аутентификации (True) или пароль (False).
        password (str): Пароль пользователя. Игнорируется при use_keys=True.
        key_file (str): Полный путь к приватному SSH-ключу (например, '~/.ssh/id_rsa').
                       Обязателен при use_keys=True.
        allow_agent (bool): Разрешить использование ssh-agent для поиска ключей.
        port (int, optional): SSH-порт. По умолчанию 22.

    Returns:
        str or None: Определённый device_type (например, 'cisco_ios', 'juniper_junos')
                     или None при ошибке аутентификации/подключения.

        При успешном определении также выводит в консоль:
        - best_match: наиболее вероятный device_type
        - potential_matches: словарь с рейтингами всех возможных совпадений

    Raises:
        NetmikoAuthenticationException: Неверные учетные данные или ключ.
        NetmikoTimeoutException: Таймаут подключения к хосту.
        SSHException: Ошибки SSH-протокола.
        RuntimeError: Другие непредвиденные ошибки.

    Example:
        >>> dtype = detect_device_type(
        ...     host='192.168.1.1',
        ...     username='admin',
        ...     use_keys=True,
        ...     password='',
        ...     key_file='~/.ssh/id_rsa',
        ...     allow_agent=True
        ... )
        best_match: cisco_ios
        potential_matches: {'cisco_ios': 85, 'cisco_nxos': 12, ...}
        >>> print(dtype)
        cisco_ios

    Notes:
        - При ошибках выводит диагностическое сообщение в консоль.
    """

    device = {
        "device_type": "autodetect",
        "host": host,
        "username": username,
        "port": port,
        "use_keys": use_keys,          # использовать ключ
        "key_file": key_file,      # путь к приватному ключу
        "allow_agent": allow_agent,       # можно использовать ssh-agent
        "password": password,
    }

    try:
        guesser = SSHDetect(**device)
        best_match = guesser.autodetect()
        # print("best_match:", best_match)
        # print("potential_matches:", guesser.potential_matches)
        return best_match
    except NetmikoAuthenticationException as e:
        print(f"Ошибка аутентификации: {e}")
    except NetmikoTimeoutException as e:
        print(f"Таймаут подключения: {e}")
    except SSHException as e:
        print(f"SSH ошибка: {e}")
    except Exception as e:
        print(f"Другая ошибка: {repr(e)}")
    return None


def connect_with_detected_type(device_type, host, username, use_keys, password, key_file,
                               allow_agent, port=22):
    '''
    Можно использовать, если понадобится,
        пока не используется.
    '''

    params = {
        "device_type": device_type,
        "host": host,
        "username": username,
        "port": port,
        "use_keys": use_keys,
        "key_file": key_file,
        "allow_agent": allow_agent,
        "password": password,
    }
    conn = ConnectHandler(**params)
    return conn


def main():
    # Ввод данных.
    print("Введите имя хоста:")
    host = input()
    print("Введите имя пользователя:")
    username = input()
    print("Введите пароль, если есть:")
    password = input()
    if password == "":
        password = None
    print("Использовать ssh агент? y/n")
    ans = input().lower
    allow_agent = False
    use_keys = False
    key_file = None
    if ans == 'y':
        allow_agent = True
    else:
        print("Использовать ssh ключи? y/n")
        ans = input().lower()
        if ans == 'y':
            use_keys = True
            print('Введите путь к файлу с ключами.')
            key_file = input()
    best_match = detect_device_type(host, username, use_keys, password,
                                    key_file, allow_agent, port=22)
    print(best_match)


if __name__ == "__main__":
    main()
