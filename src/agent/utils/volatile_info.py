from datetime import datetime


def build_volatile_info() -> str:
    now = datetime.now().astimezone()
    tz = now.strftime("%Z")
    return (
        "<system-reminder>\n"
        f"Current time: {now.strftime(f'%Y-%m-%d %H:%M:%S {tz}')}\n"
        "</system-reminder>"
    )
