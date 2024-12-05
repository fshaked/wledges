# wledges

Active edges for Wayland compositors.

You might also be interested in [wlosd](https://github.com/fshaked/wlosd)
which provides on-screen display for Wayland compositors.

## Supported Desktops

Tested on [Sway](https://swaywm.org/), but should work on all Wayland
compositors that support the Layer Shell protocol. More precisely,
it should work on all
[desktops supported](https://github.com/wmww/gtk4-layer-shell?tab=readme-ov-file#supported-desktops)
by gtk4-layer-shell.

## Installation

### Dependencies:

Debian/Ubuntu:

```
sudo apt install libgirepository-1.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-4.0 libgtk4-layer-shell-dev
pip install pygobject
```

Fedora:

```
sudo dnf install gcc gobject-introspection-devel cairo-gobject-devel pkg-config python3-devel gtk4 gtk4-layer-shell-devel
pip install pygobject
```

Arch Linux:

```
sudo pacman -S python cairo pkgconf gobject-introspection gtk4 gcc gtk4-layer-shell
pip install pygobject
```

For other distributions, you will need:
- Python 3: [instructions](https://wiki.python.org/moin/BeginnersGuide/Download)
- pygobject: [instructions](https://pygobject.gnome.org/getting_started.html)
- gtk4-layer-shell: [instructions](https://github.com/wmww/gtk4-layer-shell)

### Install wledges:
From PyPi:
```
pip install wledges
```

Or clone this repository.

## Usage

wledges allocates for each screen edge, and corner, specified on the command
line, a rectangular area of the specified size.
Every time the mouse cursor interacts with those areas (moves in, clicked on,
scrolled on) wledges prints a line to standard output.
The line indicates which edge or corner was interacted with, and what was the
interaction.

For example, running the following command in a terminal allocates a 1 pixel
active line, 30% the length of the screen, at the top (centre) of the DP-1
output, and a 1 by 1 active pixel at the top-left corner of the screen.

```
wledges --top 30%x1 --top-left 1x1 DP-1
```

The command displays a slightly bigger rectangle (30%x50) to indicate that this
edge is active.
The `--css` command line argument can be used to pass a GTK4 style sheet (see
[style.css](https://github.com/fshaked/wledges/blob/main/style.css) for example,
and [overview](https://docs.gtk.org/gtk4/css-overview.html) and
[properties](https://docs.gtk.org/gtk4/css-properties.html) for documentation),
that can be used to style the indicator, to make it less obtrusive.
In any case, only input events from the (smaller) active area are captured by
wledges; other events are sent to the window below.

Moving the mouse cursor to the very top of the screen (being inside the
displayed 30%x50 rectangle is not enough, the cursor must be in the 30%x1 active
area) first prints (after a delay of 0.75 seconds) "top timeout", and then
repeatedly (every 0.75 second) "top repeat", until the cursor is moved out of
the rectangle.
Clicking the mouse left button while the cursor is in the active rectangle
prints "top press-1", and similarly for the other mouse buttons.
Scrolling the mouse wheel prints "top scroll-DIRECTION" where DIRECTION is one
of up, down, left, right.
Clicking or scrolling the mouse also cancels the timeout and repeat lines, until
the cursor moves out of the active area, and comes back in.

If you are using [Sway](https://swaywm.org/), the following Bash script can be
used to switch workspaces when the mouse cursor touches the left or right edges
of the screen (change the first line to match your output, see `swaymsg -t
get_outputs` for a list of outputs):

```
output='DP-1'

while IFS=' ' read -r line; do
  case "${line}" in
    left\ timeout | left\ repeat)
      swaymsg "focus output ${output} ; workspace prev_on_output"
      ;;
    right\ timeout | right\ repeat)
      swaymsg "focus output ${output} ; workspace next_on_output"
      ;;
  esac
done < <(python -m wledges --left 1x50% --right 1x50% "${output}")
```

## License

MIT, see [LICENSE](https://github.com/fshaked/wledges/blob/main/LICENSE)
