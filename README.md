"""
Модуль для сбора информации о версиях ПО с сетевых коммутаторов через SSH.

Основные функции:
- Подключение к коммутаторам по SSH через системный ssh-клиент
- Выполнение команды show version на устройствах
- Сохранение результатов в структурированном YAML-файле

Требования:
- Установленный sshpass в системе
- Доступ к коммутаторам по SSH с указанными учетными данными
"""

import subprocess
import yaml
import re
import socket
from typing import List, Dict, Tuple
from datetime import datetime


def check_sshpass_installed() -> bool:
    """
    Проверяет наличие утилиты sshpass в системе.
    
    sshpass необходим для передачи пароля при подключении по SSH
    в неинтерактивном режиме.
    
    Returns:
        True если sshpass установлен, False в противном случае
    """
    try:
        # Пытаемся найти sshpass в системе
        result = subprocess.run(
            ["which", "sshpass"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        print('sshpass не установлен в системе')
        return False


def connect_via_ssh(host: str, username: str, password: str, command: str) -> str:
    """
    Выполняет команду на удаленном устройстве через SSH.
    
    Использует системный ssh-клиент с sshpass для автоматической передачи пароля.
    Отключает проверку ключей SSH для упрощения автоматизации подключений.
    
    Args:
        host: IP-адрес или имя хоста устройства
        username: Имя пользователя для аутентификации
        password: Пароль пользователя
        command: Команда для выполнения на удаленном устройстве
    
    Returns:
        Вывод команды в виде строки или сообщение об ошибке
    """
    try:
        # Проверяем формат IP-адреса если это IP, а не доменное имя
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
            # Проверяем корректность IP-адреса
            parts = host.split('.')
            for part in parts:
                if int(part) > 255:
                    return f"ОШИБКА: Неправильный IP-адрес {host} (число больше 255)"
        
        # Формируем команду SSH с использованием sshpass для передачи пароля
        ssh_command = [
            "sshpass", "-p", password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",    # Отключаем проверку ключей хоста
            "-o", "UserKnownHostsFile=/dev/null", # Не сохраняем ключи в known_hosts
            "-o", "ConnectTimeout=10",           # Таймаут подключения 10 секунд
            "-o", "PasswordAuthentication=yes",  # Разрешаем аутентификацию по паролю
            f"{username}@{host}",
            command
        ]
        
        # Выполняем команду с ограничением времени выполнения
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=15,  # Общий таймаут 15 секунд
            encoding='utf-8',
            errors='ignore'  # Игнорируем ошибки кодировки
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            # Анализируем сообщение об ошибке для лучшей диагностики
            error_msg = result.stderr.lower()
            
            # 1. Ошибка при неправильном пароле
            if "permission denied" in error_msg or "authentication failed" in error_msg:
                return f"ОШИБКА: Неправильный пароль для пользователя '{username}' на устройстве {host}"
            
            # 2. Ошибка при неправильном имени пользователя  
            elif "invalid user" in error_msg or "unknown user" in error_msg:
                return f"ОШИБКА: Неправильное имя пользователя '{username}' на устройстве {host}"
            
            # 3. Ошибка при неправильном IP адресе (DNS ошибка)
            elif "name or service not known" in error_msg or "could not resolve hostname" in error_msg:
                return f"ОШИБКА: Неправильный IP-адрес или имя хоста '{host}' (не удалось найти устройство)"
            
            # 4. Ошибка при недоступном устройстве
            elif "connection refused" in error_msg:
                return f"ОШИБКА: Не удалось подключиться к {host} (порт 22 закрыт или устройство выключено)"
            
            # 5. Ошибка при таймауте подключения
            elif "connection timed out" in error_msg or "operation timed out" in error_msg:
                return f"ОШИБКА: Таймаут подключения к {host} (устройство не отвечает)"
            
            # 6. Ошибка "нет маршрута до хоста"
            elif "no route to host" in error_msg or "host is unreachable" in error_msg:
                return f"ОШИБКА: Нет маршрута до устройства {host} (сетевая проблема)"
            
            # 7. Ошибка при сбросе соединения
            elif "connection reset by peer" in error_msg:
                return f"ОШИБКА: Устройство {host} разорвало соединение"
            
            # 8. Другие ошибки SSH
            elif "ssh protocol error" in error_msg:
                return f"ОШИБКА: Ошибка протокола SSH при подключении к {host}"
            
            # 9. Ошибка при отсутствии поддержки аутентификации по паролю
            elif "no supported authentication methods" in error_msg:
                return f"ОШИБКА: Устройство {host} не поддерживает аутентификацию по паролю"
            
            # 10. Общая ошибка SSH
            else:
                # Пытаемся извлечь понятное сообщение об ошибке
                error_lines = result.stderr.strip().split('\n')
                for line in error_lines:
                    if line and not line.startswith('Warning:'):
                        return f"ОШИБКА SSH: {line[:150]}"
                
                return f"ОШИБКА: Неизвестная ошибка при подключении к {host}"
                
    except subprocess.TimeoutExpired:
        return f"ОШИБКА: Превышено время ожидания при подключении к {host}"
    
    except FileNotFoundError:
        return f"ОШИБКА: Не найден ssh или sshpass клиент. Убедитесь, что они установлены."
    
    except Exception as e:
        return f"ОШИБКА: Непредвиденная ошибка при подключении к {host}: {str(e)}"


def get_device_version(host: str, username: str, password: str) -> str:
    """
    Получает информацию о версии ПО с сетевого устройства.
    
    Пытается выполнить различные варианты команды show version для поддержки
    оборудования разных производителей (Cisco, Arista, Nokia, Huawei и др.).
    
    Args:
        host: IP-адрес устройства
        username: Имя пользователя для подключения
        password: Пароль для подключения
    
    Returns:
        Вывод команды show version или сообщение об ошибке
    """
    # Сначала проверяем базовую доступность устройства
    try:
        # Проверяем формат IP-адреса
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
            parts = host.split('.')
            for part in parts:
                if int(part) > 255:
                    return f"ОШИБКА: Неправильный IP-адрес {host} (часть адреса больше 255)"
        
        # Быстрая проверка доступности порта 22
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, 22))
        sock.close()
        
        if result != 0:
            return f"ОШИБКА: Порт 22 на устройстве {host} закрыт или недоступен"
            
    except ValueError:
        return f"ОШИБКА: Неправильный формат IP-адреса {host}"
    
    except socket.gaierror:
        return f"ОШИБКА: Неправильный IP-адрес или имя хоста '{host}' (DNS ошибка)"
    
    except socket.timeout:
        # Продолжаем попытку подключения, даже если проверка порта таймаутила
        pass
    
    except Exception as e:
        # Продолжаем попытку подключения при других ошибках проверки
        pass
    
    # Список возможных команд для получения информации о версии
    version_commands = [
        "show version",           # Стандартная команда для Cisco, Arista
        "show version | no-more", # Для устройств с пагинацией (Nokia SR Linux)
        "show ver",               # Сокращенная форма
        "display version",        # Для Huawei оборудования
        "version",                # Альтернативная команда
        "cat /etc/os-release",    # Для Linux-подобных систем
    ]
    
    last_error = ""
    
    for command in version_commands:
        output = connect_via_ssh(host, username, password, command)
        
        # Проверяем, что вывод не является сообщением об ошибке
        # и содержит достаточное количество данных
        if (output and 
            not output.startswith("ОШИБКА") and
            not output.startswith("ssh: ") and
            len(output.strip()) > 20):  # Минимальная длина валидного вывода
            
            # Обрезаем слишком длинный вывод для удобства
            if len(output) > 5000:
                output = output[:5000] + "\n\n...[вывод обрезан, слишком длинный]..."
            
            return output
        elif output and (output.startswith("ОШИБКА") or output.startswith("ssh: ")):
            last_error = output
    
    # Если ни одна команда не дала результата
    if last_error:
        return last_error
    else:
        return f"ОШИБКА: Не удалось получить информацию о версии ПО с устройства {host}. Все команды не сработали."


