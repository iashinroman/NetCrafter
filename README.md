# NetCrafter

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
    
    Note:
        В production-среде рекомендуется использовать SSH-ключи вместо паролей
        и не отключать проверку ключей хоста.
    """
    try:
        # Формируем команду SSH с использованием sshpass для передачи пароля
        ssh_command = [
            "sshpass", "-p", password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",    # Отключаем проверку ключей хоста
            "-o", "UserKnownHostsFile=/dev/null", # Не сохраняем ключи в known_hosts
            "-o", "ConnectTimeout=30",           # Таймаут подключения 30 секунд
            "-o", "PasswordAuthentication=yes",  # Разрешаем аутентификацию по паролю
            f"{username}@{host}",
            command
        ]
        
        # Выполняем команду с ограничением времени выполнения
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=30,  # Общий таймаут 30 секунд
            encoding='utf-8',
            errors='ignore'  # Игнорируем ошибки кодировки
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            # Анализируем сообщение об ошибке для лучшей диагностики
            error_msg = result.stderr.lower()
            
            if "permission denied" in error_msg:
                return f"ОШИБКА: Неверный логин или пароль для {host}"
            elif "connection refused" in error_msg:
                return f"ОШИБКА: Не удалось подключиться к {host} (порт 22 закрыт)"
            elif "connection timed out" in error_msg:
                return f"ОШИБКА: Таймаут подключения к {host}"
            elif "no route to host" in error_msg:
                return f"ОШИБКА: Нет маршрута до {host}"
            else:
                return f"ОШИБКА SSH: {result.stderr[:100].strip()}"
                
    except subprocess.TimeoutExpired:
        return f"ОШИБКА: Превышено время ожидания при подключении к {host}"
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
    # Список возможных команд для получения информации о версии
    # Упорядочен от наиболее распространенных к менее распространенным
    version_commands = [
        "show version",           # Стандартная команда для Cisco, Arista
        "show version | no-more", # Для устройств с пагинацией (Nokia SR Linux)
        "show ver",               # Сокращенная форма
        "display version",        # Для Huawei оборудования
        "version",                # Альтернативная команда
        "cat /etc/os-release",    # Для Linux-подобных систем
    ]
    
    for command in version_commands:
        output = connect_via_ssh(host, username, password, command)
        
        # Проверяем, что вывод не является сообщением об ошибке
        # и содержит достаточное количество данных
        if (output and 
            not output.startswith("ОШИБКА") and
            len(output.strip()) > 20):  # Минимальная длина валидного вывода
            
            # Обрезаем слишком длинный вывод для удобства
            if len(output) > 5000:
                output = output[:5000] + "\n\n...[вывод обрезан, слишком длинный]..."
            
            return output
    
    # Если ни одна команда не дала результата
    return "Не удалось получить информацию о версии ПО. Проверьте доступность устройства."


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
        print(f"   {'─' * 40}")
        
        # Получаем информацию о версии ПО
        print("   Выполняю команду show version...", end=" ", flush=True)
        version_output = get_device_version(device_ip, username, password)
        
        # Определяем статус операции
        if version_output.startswith("ОШИБКА") or "Не удалось" in version_output:
            status = "ошибка"
            status_icon = "❌"
        else:
            status = "успешно"
            status_icon = "✅"
        
        print(f"{status_icon} {status}")
        
        # Сохраняем результат
        results[device_name] = {
            'ip_address': device_ip,
            'status': status,
            'show_version_output': version_output,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Показываем краткий предпросмотр вывода
        if status == "успешно":
            preview = version_output.split('\n')[0][:100]
            print(f"   Первая строка вывода: {preview}...")
        else:
            print(f"   Причина: {version_output}")
    
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
    
    # Для примера из задания используем стандартные учетные данные
    if choice == "1":
        username = "admin"
        password = "admin"
        print(f"Используются стандартные учетные данные:")
        print(f"  Логин: {username}")
        print(f"  Пароль: {password}")
        print("\n⚠️  Если эти учетные данные не подходят, измените их в коде.")
    else:
        username = input("Введите имя пользователя SSH: ").strip()
        password = input("Введите пароль SSH: ").strip()
        
        if not username or not password:
            print("❌ Не введены учетные данные")
            return
    
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
