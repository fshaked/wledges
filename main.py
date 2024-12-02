"""Active edges for wayland."""

import argparse
from ctypes import CDLL
import functools
import logging
import typing as t

# https://pycairo.readthedocs.io/en/latest/reference/index.html
import cairo

# For GTK4 Layer Shell to get linked before libwayland-client we must
# explicitly load it before importing with gi
CDLL("libgtk4-layer-shell.so")

# yapf: disable
# pylint: disable=wrong-import-position
import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
# https://amolenaar.pages.gitlab.gnome.org/pygobject-docs/
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
# https://github.com/wmww/gtk4-layer-shell
from gi.repository import Gtk4LayerShell
# pylint: enable=wrong-import-position
# yapf: enable

logger: logging.Logger = logging.getLogger(__name__)

ARGS: t.Optional[argparse.Namespace] = None

EDGE_STR_TO_GTKLAYERSHELL: dict[str, list] = {
    "top": [Gtk4LayerShell.Edge.TOP],
    "bottom": [Gtk4LayerShell.Edge.BOTTOM],
    "left": [Gtk4LayerShell.Edge.LEFT],
    "right": [Gtk4LayerShell.Edge.RIGHT],
    "top-left": [Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.LEFT],
    "top-right": [Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.RIGHT],
    "bottom-left": [Gtk4LayerShell.Edge.BOTTOM, Gtk4LayerShell.Edge.LEFT],
    "bottom-right": [Gtk4LayerShell.Edge.BOTTOM, Gtk4LayerShell.Edge.RIGHT],
}

EDGES: set[str] = set(EDGE_STR_TO_GTKLAYERSHELL.keys())


class Dimension:  # pylint: disable=too-few-public-methods
    "Parse a VALUE[%] dimension."

    def __init__(self, dim: str) -> None:
        self._is_percent = dim.endswith("%")
        self._value = int(dim.removesuffix("%"))

    def value(self, length: int | float) -> int:
        return int(self._value * length /
                   100) if self._is_percent else self._value


class Dimensions:
    "Parse WIDTH[%]xHEIGHT[%] dimensions."

    def __init__(self, dims: str) -> None:
        width, height = dims.split("x", 1)
        self._width = Dimension(width)
        self._height = Dimension(height)

    def width(self, monitor: Gdk.Monitor) -> int:
        return self._width.value(monitor.get_geometry().width)

    def height(self, monitor: Gdk.Monitor) -> int:
        return self._height.value(monitor.get_geometry().height)

    def window(self, monitor: Gdk.Monitor,
               edge: str) -> tuple[int, int, int, int]:
        width_ext = max(50, self.width(monitor)) - self.width(monitor)
        height_ext = max(50, self.height(monitor)) - self.height(monitor)
        x_offset = int(width_ext / 2) if edge in [
            "top", "bottom"
        ] else width_ext if edge.endswith("right") else 0
        y_offset = int(height_ext / 2) if edge in [
            "left", "right"
        ] else height_ext if edge.startswith("bottom") else 0

        return (x_offset, y_offset, self.width(monitor) + width_ext,
                self.height(monitor) + height_ext)


class Edge(Gtk.Window):

    def __init__(self, application: Gtk.Application, edge: str,
                 dims: Dimensions) -> None:
        super().__init__(application=application, name=edge)

        self._dims = dims
        self._timer = None

        # This container will respect the size request of the inner box.
        self._layout = Gtk.Fixed()
        self.set_child(self._layout)

        # Box is an arbitrary widget that lets you set its background.
        self._box = Gtk.Box()
        # 0,0 is an arbitrary position, it will be set correctly when
        # update_geometry is called.
        self._layout.put(self._box, 0, 0)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self.on_cross, True)
        motion.connect("leave", self.on_cross, None, None, False)
        self._box.add_controller(motion)

        for button in range(1, 9):
            click = Gtk.GestureClick(button=button)
            click.connect("pressed", self.on_press, button)
            self._box.add_controller(click)

        scroll = Gtk.EventControllerScroll()
        scroll.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self.on_scroll)
        self._box.add_controller(scroll)

    def update_geometry(self, monitor: Gdk.Monitor) -> None:
        x_offset, y_offset, width, height = self._dims.window(
            monitor, self.get_name())
        self.set_default_size(width, height)
        self._layout.move(self._box, x_offset, y_offset)
        self._box.set_size_request(self._dims.width(monitor),
                                   self._dims.height(monitor))

    def set_input_region(self, _src, monitor: Gdk.Monitor) -> None:
        "Catch events only in the box, and let the rest pass through."
        surface = self.get_native().get_surface()
        if surface:
            x_offset, y_offset, _width, _height = self._dims.window(
                monitor, self.get_name())
            # pylint: disable-next=no-member
            region = cairo.Region(
                # pylint: disable-next=no-member
                cairo.RectangleInt(x_offset, y_offset,
                                   self._dims.width(monitor),
                                   self._dims.height(monitor)))
            surface.set_input_region(region)

    def on_cross(self, _src, _x: float, _y: float, enter: bool) -> bool:
        if enter:
            self.add_css_class("hover")
            if self._timer:
                GLib.source_remove(self._timer)
            self._timer = GLib.timeout_add(ARGS.timeout, self.on_timeout, False)
        else:
            self.remove_css_class("hover")
            if self._timer:
                GLib.source_remove(self._timer)
                self._timer = None
        return True

    def on_timeout(self, is_repeat: bool) -> bool:
        if self._timer:
            event = "repeat" if is_repeat else "timeout"
            print(f"{self.get_name()} {event}", flush=True)
            if is_repeat:
                return GLib.SOURCE_CONTINUE
            self._timer = GLib.timeout_add(ARGS.repeat, self.on_timeout, True)
        return GLib.SOURCE_REMOVE

    def on_press(self, _src, _n_press: int, _x: float, _y: float,
                 button: int) -> bool:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        print(f"{self.get_name()} press-{button}", flush=True)
        return True

    def on_scroll(self, _src, dx: float, dy: float) -> bool:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        if dy != 0:
            direction: str = "up" if dy < 0 else "down"
            print(f"{self.get_name()} scroll-{direction}", flush=True)
        if dx != 0:
            direction: str = "left" if dx < 0 else "right"
            print(f"{self.get_name()} scroll-{direction}", flush=True)
        return True