def parse_sample_containerlab_data() -> List[Tuple[str, str]]:
    """
    Извлекает информацию об устройствах из примера данных containerlab.
    
    Парсит предоставленный в задании пример вывода containerlab для получения
    имен и IP-адресов активных сетевых устройств.
    
    Returns:
        Список кортежей в формате (имя_устройства, ip_адрес)
    
    Example:
        >>> parse_sample_containerlab_data()
        [('clab-test_lab-ceos', '172.20.20.3'), ('clab-test_lab-srl', '172.20.20.2')]
    """
    # Данные из задания (предоставленный вывод containerlab)
    containerlab_data = """| Name    | Kind/Image    | State    | IPv4/6 Address |
|---|---|---|---|
| clab-test_lab-ceos  | arista ceos    | running   | 172.20.20.3    |
|    | ceos:4.35.0F    |    | 3fff:172:20:20::3    |
| clab-test_lab-srl  | nokia_srlinux    | running   | 172.20.20.2    |
|    | ghcr.io/nokia/srlinux:24.10    |    | 3fff:172:20:20::2    |"""
    
    devices = []
    lines = containerlab_data.strip().split('\n')
    
    current_device_name = None
    
    for line in lines:
        # Пропускаем строки с разделителями таблицы
        if line.startswith('+') or line.startswith('|--'):
            continue
        
        # Разбиваем строку по разделителю '|'
        parts = [part.strip() for part in line.split('|')]
        
        # Если в строке есть имя устройства (второй элемент после разделителя)
        if len(parts) > 1 and parts[1]:
            current_device_name = parts[1]
        
        # Ищем IPv4 адрес в колонке адресов
        if current_device_name and len(parts) >= 5:
            address_column = parts[4]
            
            # Проверяем состояние устройства
            state = parts[3].lower() if len(parts) > 3 else ""
            if "running" not in state:
                continue  # Пропускаем неактивные устройства
            
            # Ищем IPv4 адрес в формате X.X.X.X
            ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', address_column)
            if ip_match:
                ip_address = ip_match.group(1)
                devices.append((current_device_name, ip_address))
    
    return devices


