# ui.py
import os
from rich.console import Console
from rich.panel import Panel
from rich import box

console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    console.print(Panel.fit("[bold cyan]TELEGRAM MANAGER CONSOLE[/bold cyan]", box=box.DOUBLE, padding=(1, 2)))

def print_manual():
    console.print(Panel(
        "[bold yellow]Инструкция по использованию:[/bold yellow]\n"
        "1. Добавьте аккаунт Telegram.\n"
        "2. Выберите папку для рассылки.\n"
        "3. Подготовьте сообщения в файле messages.txt или через |.\n",
        title="[bold magenta]Мануал[/bold magenta]",
        box=box.ROUNDED, padding=(1, 2)
    ))
