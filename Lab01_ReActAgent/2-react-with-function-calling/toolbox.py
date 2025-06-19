import inspect
from typing import Iterable, Dict, Callable, Union, Type

class ToolBox:
    def __init__(self) -> None:
        # Stores tool name and docstring used by the LLM to call the tools
        self.tools_dict: Dict[str, str] = {}

    def store(self, items: Iterable[Union[Callable, Type]]) -> Dict[str, str]:
        """
        Stores functions or public methods of tool classes along with their docstrings.

        Parameters:
        items (Iterable[Callable or class]): Function objects or classes containing tool methods.

        Returns:
        Dict[str, str]: Mapping of tool names to their docstrings.
        """
        for obj in items:
            if inspect.isfunction(obj) or inspect.ismethod(obj):
                self._register(obj)
            elif inspect.isclass(obj):
                # Register each public method from the class
                for name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                    if not name.startswith("_"):
                        self._register(method)
            else:
                raise TypeError(
                    f"Tool must be a function, method, or class. Got {type(obj).__name__}."
                )

        return self.tools_dict

    def describe_tools(self) -> str:
        """
        Returns the description of all tools.

        Returns:
        str: Tool names and their docstrings, formatted.
        """
        return "\n".join(f"{name}: \"{doc}\"" for name, doc in self.tools_dict.items())

    def _register(self, func: Callable) -> None:
        """
        Registers a single function with its docstring.

        Parameters:
        func (Callable): Function to register.
        """
        name = func.__name__
        doc = (func.__doc__ or "").strip()
        self.tools_dict[name] = doc