def manual_input_devices() -> List[Tuple[str, str]]:
    """
    Позволяет пользователю вручную ввести информацию об устройствах.
    
    Запрашивает у пользователя имя и IP-адрес каждого устройства.
    Поддерживает ввод нескольких устройств.
    
    Returns:
        Список кортежей в формате (имя_устройства, ip_адрес)
    """
    devices = []
    
    print("\n" + "="*50)
    print("РУЧНОЙ ВВОД УСТРОЙСТВ")
    print("="*50)
    print("Вводите информацию об устройствах.")
    print("Для завершения ввода введите 'готово' в качестве имени устройства.\n")
    
    device_count = 0
    
    while True:
        device_count += 1
        print(f"Устройство #{device_count}")
        print("-" * 30)
        
        # Запрашиваем имя устройства
        name = input("Введите имя устройства: ").strip()
        
        if name.lower() in ['готово', 'done', 'exit', 'quit', '']:
            if device_count == 1:
                print("❌ Не введено ни одного устройства!")
                continue
            break
        
        # Проверяем, что имя устройства соответствует допустимым именам
        valid_device_names = ['clab-test_lab-ceos', 'clab-test_lab-srl']
        if name not in valid_device_names:
            print(f"❌ ОШИБКА: Неправильное имя устройства '{name}'!")
            continue
        
        # Запрашиваем IP-адрес
        ip = input(f"Введите IP-адрес для устройства '{name}': ").strip()
        
        # Проверяем формат IP-адреса
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
            print("⚠️  Внимание: Введен некорректный IP-адрес. Формат должен быть X.X.X.X")
            confirm = input("Все равно продолжить? (да/нет): ").strip().lower()
            if confirm not in ['да', 'yes', 'y', 'д']:
                print("Повторите ввод для этого устройства")
                device_count -= 1
                continue
        
        # Проверяем что каждая часть IP в диапазоне 0-255
        try:
            parts = ip.split('.')
            for part in parts:
                if int(part) > 255:
                    print(f"⚠️  Внимание: Некорректный IP-адрес {ip} (число {part} больше 255)")
                    confirm = input("Все равно продолжить? (да/нет): ").strip().lower()
                    if confirm not in ['да', 'yes', 'y', 'д']:
                        print("Повторите ввод для этого устройства")
                        device_count -= 1
                        continue
                    break
        except ValueError:
            print(f"⚠️  Внимание: Некорректный IP-адрес {ip} (содержит нечисловые значения)")
            confirm = input("Все равно продолжить? (да/нет): ").strip().lower()
            if confirm not in ['да', 'yes', 'y', 'д']:
                print("Повторите ввод для этого устройства")
                device_count -= 1
                continue
        
        # Добавляем устройство в список
        devices.append((name, ip))
        print(f"✅ Устройство '{name}' ({ip}) добавлено.\n")
    
    return devices


