import time
import inspect
from colorama import Fore, Style, init
from config import COLOR_THRESHOLDS, MIN_TIME_IN_MS_THRESHOLD, MAX_TIME_IN_MS_THRESHOLD, TIMER_ENABLED

_warning_shown = False

# init colorama
init(autoreset=True)

def show_timer_warning():
    """Show initial warning about performance monitoring."""
    global _warning_shown
    if not _warning_shown and TIMER_ENABLED:
        print(f"{Fore.LIGHTBLACK_EX}Performance monitoring is enabled. Operations taking between "
              f"{MIN_TIME_IN_MS_THRESHOLD}ms and {MAX_TIME_IN_MS_THRESHOLD}ms will be logged. ")
        print(f"This is not an error. Configure thresholds in config.py{Style.RESET_ALL}")
        _warning_shown = True

def timer(func):
    """
    Decorator to calculate the runtime of a method in milliseconds,
    color-code the output, and display the file, class, and method/function name.
    Only shows operations between MIN_TIME_IN_MS_THRESHOLD and MAX_TIME_IN_MS_THRESHOLD.
    """
    def wrapper(*args, **kwargs):
        if not TIMER_ENABLED:
            return func(*args, **kwargs)

        show_timer_warning()
        
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

        # Only log if within thresholds
        if MIN_TIME_IN_MS_THRESHOLD < runtime_ms < MAX_TIME_IN_MS_THRESHOLD:
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
            print(output)

        return result
    return wrapper