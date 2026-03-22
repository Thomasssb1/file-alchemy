from __future__ import annotations

from dataclasses import dataclass, field

from .conversion_route import ConversionRoute


@dataclass
class ConversionRegistry:
    """Central store of all supported (input_ext, output_ext) routes."""

    _routes: dict[tuple[str, str], ConversionRoute] = field(
        default_factory=dict, init=False, repr=False
    )

    def register(self, route: ConversionRoute) -> None:
        """Add *route* to the registry, overwriting any existing entry."""
        self._routes[(route.input_ext, route.output_ext)] = route

    def get_route(self, input_ext: str, output_ext: str) -> ConversionRoute | None:
        """Return the route for *(input_ext, output_ext)*, or ``None``."""
        key = (input_ext.lower().lstrip("."), output_ext.lower().lstrip("."))
        return self._routes.get(key)

    def outputs_for(self, input_ext: str) -> list[str]:
        """Return all output extensions reachable from *input_ext*."""
        key_ext = input_ext.lower().lstrip(".")
        return [out_ext for (in_ext, out_ext) in self._routes if in_ext == key_ext]

    def is_supported(self, input_ext: str, output_ext: str) -> bool:
        """Return ``True`` if the conversion is registered."""
        return self.get_route(input_ext, output_ext) is not None

    @property
    def all_routes(self) -> list[ConversionRoute]:
        return list(self._routes.values())