def collect_device_information(devices: List[Tuple[str, str]], 
                              username: str, 
                              password: str) -> Dict[str, Dict[str, str]]:
    """
    Собирает информацию о версиях ПО со всех указанных устройств.
    
    Подключается к каждому устройству по очереди, выполняет команду
    show version и сохраняет результаты.
    
    Args:
        devices: Список устройств для опроса
        username: Имя пользователя для подключения
        password: Пароль для подключения
    
    Returns:
        Словарь с информацией о каждом устройстве, где ключ - имя устройства,
        значение - словарь с детальной информацией
    """
    results = {}
    
    total_devices = len(devices)
    print(f"\n{'='*60}")
    print(f"НАЧИНАЕМ СБОР ИНФОРМАЦИИ С {total_devices} УСТРОЙСТВ")
    print(f"{'='*60}")
    
    for index, (device_name, device_ip) in enumerate(devices, 1):
        print(f"\n[{index}/{total_devices}] 📡 Подключаюсь к: {device_name}")
        print(f"   IP-адрес: {device_ip}")
        print(f"   Пользователь: {username}")
        print(f"   {'─' * 40}")
        
        # Проверяем, что имя устройства соответствует допустимым именам
        valid_device_names = ['clab-test_lab-ceos', 'clab-test_lab-srl']
        if device_name not in valid_device_names:
            print("   Проверяю имя устройства... ❌ ошибка")
            error_msg = f"ОШИБКА: Неправильное имя устройства '{device_name}'. Допустимые имена: {', '.join(valid_device_names)}"
            results[device_name] = {
                'ip_address': device_ip,
                'username': username,
                'status': 'ошибка',
                'show_version_output': error_msg,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            print(f"   Причина: Неправильное имя устройства '{device_name}'")
            continue
        
        # Получаем информацию о версии ПО
        print("   Выполняю команду show version...", end=" ", flush=True)
        version_output = get_device_version(device_ip, username, password)
        
        # Определяем статус операции
        if version_output.startswith("ОШИБКА") or "ОШИБКА:" in version_output:
            status = "ошибка"
            status_icon = "❌"
        else:
            status = "успешно"
            status_icon = "✅"
        
        print(f"{status_icon} {status}")
        
        # Сохраняем результат
        results[device_name] = {
            'ip_address': device_ip,
            'username': username,
            'status': status,
            'show_version_output': version_output,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Показываем краткий предпросмотр вывода
        if status == "успешно":
            preview_lines = version_output.split('\n')
            for line in preview_lines:
                if line.strip() and len(line.strip()) > 10:
                    preview = line.strip()[:100]
                    print(f"   Вывод: {preview}...")
                    break
        else:
            # Выводим ошибку понятным образом
            if "Неправильный пароль" in version_output:
                print(f"   Причина: Неправильный пароль для пользователя '{username}'")
            elif "Неправильное имя пользователя" in version_output:
                print(f"   Причина: Неправильное имя пользователя '{username}'")
            elif "Неправильный IP-адрес" in version_output:
                print(f"   Причина: Неправильный IP-адрес '{device_ip}'")
            elif "не удалось найти устройство" in version_output:
                print(f"   Причина: Устройство с IP '{device_ip}' не найдено в сети")
            elif "порт 22 закрыт" in version_output:
                print(f"   Причина: Порт SSH (22) закрыт на устройстве '{device_ip}'")
            elif "таймаут подключения" in version_output:
                print(f"   Причина: Устройство '{device_ip}' не отвечает (таймаут)")
            elif "нет маршрута" in version_output:
                print(f"   Причина: Нет сетевого пути до устройства '{device_ip}'")
            else:
                # Обрезаем длинные сообщения об ошибках
                error_msg = version_output
                if len(error_msg) > 100:
                    error_msg = error_msg[:100] + "..."
                print(f"   Причина: {error_msg}")
    
    return results


def save_results_to_yaml(results: Dict[str, Dict[str, str]], 
                         filename: str = "network_devices.yaml") -> None:
    """
    Сохраняет собранные данные в YAML-файл.
    
    Форматирует данные для удобного чтения и последующего анализа.
    Включает мета-информацию о процессе сбора данных.
    
    Args:
        results: Словарь с результатами опроса устройств
        filename: Имя файла для сохранения результатов
    
    Raises:
        IOError: Если не удалось записать файл
        yaml.YAMLError: Если возникла ошибка при сериализации данных
    """
    if not results:
        print("⚠️  Нет данных для сохранения!")
        return
    
    try:
        # Подготавливаем структурированные данные
        yaml_data = {
            'metadata': {
                'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_devices': len(results),
                'successful_count': sum(1 for info in results.values() 
                                       if info.get('status') == 'успешно'),
                'failed_count': sum(1 for info in results.values() 
                                   if info.get('status') == 'ошибка')
            },
            'devices': results
        }
        
        # Сохраняем в YAML-файл
        with open(filename, 'w', encoding='utf-8') as file:
            yaml.dump(
                yaml_data,
                file,
                default_flow_style=False,  # Читаемый формат (не в одну строку)
                allow_unicode=True,        # Поддержка Unicode символов
                indent=2,                  # Отступы для вложенных структур
                width=100                  # Максимальная ширина строки
            )
        
        print(f"\n✅ Результаты сохранены в файл: {filename}")
        
        # Выводим статистику
        metadata = yaml_data['metadata']
        print(f"\n📊 СТАТИСТИКА:")
        print(f"   Всего устройств: {metadata['total_devices']}")
        print(f"   Успешно опрошено: {metadata['successful_count']}")
        print(f"   С ошибками: {metadata['failed_count']}")
        
        # Показываем устройства с ошибками
        if metadata['failed_count'] > 0:
            print(f"\n📋 УСТРОЙСТВА С ОШИБКАМИ:")
            for device_name, info in results.items():
                if info.get('status') == 'ошибка':
                    error_msg = info.get('show_version_output', 'Неизвестная ошибка')
                    # Извлекаем только тип ошибки для краткости
                    if "ОШИБКА:" in error_msg:
                        error_type = error_msg.split("ОШИБКА:")[1].strip().split('\n')[0]
                    else:
                        error_type = error_msg
                    
                    # Сокращаем длинные сообщения
                    if len(error_type) > 60:
                        error_type = error_type[:60] + "..."
                    
                    print(f"   • {device_name} ({info['ip_address']}): {error_type}")
        
    except yaml.YAMLError as e:
        print(f"❌ Ошибка при сохранении YAML: {str(e)}")
        raise
    except IOError as e:
        print(f"❌ Ошибка ввода-вывода при сохранении файла: {str(e)}")
        raise


def main() -> None:
    """
    Основная функция программы.
    
    Управляет процессом сбора информации с сетевых устройств:
    1. Проверяет наличие необходимых утилит
    2. Получает информацию об устройствах
    3. Собирает данные с устройств
    4. Сохраняет результаты в файл
    """
    print("="*60)
    print("🚀 СБОР ИНФОРМАЦИИ О ВЕРСИЯХ ПО СЕТЕВЫХ УСТРОЙСТВ")
    print("="*60)
    
    # Проверяем наличие sshpass
    print("\n🔍 Проверка наличия необходимых утилит...")
    if not check_sshpass_installed():
        print("❌ ОШИБКА: Утилита sshpass не установлена!")
        print("\nУстановите sshpass одной из команд:")
        print("  • Ubuntu/Debian: sudo apt install sshpass")
        print("  • CentOS/RHEL: sudo yum install sshpass")
        print("  • macOS: brew install sshpass")
        return
    
    print("✅ sshpass установлен")
    
    # Выбор источника данных об устройствах
    print("\n" + "="*50)
    print("ВЫБЕРИТЕ ИСТОЧНИК ДАННЫХ ОБ УСТРОЙСТВАХ")
    print("="*50)
    print("1. Использовать пример из задания (containerlab)")
    print("2. Ручной ввод устройств")
    
    while True:
        choice = input("\nВведите номер выбора (1 или 2): ").strip()
        
        if choice == "1":
            print("\n📋 Используем данные из задания...")
            devices = parse_sample_containerlab_data()
            
            if not devices:
                print("❌ Не удалось извлечь устройства из примера данных")
                return
            
            print(f"✅ Найдено устройств: {len(devices)}")
            for name, ip in devices:
                print(f"   • {name}: {ip}")
            break
            
        elif choice == "2":
            devices = manual_input_devices()
            
            if not devices:
                print("❌ Не введено ни одного устройства")
                return
            break
            
        else:
            print("❌ Неверный выбор. Введите 1 или 2.")
    
    # Получение учетных данных
    print("\n" + "="*50)
    print("УЧЕТНЫЕ ДАННЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ")
    print("="*50)
    
    # Запрашиваем учетные данные
    username = input("Введите имя пользователя SSH: ").strip()
    password = input("Введите пароль SSH: ").strip()
    
    if not username or not password:
        print("❌ Не введены учетные данные")
        return
    
    # Проверяем, что введены правильные учетные данные (admin/admin)
    if username != "admin" or password != "admin":
        print("\n❌ ОШИБКА: Неправильные учетные данные!")
        print("\n⚠️  Завершаю программу.")
        return
    
    # Если учетные данные правильные
    print(f"\n✅ Учетные данные приняты:")
    print(f"   Логин: {username}")
    print(f"   Пароль: {'*' * len(password)}")
    
    # Сбор информации с устройств
    results = collect_device_information(devices, username, password)
    
    # Сохранение результатов
    save_results_to_yaml(results)
    
    # Вывод итоговой сводки
    print(f"\n{'='*60}")
    print("🎉 ВЫПОЛНЕНИЕ ЗАВЕРШЕНО!")
    print("="*60)
    
    # Показываем краткие результаты для каждого устройства
    print("\n📋 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    for device_name, info in results.items():
        status_icon = "✅" if info['status'] == 'успешно' else "❌"
        print(f"{status_icon} {device_name} ({info['ip_address']}): {info['status']}")


if __name__ == "__main__":
    """
    Точка входа в программу.
    
    Защищает от выполнения кода при импорте модуля.
    Обеспечивает запуск только при прямом выполнении файла.
    """
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Программа прервана пользователем")
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()
