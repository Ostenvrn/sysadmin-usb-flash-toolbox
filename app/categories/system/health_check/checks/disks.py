def _get_disks() -> list:
    """Собирает информацию о дисках (без дубликатов)."""
    disks = []
    seen_devices = set()

    if os_detector.is_windows:
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            if os.path.exists(path):
                try:
                    total, used, free = shutil.disk_usage(path)
                    disks.append({
                        "path": path,
                        "total_gb": round(total / 1024**3, 2),
                        "used_gb": round(used / 1024**3, 2),
                        "free_gb": round(free / 1024**3, 2),
                        "percent": round((used / total) * 100, 1) if total > 0 else 0,
                    })
                except Exception:
                    pass
    else:
        # Linux: проверяем, что это разные устройства (st_dev)
        for path in ["/", "/home", "/var", "/boot"]:
            if not os.path.exists(path):
                continue
            try:
                st = os.stat(path)
                dev_id = st.st_dev
                if dev_id in seen_devices:
                    continue  # уже добавляли это устройство
                seen_devices.add(dev_id)

                total, used, free = shutil.disk_usage(path)
                disks.append({
                    "path": path,
                    "total_gb": round(total / 1024**3, 2),
                    "used_gb": round(used / 1024**3, 2),
                    "free_gb": round(free / 1024**3, 2),
                    "percent": round((used / total) * 100, 1) if total > 0 else 0,
                })
            except Exception:
                pass

    return disks