class MainApp(Gtk.Application):

    def __init__(self) -> None:
        assert ARGS
        super().__init__(
            application_id="com.wledges",
            # Allow multiple instances.
            flags=Gio.ApplicationFlags.NON_UNIQUE)

        self._monitor: t.Optional[Gdk.Monitor] = None
        self._windows: list[Edge] = []

        display = Gdk.DisplayManager.get().get_default_display()

        if ARGS.css:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(ARGS.css)
            Gtk.StyleContext.add_provider_for_display(
                display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def on_activate(self, _src) -> None:
        monitors = Gdk.DisplayManager.get().get_default_display().get_monitors()
        # Listen to outputs being plugged and unplugged.
        monitors.connect("items-changed", self.on_monitors_changed, False)
        # Trigger an output change to set up the windows as needed.
        self.on_monitors_changed(monitors, 0, 0, len(monitors), True)
        # Don't quit when all windows are closed (e.g. output is unplugged).
        self.hold()

    def create_windows(self, monitor: Gdk.Monitor) -> None:
        self._windows = [Edge(self, edge, dims) for (edge, dims) in ARGS.edges]
        for window in self._windows:
            window.update_geometry(self._monitor)
            window.connect("realize", window.set_input_region, self._monitor)

            window.add_css_class(ARGS.output)

            Gtk4LayerShell.init_for_window(window)
            Gtk4LayerShell.set_monitor(window, monitor)
            Gtk4LayerShell.set_layer(window, Gtk4LayerShell.Layer.OVERLAY)
            for gtk_edge in EDGE_STR_TO_GTKLAYERSHELL[window.get_name()]:
                Gtk4LayerShell.set_anchor(window, gtk_edge, True)

            window.present()

    def on_update_geometry(self, _monitor: Gdk.Monitor, _param) -> None:
        for window in self._windows:
            window.update_geometry(self._monitor)
            window.set_input_region(window, self._monitor)

    # pylint: disable-next=too-many-positional-arguments,too-many-arguments
    def on_monitors_changed(self, monitors: Gio.ListStore, position: int,
                            removed: int, added: int,
                            now: bool) -> t.Optional[bool]:
        if not now:
            # It takes time for the monitor.get_connector() to get the correct
            # value, so we wait a second.
            GLib.timeout_add(int(1 * 1000), self.on_monitors_changed, monitors,
                             position, removed, added, True)
            return None

        for monitor in monitors:
            if monitor.get_connector() == ARGS.output:
                if self._monitor is None:
                    monitor.connect("notify::geometry", self.on_update_geometry)
                    self._monitor = monitor
                    self.create_windows(monitor)
                return GLib.SOURCE_REMOVE

        # output was removed
        self._monitor = None
        self._windows = []
        return GLib.SOURCE_REMOVE


def main() -> None:
    """Entry point."""
    logging.basicConfig(level=logging.WARN)

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__)
    # yapf: disable
    parser.add_argument("output", default="",
                        metavar="OUTPUT", help="set the output")
    parser.add_argument("-c", "--css", default=None,
                        metavar="FILE", help="set the css file")
    parser.add_argument("-v", "--verbosity", action="count", default=0,
                        help="increase output verbosity")
    parser.add_argument("-V", "--version", action="version", version="%(prog)s 0.0")
    parser.add_argument("-t", "--timeout", default=750,
                        metavar="MSEC", help="(default 750) trigger timeout"
                        " event after MSEC milliseconds.")
    parser.add_argument("-r", "--repeat", default=750,
                        metavar="MSEC", help="(default 750) re-trigger a"
                        " timeout event after MSEC milliseconds.")
    for edge in EDGES:
        parser.add_argument(f"--{edge}", metavar="WxH",
                            action="append", dest="edges",
                            type=functools.partial(lambda edge, x: (edge, Dimensions(x)), edge),
                            help=f"set the {edge} edge")
    # yapf: enable

    global ARGS  # pylint: disable=global-statement
    ARGS = parser.parse_args()

    match ARGS.verbosity:
        case 0:
            logger.setLevel(logging.ERROR)
        case 1:
            logger.setLevel(logging.WARN)
        case 2:
            logger.setLevel(logging.INFO)
        case _:
            logger.setLevel(logging.DEBUG)
            logger.debug("logging level: DEBUG")

    app: MainApp = MainApp()
    app.connect("activate", app.on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
