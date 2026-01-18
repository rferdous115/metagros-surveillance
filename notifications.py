"""
Desktop Notifications for Security Events
Provides Windows toast notifications when security events are detected.
"""
import threading

_notifications_enabled = True
_notifier = None

def init_notifier():
    global _notifier
    try:
        from win10toast import ToastNotifier
        _notifier = ToastNotifier()
        print("[Notifications] Initialized")
        return True
    except ImportError:
        print("[Notifications] win10toast not installed")
        return False

def notify(title: str, message: str, duration: int = 5):
    global _notifier, _notifications_enabled
    if not _notifications_enabled:
        return
    if _notifier is None:
        if not init_notifier():
            print(f"NOTIFICATION: {title} - {message}")
            return
    try:
        def _show():
            try:
                _notifier.show_toast(title, message, duration=duration, threaded=False)
            except:
                pass
        threading.Thread(target=_show, daemon=True).start()
    except Exception as e:
        print(f"[Notifications] Error: {e}")

def set_enabled(enabled: bool):
    global _notifications_enabled
    _notifications_enabled = enabled

def notify_loitering(person_id: int, duration: float):
    notify("Loitering Detected", f"Person #{person_id} in area for {duration:.0f}s")

def notify_vehicle_loitering(vehicle_id: int, duration: float):
    notify("Vehicle Loitering", f"Vehicle #{vehicle_id} stationary for {duration:.0f}s")

def notify_crowd(count: int):
    notify("Crowd Detected", f"{count} people detected")

def notify_zone_intrusion(zone_name: str):
    notify("Zone Intrusion!", f"Entry to restricted zone: {zone_name}")
