import io
import sys
import time
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# Windows cp1252 can't encode Unicode box-drawing / emoji chars — force UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Logger:
    def __init__(self, name: str = "") -> None:
        self._name = name

    def stage(self, msg: str) -> None:
        print(f"\n{Style.BRIGHT}{Fore.CYAN}╔══ {msg} ══{Style.RESET_ALL}")

    def info(self, msg: str) -> None:
        print(f"  {Style.DIM}[{_ts()}]{Style.RESET_ALL} {msg}")

    def success(self, msg: str) -> None:
        print(f"  {Fore.GREEN}✓{Style.RESET_ALL} {msg}")

    def warn(self, msg: str) -> None:
        print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL}  {msg}")

    def error(self, msg: str) -> None:
        print(f"  {Fore.RED}✗{Style.RESET_ALL} {msg}")

    def source(self, source_id: str, status: str, detail: str = "") -> None:
        icon = (
            f"{Fore.YELLOW}↻{Style.RESET_ALL}" if status == "changed"
            else f"{Fore.RED}✗{Style.RESET_ALL}" if status == "error"
            else f"{Style.DIM}–{Style.RESET_ALL}"
        )
        color = Fore.YELLOW if status == "changed" else Fore.RED if status == "error" else ""
        label = f"{color}{source_id:<28}{Style.RESET_ALL}"
        tail = f"  {Style.DIM}{detail}{Style.RESET_ALL}" if detail else ""
        print(f"  {icon} {label}{tail}")

    def timing(self, label: str, elapsed_ms: float) -> None:
        display = f"{elapsed_ms:.0f}ms" if elapsed_ms < 1000 else f"{elapsed_ms / 1000:.1f}s"
        print(f"  {Style.DIM}{label}: {display}{Style.RESET_ALL}")

    def stat(self, label: str, value: object) -> None:
        print(f"  {Fore.MAGENTA}→{Style.RESET_ALL} {label}: {Style.BRIGHT}{value}{Style.RESET_ALL}")


logger = Logger()
