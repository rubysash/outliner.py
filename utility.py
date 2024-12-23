import time
import inspect
from colorama import Fore, Style
from config import COLOR_THRESHOLDS

def timer(func):
    """
    Decorator to calculate the runtime of a method in milliseconds,
    color-code the output, and display the file, class, and method/function name.
    """
    def wrapper(*args, **kwargs):
        # Get file and class name
        frame = inspect.currentframe()
        caller = inspect.getouterframes(frame)[1]
        file_name = caller.filename.split("/")[-1]
        class_name = args[0].__class__.__name__ if args else None
        function_name = func.__name__

        # Measure runtime
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        runtime_ms = (end_time - start_time) * 1000

        # Determine the color based on thresholds
        if runtime_ms > COLOR_THRESHOLDS["red"]:
            color = Fore.RED
        elif runtime_ms > COLOR_THRESHOLDS["orange"]:
            color = Fore.LIGHTRED_EX
        elif runtime_ms > COLOR_THRESHOLDS["yellow"]:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN

        # Prepare aligned output
        output = (
            f"{color}{runtime_ms:>10.2f} ms"
            f" | {file_name}"
            f"{f' | {class_name}' if class_name else ''}"
            f" | {function_name}{Style.RESET_ALL}"
        )
        if runtime_ms > 1:
            print(output)

        return result

    return wrapper